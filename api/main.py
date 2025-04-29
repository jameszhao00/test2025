import os
import uuid  # Used for generating unique session IDs
import random  # Used for simulating varied LLM responses
from typing import List, Literal, Dict, Optional, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from collections import defaultdict

# --- Pydantic Models for Chat ---

class ChatMessage(BaseModel):
    """Represents a single message in the chat."""
    id: int  # Monotonically increasing ID within a session
    session_id: str # The session this message belongs to
    role: Literal['user', 'assistant']  # Who sent the message
    content: str  # The text content of the message

class ChatRequest(BaseModel):
    """The request body for sending a new message to a chat session."""
    session_id: Optional[str] = Field(None, description="The ID of the chat session. If null, a new session is created.")
    content: str = Field(..., description="The text content of the user's message.")

class ChatResponse(BaseModel):
    """The response body after sending a message."""
    session_id: str # The ID of the session (useful if a new one was created)
    reply: ChatMessage # The assistant's reply message

class FetchMessagesResponse(BaseModel):
    """The response body for fetching messages from a session."""
    messages: List[ChatMessage]

# --- FastAPI App Setup ---

app = FastAPI(title="Session-Based Chatty LLM API")

# --- In-Memory Session Storage ---
# Stores chat history and the next message ID for each session
# Structure: { session_id: { "messages": [ChatMessage, ...], "next_message_id": int } }
chat_sessions: Dict[str, Dict[str, Any]] = {}

# --- Simulated LLM Responses ---
canned_responses = [
    "That's truly fascinating!",
    "Interesting point. Could you expand on that?",
    "I understand. What are your thoughts on the implications?",
    "Let me process that for a moment...",
    "Okay, I see. How does that relate to our previous topic?",
    "That's a unique perspective!",
    "Hmm, I'll need to consider that.",
]

# --- Helper Functions ---

def get_or_create_session(session_id: Optional[str]) -> Dict[str, Any]:
    """Retrieves an existing session or creates a new one."""
    global chat_sessions
    if session_id and session_id in chat_sessions:
        return chat_sessions[session_id]
    elif session_id: # session_id provided but not found
         raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    else: # No session_id provided, create a new one
        new_session_id = str(uuid.uuid4())
        chat_sessions[new_session_id] = {"messages": [], "next_message_id": 1}
        print(f"Created new session: {new_session_id}") # For debugging
        return chat_sessions[new_session_id]

def add_message_to_session(session_data: Dict[str, Any], session_id: str, role: Literal['user', 'assistant'], content: str) -> ChatMessage:
    """Adds a message to the session history with the next available ID."""
    message_id = session_data["next_message_id"]
    message = ChatMessage(
        id=message_id,
        session_id=session_id,
        role=role,
        content=content
    )
    session_data["messages"].append(message)
    session_data["next_message_id"] += 1
    return message

def simulate_llm_response(user_content: str) -> str:
    """Generates a simulated LLM response based on user input."""
    if "hello" in user_content.lower():
        return "Hello there! How can I assist you today?"
    elif "bye" in user_content.lower():
        return "Goodbye! Feel free to return anytime."
    # Add more sophisticated logic here if needed
    return random.choice(canned_responses)

# --- API Endpoints ---

@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """
    Handles a new user message for a chat session (existing or new).
    Adds the user message and a simulated assistant reply to the session history.
    Returns the session ID and the assistant's reply message.
    """
    try:
        session_data = get_or_create_session(request.session_id)
        # Determine the actual session ID (could be newly generated)
        current_session_id = request.session_id or next(iter(chat_sessions.keys() - (set(chat_sessions.keys()) - set([k for k, v in chat_sessions.items() if v == session_data]))), None)
        if not current_session_id:
             # This case should ideally not happen with get_or_create_session logic, but as a safeguard:
             raise HTTPException(status_code=500, detail="Could not determine session ID")

        # 1. Add user message to history
        user_message = add_message_to_session(session_data, current_session_id, 'user', request.content)

        # 2. Simulate LLM response
        assistant_content = simulate_llm_response(user_message.content)

        # 3. Add assistant reply to history
        assistant_reply = add_message_to_session(session_data, current_session_id, 'assistant', assistant_content)

        print(f"Session {current_session_id} history length: {len(session_data['messages'])}") # For debugging

        return ChatResponse(session_id=current_session_id, reply=assistant_reply)

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Handle unexpected errors
        print(f"Error handling chat: {e}") # Log the error
        raise HTTPException(status_code=500, detail="An internal server error occurred.")


@app.get("/api/chat/{session_id}/messages", response_model=FetchMessagesResponse)
async def get_session_messages(
    session_id: str,
    since: Optional[int] = Query(0, description="Fetch messages with an ID greater than this value. Defaults to 0 (fetch all).")
):
    """
    Fetches messages for a given session ID, optionally filtering
    for messages created after a specific message ID (`since`).
    """
    global chat_sessions
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session_data = chat_sessions[session_id]
    messages = session_data.get("messages", [])

    # Filter messages based on the 'since' parameter
    filtered_messages = [msg for msg in messages if msg.id > since]

    return FetchMessagesResponse(messages=filtered_messages)


@app.get("/api/hello")
async def hello():
    """A simple endpoint to check if the API is running."""
    return {"message": "Hello from FastAPI Session Chat API!"}


# --- Static File Serving (for Vue App) ---
# This part remains the same to serve the frontend

# Determine the path to the static files directory relative to this script
static_files_path = os.path.join(os.path.dirname(__file__), "..", "web", "dist")

# Mount the 'assets' directory specifically
if os.path.exists(os.path.join(static_files_path, "assets")):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(static_files_path, "assets")),
        name="assets",
    )
else:
    print(f"Warning: Assets directory not found at {os.path.join(static_files_path, 'assets')}")


@app.get("/{full_path:path}")
async def serve_vue_app(full_path: str):
    """Serves the Vue app for any path not matching other API routes."""
    index_path = os.path.join(static_files_path, "index.html")
    # Check if the requested path corresponds to a file in the static directory
    potential_file_path = os.path.join(static_files_path, full_path)

    # Prevent serving API routes as files
    if full_path.startswith("api/"):
         raise HTTPException(status_code=404, detail="Not Found")

    if not os.path.isfile(potential_file_path) or full_path == "index.html":
        # If it's not a file (likely a Vue route) or is index.html itself, serve index.html
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            # Only raise if index.html itself is missing
             if not os.path.exists(index_path):
                  print(f"Error: index.html not found at {index_path}")
                  raise HTTPException(status_code=404, detail="index.html not found")
             else: # Should not happen based on above logic, but safety first
                  raise HTTPException(status_code=404, detail="Not Found")

    else:
        # If it IS a file (like main.js, style.css), serve it directly
        return FileResponse(potential_file_path)


@app.get("/")
async def serve_index():
    """Serves the index.html for the root path."""
    index_path = os.path.join(static_files_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    print(f"Error: index.html not found at {index_path}")
    raise HTTPException(status_code=404, detail="index.html not found")

# --- Main Execution Guard (Optional, for local testing) ---
# if __name__ == "__main__":
#     import uvicorn
#     # It's recommended to run with reload during development:
#     # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
#     uvicorn.run(app, host="0.0.0.0", port=8000)
