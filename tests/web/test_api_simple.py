import os
from fastapi.testclient import TestClient
from web.app import app
import pytest
import asyncio
from unittest.mock import patch, MagicMock

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "IDS MCP Agent" in response.text

@patch("web.app.mcp_client")
@patch("google.generativeai.GenerativeModel")
def test_chat_endpoint(mock_model, mock_mcp_client):
    # Mock MCP Client
    # We need to make sure the return value is awaitable
    async def mock_list_tools():
        return [
            {
                "name": "create_ids",
                "description": "Create a new IDS",
                "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}}
            }
        ]
    mock_mcp_client.list_tools.side_effect = mock_list_tools
    
    # Mock Gemini Model
    mock_chat = MagicMock()
    mock_model.return_value.start_chat.return_value = mock_chat
    
    # Mock response with no function call
    mock_response = MagicMock()
    mock_response.parts = []
    mock_response.text = "Hello! I can help you."
    mock_chat.send_message.return_value = mock_response
    
    # We need to mock the global mcp_client in app.py
    # Since we are using TestClient, the startup event runs.
    # We should probably mock the MCPClient class in app.py to avoid spawning subprocess
    
    with patch("web.app.MCPClient") as MockMCPClient:
        instance = MockMCPClient.return_value
        instance.start = MagicMock(side_effect=lambda: asyncio.sleep(0)) # Async mock
        instance.stop = MagicMock(side_effect=lambda: asyncio.sleep(0)) # Async mock
        instance.list_tools.side_effect = mock_list_tools
        
        # We need to trigger startup to set the global mcp_client
        with TestClient(app) as tc:
            response = tc.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}]})
            assert response.status_code == 200
            assert response.json()["response"] == "Hello! I can help you."

if __name__ == "__main__":
    # Manually run if executed as script
    try:
        test_read_root()
        print("Root endpoint test passed.")
        # test_chat_endpoint() # This is harder to run manually without pytest infrastructure
    except Exception as e:
        print(f"Test failed: {e}")
