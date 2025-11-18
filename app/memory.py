import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# This file will be created automatically in your root directory
DB_PATH = "agent_checkpoints.sqlite"


def get_checkpointer():
    """
    Creates and returns a LangGraph Checkpointer using SQLite.

    Why SQLite?
    It provides persistent storage for the agent's state (memory).
    This means if the script crashes or restarts, the agent picks up
    exactly where it left off using the thread_id.
    """
    # 1. Establish a connection to the local database file
    # check_same_thread=False is needed because LangGraph might run async
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    # 2. Initialize the LangGraph SqliteSaver
    # This handles the heavy lifting of serializing the state
    checkpointer = SqliteSaver(conn)

    return checkpointer