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

# 2. IMPORT MEMORY (SQLITE)
# We use the persistent DB we created in app/memory.py
# If you haven't created app/memory.py yet, swap this import to:
# from langgraph.checkpoint.memory import MemorySaver
try:
    from app.memory import get_checkpointer
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver


    def get_checkpointer():
        return MemorySaver()

# Import your custom tools
from app.tools import (
    get_recent_cost_trends,
    scan_unused_ebs_volumes,
    scan_unassociated_ips
)

# --- CONFIGURATION ---

# Get the key explicitly
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("❌ GOOGLE_API_KEY is missing. Please check your .env file.")

# Define the LLM
# NOTE: We use 'gemini-1.5-flash' as it is the current standard stable model.
# If this fails, try 'gemini-pro'.
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=api_key
)

# Define the tools list
tools = [get_recent_cost_trends, scan_unused_ebs_volumes, scan_unassociated_ips]

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
    Analyze cloud costs and identify waste to save the user money.

    YOUR PROCESS:
    1. Always start by checking recent cost trends using 'get_recent_cost_trends'.
    2. Analyze the data. Is there a spike?
    3. If costs look high or suspicious, PROACTIVELY use scanning tools:
       - 'scan_unused_ebs_volumes'
       - 'scan_unassociated_ips'
    4. If you find waste, calculate the total potential savings.
    5. Summarize your findings clearly.

    BEHAVIOR:
    - Be concise and professional.
    - Use the tool outputs for data.
    """)

    # Invoke the LLM
    response = llm_with_tools.invoke([system_prompt] + messages)

    # --- 🧹 CLEAN UP GEMINI RESPONSE (The Fix) ---
    # Gemini sometimes returns a mixed list [{'text': '...'}, {'extras': ...}]
    # We scrub this so only the clean text remains.
    if isinstance(response.content, list):
        clean_text = ""
        for part in response.content:
            # Check if the part is a dictionary and has a 'text' key
            if isinstance(part, dict) and "text" in part:
                clean_text += part["text"]
            # If it's just a string (rare but possible), append it
            elif isinstance(part, str):
                clean_text += part
        response.content = clean_text
    # ---------------------------------------------

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
# Use SQLite for persistence (Requirement for Capstone)
checkpointer = get_checkpointer()

app = workflow.compile(checkpointer=checkpointer)