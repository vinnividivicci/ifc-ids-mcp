import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

class MCPClient:
    def __init__(self, server_command: List[str], env: Optional[Dict[str, str]] = None):
        self.server_command = server_command
        self.env = env or os.environ.copy()
        self.process = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}

    async def start(self):
        """Start the MCP server subprocess."""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env
        )
        # Start reading stdout in background
        asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())
        
        # Initialize connection
        await self._initialize()

    async def stop(self):
        """Stop the MCP server subprocess."""
        if self.process:
            self.process.terminate()
            await self.process.wait()

    async def _read_stdout(self):
        """Read JSON-RPC messages from server stdout."""
        while True:
            if self.process.stdout.at_eof():
                break
            
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                
                message = json.loads(line.decode())
                await self._handle_message(message)
            except Exception as e:
                print(f"Error reading from server: {e}", file=sys.stderr)

    async def _read_stderr(self):
        """Read logs from server stderr."""
        while True:
            if self.process.stderr.at_eof():
                break
            
            line = await self.process.stderr.readline()
            if not line:
                break
            print(f"[MCP Server] {line.decode().strip()}", file=sys.stderr)

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming JSON-RPC message."""
        if "id" in message and message["id"] in self.pending_requests:
            future = self.pending_requests.pop(message["id"])
            if "error" in message:
                future.set_exception(Exception(message["error"]["message"]))
            else:
                future.set_result(message.get("result"))

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send JSON-RPC request."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        future = asyncio.Future()
        self.pending_requests[self.request_id] = future
        
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        await self.process.stdin.drain()
        
        return await future

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Send JSON-RPC notification."""
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        await self.process.stdin.drain()

    async def _initialize(self):
        """Initialize MCP connection."""
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ids-mcp-web-client", "version": "0.1.0"}
        })
        await self._send_notification("notifications/initialized")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        response = await self._send_request("tools/list")
        return response.get("tools", [])

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool."""
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return response

@asynccontextmanager
async def mcp_client_lifespan(command: List[str], env: Optional[Dict[str, str]] = None):
    client = MCPClient(command, env)
    await client.start()
    try:
        yield client
    finally:
        await client.stop()
