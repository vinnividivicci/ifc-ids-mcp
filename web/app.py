import os
import sys
import json
import asyncio
from typing import List, Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from web.mcp_client import MCPClient

# Configuration
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY not found in environment variables.")

# Initialize Gemini
genai.configure(api_key=GOOGLE_API_KEY)

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# MCP Client instance
mcp_client: MCPClient = None

# Chat models
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class ChatResponse(BaseModel):
    response: str

@app.on_event("startup")
async def startup_event():
    global mcp_client
    # Command to run the MCP server
    # Assuming we are running from the root of the repo
    server_command = [sys.executable, "-m", "ids_mcp_server"]
    
    mcp_client = MCPClient(server_command)
    await mcp_client.start()
    print("MCP Client started and connected to server.")

@app.on_event("shutdown")
async def shutdown_event():
    if mcp_client:
        await mcp_client.stop()
        print("MCP Client stopped.")

import sys

def sanitize_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize JSON schema for Gemini compatibility."""
    if not isinstance(schema, dict):
        return schema
    
    new_schema = schema.copy()
    
    # Remove unsupported fields
    for field in ["anyOf", "oneOf", "allOf", "title", "$schema", "default"]:
        if field in new_schema:
            # For now, just take the first option if it's a combination
            # This is a simplification and might not work for all cases
            if field in ["anyOf", "oneOf", "allOf"] and isinstance(new_schema[field], list) and new_schema[field]:
                # Try to merge the first option
                first_option = new_schema[field][0]
                if isinstance(first_option, dict):
                    # Recursively sanitize the option
                    sanitized_option = sanitize_schema(first_option)
                    # Merge into current schema (excluding the combination field)
                    del new_schema[field]
                    new_schema.update(sanitized_option)
            else:
                del new_schema[field]

    # Recursively sanitize properties
    if "properties" in new_schema:
        new_schema["properties"] = {
            k: sanitize_schema(v) for k, v in new_schema["properties"].items()
        }
    
    if "items" in new_schema:
        new_schema["items"] = sanitize_schema(new_schema["items"])

    return new_schema

def convert_mcp_tool_to_gemini(tool_def: Dict[str, Any]) -> FunctionDeclaration:
    """Convert MCP tool definition to Gemini FunctionDeclaration."""
    schema = tool_def.get("inputSchema", {})
    sanitized_schema = sanitize_schema(schema)
    
    return FunctionDeclaration(
        name=tool_def["name"],
        description=tool_def.get("description", ""),
        parameters=sanitized_schema
    )

@app.post("/chat")
async def chat(request: ChatRequest):
    if not mcp_client:
        raise HTTPException(status_code=503, detail="MCP Client not initialized")

    async def event_generator() -> AsyncGenerator[str, None]:
        # 1. Get tools from MCP server
        try:
            mcp_tools = await mcp_client.list_tools()
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # 2. Convert to Gemini tools
        gemini_tools = [convert_mcp_tool_to_gemini(t) for t in mcp_tools]
        
        # 3. Initialize model with tools
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=[Tool(function_declarations=gemini_tools)]
        )
        
        # 4. Build history
        history = []
        for msg in request.messages[:-1]:
            history.append({"role": "user" if msg.role == "user" else "model", "parts": [msg.content]})
        
        chat_session = model.start_chat(history=history)
        
        # 5. Send message and handle tool calls
        user_message = request.messages[-1].content
        
        # Send thinking event
        yield f"data: {json.dumps({'type': 'thinking', 'content': 'Processing your request...'})}\n\n"
        
        # We need a loop to handle multiple tool calls
        response = chat_session.send_message(user_message)
        
        while True:
            # Check if there are function calls
            if not response.parts:
                 break
            
            # Check for thinking/reasoning content
            for part in response.parts:
                if hasattr(part, 'thought') and part.thought:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': part.thought})}\n\n"
                 
            part = response.parts[0]
            if fn := part.function_call:
                # Execute tool
                tool_name = fn.name
                # Convert protobuf objects to JSON-serializable types
                def to_serializable(obj):
                    if hasattr(obj, 'items'):  # dict-like
                        return {k: to_serializable(v) for k, v in obj.items()}
                    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                        return [to_serializable(v) for v in obj]
                    else:
                        return obj
                tool_args = to_serializable(dict(fn.args))
                
                print(f"Executing tool: {tool_name} with args: {tool_args}")
                
                # Send tool use event with args
                yield f"data: {json.dumps({'type': 'tool_use', 'tool': tool_name, 'args': tool_args})}\n\n"
                
                try:
                    tool_result = await mcp_client.call_tool(tool_name, tool_args)
                    
                    # Send tool result event
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'success': True})}\n\n"
                    
                    # Send result back to model
                    response = chat_session.send_message(
                        genai.protos.Content(
                            parts=[genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": tool_result}
                                )
                            )]
                        )
                    )
                except Exception as e:
                    # Send tool error event
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'success': False, 'error': str(e)})}\n\n"
                    
                    # Send error back to model
                    response = chat_session.send_message(
                        genai.protos.Content(
                            parts=[genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"error": str(e)}
                                )
                            )]
                        )
                    )
            else:
                # Text response, we are done
                break
        
        # Send final response
        yield f"data: {json.dumps({'type': 'response', 'content': response.text})}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.get("/download_ids")
async def download_ids():
    if not mcp_client:
        raise HTTPException(status_code=503, detail="MCP Client not initialized")
    
    try:
        # Call export_ids tool to get XML content
        result = await mcp_client.call_tool("export_ids", {})
        
        # Parse result
        content = result.get("content", [])
        if not content:
             raise HTTPException(status_code=404, detail="No content returned from tool")
             
        text_content = content[0].get("text")
        if not text_content:
             raise HTTPException(status_code=404, detail="No text content returned")
             
        import json
        try:
            tool_output = json.loads(text_content)
        except json.JSONDecodeError:
            tool_output = text_content
            
        if isinstance(tool_output, dict):
            xml_content = tool_output.get("xml")
        else:
            xml_content = str(tool_output)
            
        if not xml_content:
             raise HTTPException(status_code=404, detail="No XML content found in IDS")
             
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={"Content-Disposition": 'attachment; filename="requirements.ids"'}
        )
    except Exception as e:
        print(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def read_root():
    return FileResponse("web/static/index.html")
