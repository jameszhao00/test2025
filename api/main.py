import os
import uuid
from typing import List, Dict, Optional, Any, Literal  # Keep Literal for roles/types

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# --- Import Pydantic Models from models.py ---
from models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FetchMessagesResponse,
    TextContent,
)

# --- Import Gemini Client ---
from gemini_client import generate_gemini_chat_response

# --- FastAPI App Setup ---
app = FastAPI(title="Session-Based Chatty LLM API (No IDs) - Gemini Powered")

# --- In-Memory Session Storage ---
# Stores session data, where each session has a list of 'messages' (as dicts)
chat_sessions: Dict[str, Dict[str, Any]] = {}

# --- Helper Functions ---


def get_or_create_session(session_id: Optional[str]) -> tuple[str, Dict[str, Any]]:
    """Retrieves an existing session or creates a new one."""
    global chat_sessions
    if session_id and session_id in chat_sessions:
        print(f"Retrieving existing session: {session_id}")
        return session_id, chat_sessions[session_id]
    elif session_id:
        # If session_id is provided but not found, it's an error
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    else:
        # Create a new session if no ID was provided
        new_session_id = str(uuid.uuid4())
        chat_sessions[new_session_id] = {"messages": []}
        print(f"Created new session: {new_session_id}")
        return new_session_id, chat_sessions[new_session_id]


def add_message_to_session(
    session_data: Dict[str, Any],
    session_id: str,
    role: Literal["user", "assistant"],
    response_type: Literal["text", "markdown", "form", "sxs"],
    content_dict: Dict[
        str, Any
    ],  # Expects {'text_content': {...}}, {'form_content': {...}}, etc.
) -> ChatMessage:
    """
    Creates a ChatMessage object, validates it, adds its dict representation
    to the session history, and returns the object.
    """
    try:
        # Create and validate the message object using the imported Pydantic model
        message = ChatMessage(
            session_id=session_id,
            role=role,
            response_type=response_type,
            **content_dict,  # Unpack the specific content field (e.g., text_content=...)
        )
        # Store the message as a dictionary in the session history
        # Use model_dump for serialization compatible with Pydantic v2
        session_data["messages"].append(message.model_dump(mode="json"))
        print(
            f"Added {role} message ({response_type}) to session {session_id}. Total messages: {len(session_data['messages'])}"
        )
        # Return the Pydantic model instance for use in the API response
        return message
    except Exception as e:
        # Catch potential validation errors or other issues during message creation
        print(f"Error creating or adding ChatMessage: {e}")
        print(f"Session Data (keys): {session_data.keys()}")
        print(f"Content Dict trying to add: {content_dict}")
        # Raise an internal server error if message creation fails
        raise HTTPException(
            status_code=500, detail=f"Internal error creating chat message: {e}"
        )


# --- API Endpoints ---


@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """
    Handles chat requests:
    1. Gets/Creates session.
    2. Adds user message to history.
    3. Calls Gemini client to generate a response based on history and requested type.
    4. Adds assistant message to history.
    5. Returns session ID and assistant reply.
    """
    try:
        current_session_id, session_data = get_or_create_session(request.session_id)
        history = session_data.get("messages", [])  # History is list of dicts

        # --- Determine Requested Response Type (Round-Robin Example) ---
        # The caller (this endpoint) decides the type for the next response.
        # Simple round-robin: text -> markdown -> form -> sxs -> text ...
        response_types_cycle: List[Literal["text", "markdown", "form", "sxs"]] = [
            "text",
            "markdown",
            "form",
            "sxs",
        ]
        # Get the type of the *last assistant message* to determine the next type
        last_assistant_type = "text"  # Default if no previous assistant message
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant_type = msg.get("response_type", "text")
                break
        try:
            current_index = response_types_cycle.index(last_assistant_type)
            next_type_index = (current_index + 1) % len(response_types_cycle)
            requested_type = response_types_cycle[next_type_index]
        except ValueError:
            requested_type = "text"  # Fallback if last type wasn't in cycle
        print(f"Requesting response type: {requested_type}")
        # --- End Response Type Determination ---

        # 1. Add user message (always 'text' type for user input)
        user_content_dict = {"text_content": TextContent(text=request.content)}
        add_message_to_session(
            session_data, current_session_id, "user", "text", user_content_dict
        )
        # Refresh history *after* adding the user message
        history = session_data.get("messages", [])

        # 2. Generate response using Gemini Client
        # Pass the history (list of dicts), new user content, and requested type
        actual_response_type, assistant_content_dict = (
            await generate_gemini_chat_response(
                history, request.content, requested_type
            )
        )
        # assistant_content_dict will be like {'text_content': {...}} or {'form_content': {...}} etc.

        # 3. Add assistant reply to history and get the message object for the response
        assistant_reply = add_message_to_session(
            session_data,
            current_session_id,
            "assistant",
            actual_response_type,  # Use the type returned by Gemini client
            assistant_content_dict,  # Pass the structured content dict
        )

        # 4. Return the response containing the session ID and the assistant's reply message object
        return ChatResponse(session_id=current_session_id, reply=assistant_reply)

    except HTTPException as e:
        # Re-raise known HTTP exceptions (like 404 Session Not Found)
        raise e
    except Exception as e:
        import traceback

        print(f"Error handling chat: {e}\n{traceback.format_exc()}")
        # Return a generic 500 error for unexpected issues
        raise HTTPException(
            status_code=500, detail=f"An internal server error occurred: {e}"
        )


@app.get("/api/chat/{session_id}/messages", response_model=FetchMessagesResponse)
async def get_session_messages(session_id: str):
    """Fetches ALL messages for a given session ID."""
    global chat_sessions
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session_data = chat_sessions[session_id]
    # Messages are stored as dicts, convert back to ChatMessage models for the response
    try:
        # Validate dicts against the ChatMessage model during list comprehension
        messages_as_models = [
            ChatMessage(**msg_dict) for msg_dict in session_data.get("messages", [])
        ]
    except Exception as e:
        print(f"Error parsing stored messages for session {session_id}: {e}")
        # If stored data is invalid, raise an error
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving message history for session {session_id}.",
        )

    print(f"Fetching all {len(messages_as_models)} messages for session {session_id}")
    return FetchMessagesResponse(messages=messages_as_models)


@app.get("/api/hello")
async def hello():
    """Simple endpoint to check if the API is running."""
    return {"message": "Hello from FastAPI Session Chat API (No IDs) - Gemini Powered!"}


# --- Static File Serving ---
# Assumes the built Vue app is in ../web/dist relative to this file
static_files_path = os.path.join(os.path.dirname(__file__), "..", "web", "dist")

# Mount the assets directory if it exists
assets_path = os.path.join(static_files_path, "assets")
if os.path.exists(assets_path) and os.path.isdir(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    print(f"Mounted /assets directory from: {assets_path}")
else:
    print(f"Warning: Assets directory not found or not a directory at {assets_path}")


# Serve index.html for the root path
@app.get("/")
async def serve_index():
    index_path = os.path.join(static_files_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    else:
        print(f"Error: index.html not found at {index_path}")
        raise HTTPException(status_code=404, detail="index.html not found")


# Serve other static files or index.html for SPA routing
@app.get("/{full_path:path}")
async def serve_vue_app(full_path: str):
    # Prevent serving API routes or paths with '..'
    if full_path.startswith("api/") or ".." in full_path:
        raise HTTPException(status_code=404, detail="Not Found")

    potential_file_path = os.path.join(static_files_path, full_path)
    index_path = os.path.join(static_files_path, "index.html")

    # Serve the specific file if it exists and is not a directory
    if os.path.isfile(potential_file_path):
        return FileResponse(potential_file_path)
    # Otherwise, serve index.html for SPA routing (if it exists)
    elif os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    # If index.html doesn't exist either, return 404
    else:
        print(
            f"Error: index.html not found at {index_path} while trying to serve path {full_path}"
        )
        raise HTTPException(status_code=404, detail="Not Found")


# --- Run Instruction (for local development) ---
# Use: uvicorn api.main:app --reload --port 8000
