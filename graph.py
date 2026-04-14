import os
import json
import operator
from datetime import datetime
from typing import TypedDict, Literal, Optional, Annotated

from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from mcp_server import dispatch_tool

# 1. State Definition
class AgentState(TypedDict):
    task: str
    supervisor_route: str
    route_reason: str
    final_answer: str
    mcp_tools_used: list
    history: Annotated[list, operator.add]
    latency_ms: Optional[int]
    run_id: str

# 2. LLM Initialization
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 3. Nodes
def supervisor_node(state: AgentState) -> dict:
    prompt = f"""You are a routing supervisor. Based on the user's task, route to the most appropriate agent.
Task: "{state['task']}"

Available routes:
- "IT_Agent": For IT support, SLA policies, technical tickets, access control, passwords, or system systems.
- "HR_Agent": For HR policy, leave policy, remote work, employee benefits, or internal company guidelines.
- "CS_Agent": For customer policies, refund policies, warranties, store credit, flash sales.
- "Out_of_Domain_Agent": ONLY for completely unrelated questions, general knowledge, chit-chat, or programming questions unrelated to internal docs.

Respond strictly in JSON format:
{{"route": "Agent_Name", "reason": "brief explanation"}}
"""
    response = llm.invoke([SystemMessage(content=prompt)])
    try:
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
        res_json = json.loads(content)
        route = res_json.get("route", "Out_of_Domain_Agent")
        reason = res_json.get("reason", "Parsed correctly")
    except Exception as e:
        route = "Out_of_Domain_Agent"
        reason = f"Fallback due to parse error: {e}"
        
    return {
        "supervisor_route": route, 
        "route_reason": reason, 
        "history": [f"[supervisor] selected {route}: {reason}"]
    }

def it_agent_node(state: AgentState) -> dict:
    tool_res = dispatch_tool("search_it_kb", {"query": state["task"], "top_k": 3})
    chunks = tool_res.get("chunks", [])
    context = "\n".join([f"[{c['score']:.2f}] {c['content']}" for c in chunks])
    
    prompt = f"""You are IT Support Agent at the company. Answer the user's question based strictly on the context below. Do not guess.
Context:
{context}

Question: {state['task']}
"""
    ans = llm.invoke([SystemMessage(content=prompt)]).content
    return {"final_answer": ans, "mcp_tools_used": ["search_it_kb"], "history": ["[IT_Agent] generated answer"]}

def hr_agent_node(state: AgentState) -> dict:
    tool_res = dispatch_tool("search_hr_kb", {"query": state["task"], "top_k": 3})
    chunks = tool_res.get("chunks", [])
    context = "\n".join([f"[{c['score']:.2f}] {c['content']}" for c in chunks])
    
    prompt = f"""You are HR Support Agent at the company. Answer the user's question based strictly on the context below. Do not guess.
Context:
{context}

Question: {state['task']}
"""
    ans = llm.invoke([SystemMessage(content=prompt)]).content
    return {"final_answer": ans, "mcp_tools_used": ["search_hr_kb"], "history": ["[HR_Agent] generated answer"]}

def cs_agent_node(state: AgentState) -> dict:
    tool_res = dispatch_tool("search_cs_kb", {"query": state["task"], "top_k": 3})
    chunks = tool_res.get("chunks", [])
    context = "\n".join([f"[{c['score']:.2f}] {c['content']}" for c in chunks])
    
    prompt = f"""You are Customer Policy Support Agent at the company. Answer the user's question based strictly on the context below. Do not guess.
Context:
{context}

Question: {state['task']}
"""
    ans = llm.invoke([SystemMessage(content=prompt)]).content
    return {"final_answer": ans, "mcp_tools_used": ["search_cs_kb"], "history": ["[CS_Agent] generated answer"]}

def ood_agent_node(state: AgentState) -> dict:
    prompt = f"""You are an internal assistant. The user asked an out-of-domain question.
Politely decline to answer and guide them to ask queries related to IT, HR, or Customer Policies.
Question: {state['task']}
"""
    ans = llm.invoke([SystemMessage(content=prompt)]).content
    return {"final_answer": ans, "mcp_tools_used": [], "history": ["[Out_of_Domain_Agent] rejected query politely"]}

# 4. Conditional edge
def route_decision(state: AgentState) -> str:
    allowed_routes = ["IT_Agent", "HR_Agent", "CS_Agent", "Out_of_Domain_Agent"]
    if state["supervisor_route"] in allowed_routes:
        return state["supervisor_route"]
    return "Out_of_Domain_Agent"

# 5. Build Graph
graph_builder = StateGraph(AgentState)
graph_builder.add_node("supervisor", supervisor_node)
graph_builder.add_node("IT_Agent", it_agent_node)
graph_builder.add_node("HR_Agent", hr_agent_node)
graph_builder.add_node("CS_Agent", cs_agent_node)
graph_builder.add_node("Out_of_Domain_Agent", ood_agent_node)

graph_builder.add_edge(START, "supervisor")
graph_builder.add_conditional_edges(
    "supervisor",
    route_decision,
    {
        "IT_Agent": "IT_Agent",
        "HR_Agent": "HR_Agent",
        "CS_Agent": "CS_Agent",
        "Out_of_Domain_Agent": "Out_of_Domain_Agent"
    }
)

graph_builder.add_edge("IT_Agent", END)
graph_builder.add_edge("HR_Agent", END)
graph_builder.add_edge("CS_Agent", END)
graph_builder.add_edge("Out_of_Domain_Agent", END)

app = graph_builder.compile()

def run_graph(task: str) -> dict:
    import time
    start = time.time()
    
    initial_state = {
        "task": task,
        "supervisor_route": "",
        "route_reason": "",
        "final_answer": "",
        "mcp_tools_used": [],
        "history": [],
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }
    
    result = app.invoke(initial_state)
    result["latency_ms"] = int((time.time() - start) * 1000)
    
    return result

if __name__ == "__main__":
    print("=========================================")
    print("Day 09 Lab - Multi-Agent System (LangGraph)")
    print("=========================================")
    
    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Xin nghỉ thai sản như nào vậy?",
        "Sản phẩm bị lỗi tôi muốn hoàn tiền trong kỳ Flash Sale",
        "Định lý Pytago là gì?"
    ]
    
    for q in test_queries:
        print(f"\n[QUERY]: {q}")
        res = run_graph(q)
        print(f" -> Route  : {res['supervisor_route']} ({res['route_reason']})")
        print(f" -> Tools  : {res.get('mcp_tools_used', [])}")
        print(f" -> Answer : {res['final_answer'][:150]}...")
        print(f" -> Latency: {res.get('latency_ms')} ms")
