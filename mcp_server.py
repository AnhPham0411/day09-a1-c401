import os
from typing import Any, Dict, List
from src.hybrid_retriever import HybridRetriever

# Khởi tạo singleton
hybrid_retriever = HybridRetriever()

TOOL_SCHEMAS = {
    "search_it_kb": {
        "name": "search_it_kb",
        "description": "T\u00ecm ki\u1ebfm Knowledge Base nghi\u1ec7p v\u1ee5 ph\u00f2ng IT (SLA, Access Control, FAQ, x\u1eed l\u00fd ticket, server).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "C\u00e2u h\u1ecfi c\u1ea7n t\u00ecm"},
                "top_k": {"type": "integer", "description": "S\u1ed1 k\u1ebft qu\u1ea3", "default": 3},
            },
            "required": ["query"],
        },
    },
    "search_hr_kb": {
        "name": "search_hr_kb",
        "description": "T\u00ecm ki\u1ebfm Knowledge Base nghi\u1ec7p v\u1ee5 ph\u00f2ng HR (Ch\u00ednh s\u00e1ch ngh\u1ec9 ph\u00e9p, quy \u0111\u1ecbnh, benefit).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "C\u00e2u h\u1ecfi c\u1ea7n t\u00ecm"},
                "top_k": {"type": "integer", "description": "S\u1ed1 k\u1ebft qu\u1ea3", "default": 3},
            },
            "required": ["query"],
        },
    },
    "search_cs_kb": {
        "name": "search_cs_kb",
        "description": "T\u00ecm ki\u1ebfm Knowledge Base nghi\u1ec7p v\u1ee5 ph\u00f2ng Ch\u00ednh S\u00e1ch (Refund policy, CS).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "C\u00e2u h\u1ecfi c\u1ea7n t\u00ecm"},
                "top_k": {"type": "integer", "description": "S\u1ed1 k\u1ebft qu\u1ea3", "default": 3},
            },
            "required": ["query"],
        },
    }
}

def tool_search_it_kb(query: str, top_k: int = 3) -> dict:
    try:
        results = hybrid_retriever.search(query, "IT", top_k=top_k)
        return {"chunks": results, "total_found": len(results)}
    except Exception as e:
        return {"error": str(e)}

def tool_search_hr_kb(query: str, top_k: int = 3) -> dict:
    try:
        results = hybrid_retriever.search(query, "HR", top_k=top_k)
        return {"chunks": results, "total_found": len(results)}
    except Exception as e:
        return {"error": str(e)}

def tool_search_cs_kb(query: str, top_k: int = 3) -> dict:
    try:
        results = hybrid_retriever.search(query, "CS", top_k=top_k)
        return {"chunks": results, "total_found": len(results)}
    except Exception as e:
        return {"error": str(e)}

TOOL_REGISTRY = {
    "search_it_kb": tool_search_it_kb,
    "search_hr_kb": tool_search_hr_kb,
    "search_cs_kb": tool_search_cs_kb,
}

def list_tools() -> list:
    return list(TOOL_SCHEMAS.values())

def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' kh\u00f4ng t\u1ed3n t\u1ea1i."}
    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        return tool_fn(**tool_input)
    except Exception as e:
        return {"error": f"Tool '{tool_name}' exception: {e}"}

if __name__ == "__main__":
    print(dispatch_tool("search_it_kb", {"query": "SLA P1", "top_k": 2}))
