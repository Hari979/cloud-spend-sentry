import os
import dotenv
from typing import TypedDict, Annotated, Literal

# 1. LOAD KEYS IMMEDIATELY
dotenv.load_dotenv()

# LangChain / LangGraph Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# 2. IMPORT MEMORY
try:
    from app.memory import get_checkpointer
except ImportError:
    # Fallback if memory.py isn't created yet
    from langgraph.checkpoint.memory import MemorySaver


    def get_checkpointer():
        return MemorySaver()

# 3. IMPORT TOOLS (Including the new Top Spenders tool)
from app.tools import (
    get_recent_cost_trends,
    scan_unused_ebs_volumes,
    scan_unassociated_ips,
    get_top_5_spending_services,
    scan_idle_instances,
    scan_old_snapshots,
    compare_monthly_costs,
    get_monthly_cost_report
)

# --- CONFIGURATION ---

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("❌ GOOGLE_API_KEY is missing. Please check your .env file.")

# Define the LLM (Using 1.5 Flash as confirmed working)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=api_key
)

# Define the tools list (Added new tool here)
tools = [
    get_recent_cost_trends,
    get_top_5_spending_services,
    scan_unused_ebs_volumes,
    scan_unassociated_ips,
    scan_idle_instances,
    scan_old_snapshots,
    compare_monthly_costs,
    get_monthly_cost_report
]

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools)


# --- 1. STATE MANAGEMENT ---
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# --- 2. NODE DEFINITIONS ---

def agent_node(state: AgentState):
    """The 'Reasoning' node."""
    messages = state["messages"]

    system_prompt = SystemMessage(content="""
    You are 'CloudSpend Sentry', an expert AWS FinOps and SRE Agent.

    YOUR GOAL:
    Analyze cloud costs, understand spending breakdown, and identify waste.

    YOUR PROCESS:
    1. TRENDS: Start by checking 'get_recent_cost_trends' to see if costs are rising.
    2. BREAKDOWN: Use 'get_top_5_spending_services' to see WHERE the money is going.
    3. WASTE: If you see high costs or spikes, PROACTIVELY use scanning tools:
       - 'scan_unused_ebs_volumes'
       - 'scan_unassociated_ips'
       - 'scan_idle_instances'
       - 'scan_old_snapshots'
       - 'compare_monthly_costs'
       - 'get_monthly_cost_report'
    4. REPORT: Calculate potential savings from waste and summarize the top spenders.

    BEHAVIOR:
    - Be concise and professional.
    - Use the tool outputs for data. Don't guess.
    """)

    # Invoke the LLM
    response = llm_with_tools.invoke([system_prompt] + messages)

    # --- 🧹 CLEAN UP GEMINI RESPONSE ---
    # Gemini sometimes returns a mixed list [{'text': '...'}, {'extras': ...}]
    if isinstance(response.content, list):
        clean_text = ""
        for part in response.content:
            if isinstance(part, dict) and "text" in part:
                clean_text += part["text"]
            elif isinstance(part, str):
                clean_text += part
        response.content = clean_text
    # -----------------------------------

    return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", END]:
    """Checks if the agent wants to run a tool."""
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "tools"
    return END


# --- 3. GRAPH CONSTRUCTION ---
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

# --- 4. MEMORY & COMPILATION ---
checkpointer = get_checkpointer()

app = workflow.compile(checkpointer=checkpointer)