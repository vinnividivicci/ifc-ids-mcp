
from ids_mcp_server.server import mcp
import json

print("Tools registered:", mcp._tools.keys())
for name, tool in mcp._tools.items():
    print(f"\nTool: {name}")
    print(f"Description: {tool.description}")
    print(f"Parameters: {tool.parameters}")
