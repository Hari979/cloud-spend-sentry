import uuid
import dotenv
import os

# 1. Load Environment Variables FIRST
# This must happen before importing 'app.agent', because 'app.agent'
# tries to initialize the LLM immediately upon import.
dotenv.load_dotenv()

# Verify key is loaded (Optional check to catch errors early)
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ Error: OPENAI_API_KEY not found. Check your .env file.")
    exit(1)

from langchain_core.messages import HumanMessage

# Import the compiled graph from our agent definition
# Now that env vars are loaded, this import will succeed.
from app.agent import app


def main():
    print("🚀 CloudSpend Sentry Initialized")
    print("--------------------------------")

    # 2. Define Session Configuration
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print(f"🆔 Session ID: {thread_id}")

    # 3. Define the Trigger
    user_input = "Check my AWS costs for the last week. If you see any spikes, look for waste."

    print(f"👤 User: {user_input}\n")

    # 4. Run the Agent
    inputs = {"messages": [HumanMessage(content=user_input)]}

    try:
        for event in app.stream(inputs, config=config):
            for node_name, state_update in event.items():
                print(f"\n--- Step: {node_name} ---")
                last_message = state_update['messages'][-1]

                if node_name == "agent":
                    print(f"🤖 Agent: {last_message.content}")
                    if last_message.tool_calls:
                        tool_names = [t['name'] for t in last_message.tool_calls]
                        print(f"🛠️  Action: Calling Tools -> {tool_names}")

                elif node_name == "tools":
                    print(f"💾 Tool Output: {last_message.content}")

    except Exception as e:
        print(f"\n❌ Runtime Error: {e}")

    print("\n--------------------------------")
    print("✅ Optimization Check Complete.")


if __name__ == "__main__":
    main()