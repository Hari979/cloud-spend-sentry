import streamlit as st
import uuid
import dotenv
from langchain_core.messages import HumanMessage

# Import your existing agent
from app.agent import app

# Load environment variables
dotenv.load_dotenv()

# --- PAGE CONFIG ---
st.set_page_config(page_title="CloudSpend Sentry", page_icon="🛡️")
st.title("🛡️ CloudSpend Sentry")
st.caption("Your AI FinOps Agent for AWS Cost Optimization")

# --- SESSION STATE ---
# 1. Generate a unique session ID for memory (persists for the browser session)
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# 2. Initialize chat history for the UI
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant",
         "content": "Hello! I am your AWS Sentry. I can check your costs and scan for waste. How can I help?"}
    ]

# --- DISPLAY CHAT HISTORY ---
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        st.chat_message("assistant").write(msg["content"])

# --- CHAT LOGIC ---
if user_input := st.chat_input("Ask me to check costs..."):
    # 1. Display user message immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    # 2. Run the Agent
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    inputs = {"messages": [HumanMessage(content=user_input)]}

    # Create a placeholder for the agent's response
    with st.chat_message("assistant"):
        with st.spinner("Analysing AWS infrastructure..."):

            final_response = ""

            # Stream the graph events
            try:
                for event in app.stream(inputs, config=config):
                    for node_name, state_update in event.items():
                        last_message = state_update['messages'][-1]

                        # If it's a tool output, we can show a status indicator
                        if node_name == "tools":
                            # Optional: Show what tool just ran (as a collapsible status)
                            tool_name = last_message.name
                            with st.status(f"🛠️ Ran tool: {tool_name}", expanded=False):
                                st.code(last_message.content)

                        # If it's the final agent response
                        if node_name == "agent":
                            final_response = last_message.content

                # Display the final text
                st.markdown(final_response)

                # Save to chat history so it stays on refresh
                st.session_state.messages.append({"role": "assistant", "content": final_response})

            except Exception as e:
                st.error(f"An error occurred: {e}")