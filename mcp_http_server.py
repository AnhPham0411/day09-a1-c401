from fastapi import FastAPI
from mcp_server import dispatch_tool, list_tools  # Import từ file extended
import uvicorn

app = FastAPI()

@app.get("/tools")
def get_tools():
    return list_tools()

@app.post("/tools/{tool_name}")
def call_tool(tool_name: str, tool_input: dict):
    return dispatch_tool(tool_name, tool_input)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)