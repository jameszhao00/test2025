import os
import uuid
import json # Import json module
from typing import List, Dict, Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.genai import types
from pydantic import ValidationError # Import for handling schema validation errors

# --- Import Pydantic Models from models.py ---
from models import (
    TextAndWorkflowState,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FetchMessagesResponse,
    TextContent, # Needed for constructing response
)
import prompts

# --- Import Stateless Gemini Client Function ---
# Assuming gemini_client.py is in the same directory
from gemini_client import generate_gemini_response_stateless # Import the STATELESS function

# --- FastAPI App Setup ---
app = FastAPI(title="Session-Based Chatty LLM API (Stateless) - Gemini Powered")

# --- In-Memory Session Storage (Stores History Lists) ---
# Stores List[types.Content] for each session_id
chat_sessions: Dict[str, List[types.Content]] = {}

# --- Helper Function to Convert TextAndWorkflowState to types.Content ---
def text_workflow_to_content(state: TextAndWorkflowState) -> types.Content:
    """Converts a TextAndWorkflowState object to a types.Content object for history."""
    # Gemini expects the JSON representation as a string within a Part
    json_string = state.model_dump_json() # Use model_dump_json for Pydantic v2+
    return types.Content(role="model", parts=[types.Part.from_text(text=json_string)])

# --- Helper Function to Convert types.Content back to ChatMessage ---
def content_to_chat_message(content: types.Content, session_id: str) -> Optional[ChatMessage]:
    """Converts a types.Content object back to a ChatMessage API model."""
    message_role: Literal['user', 'assistant'] = "assistant" if content.role == "model" else "user"
    msg_data = {
        "session_id": session_id,
        "role": message_role,
        "response_type": "text", # Default
        "textContent": None,
        "textAndWorkflowStateContent": None,
    }
    combined_text = ""

    if not content.parts:
        print(f"Warning: Content object has no parts. Role: {content.role}")
        return None # Cannot process message with no parts

    # Combine text from all parts first (useful for user messages and fallback)
    for part in content.parts:
        try:
            combined_text += getattr(part, 'text', '')
        except Exception as e:
            print(f"Warning: Could not get text from part: {e}")

    if not combined_text:
        print(f"Warning: No text content found in parts for role {content.role}")
        # Allow empty messages? Or skip? Let's skip for now.
        # If empty messages are needed, adjust logic here.
        return None

    if message_role == 'assistant':
        # ASSUME the first part contains the JSON structure for TextAndWorkflowState
        first_part_text = getattr(content.parts[0], 'text', '')
        if first_part_text:
            try:
                # Attempt to parse the first part's text as JSON
                parsed_json = json.loads(first_part_text)
                # Validate and create the TextAndWorkflowState model
                validated_content = TextAndWorkflowState(**parsed_json)
                msg_data["response_type"] = "text_and_workflow_state"
                msg_data["textAndWorkflowStateContent"] = validated_content
                print("DEBUG: Assistant message successfully parsed as TextAndWorkflowState.")
            except (json.JSONDecodeError, ValidationError, TypeError) as parse_error:
                print(f"Warning: Assistant message - Failed to parse/validate first part as TextAndWorkflowState: {parse_error}. Falling back to text.")
                # Fallback: Use the combined text from all parts
                msg_data["response_type"] = "text"
                msg_data["textContent"] = TextContent(text=combined_text)
            except Exception as e:
                 print(f"Error processing assistant message content: {e}. Falling back to text.")
                 msg_data["response_type"] = "text"
                 msg_data["textContent"] = TextContent(text=combined_text)
        else:
             # Assistant message with no text in the first part - treat as text using combined
             print("Warning: Assistant message - First part has no text. Treating as plain text.")
             msg_data["response_type"] = "text"
             msg_data["textContent"] = TextContent(text=combined_text)
    else: # User message
        msg_data["response_type"] = "text"
        msg_data["textContent"] = TextContent(text=combined_text)
        print("DEBUG: User message processed as TextContent.")

    try:
        # Create the final ChatMessage model
        msg = ChatMessage(**msg_data)
        return msg
    except Exception as e:
        print(f"Error creating final ChatMessage model: {e} - Data: {msg_data}")
        return None

# --- API Endpoints ---

@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """
    Handles chat requests using the stateless Gemini client.
    Manages history in memory.
    ASSUMES the response from Gemini will be TextAndWorkflowState.
    """
    session_id = request.session_id
    user_content_text = request.content
    history: List[types.Content] = []

    # 1. Get or Create Chat History
    if session_id and session_id in chat_sessions:
        history = chat_sessions[session_id]
        print(f"Using existing chat history for session: {session_id} (Length: {len(history)})")
    else:
        # Start a new chat history
        if not session_id:
            session_id = str(uuid.uuid4()) # Generate new ID only if none provided
        print(f"Started new chat session: {session_id}")
        chat_sessions[session_id] = history # Store the empty list

    # Call the stateless function, passing system prompt, history, and new message
    response_content_model: Optional[TextAndWorkflowState] = (
        await generate_gemini_response_stateless(
            system_instructions=prompts.ML_AGENT_INSTRUCTIONS,
            history=history, # Pass the current history list
            latest_user_content=user_content_text
        )
    )
    if not response_content_model:
        # Handle cases where Gemini client returned None (e.g., parsing error)
        raise HTTPException(status_code=500, detail="Failed to get valid response from Gemini model.")

    history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_content_text)]))
    history.append(text_workflow_to_content(response_content_model))

    # Store the updated history back (important!)
    chat_sessions[session_id] = history
    print(f"Updated history for session {session_id}. New length: {len(history)}")

    # 4. Construct the API response object
    assistant_reply_chatmessage = ChatMessage(
        session_id=session_id,
        role="assistant",
        response_type='text_and_workflow_state', # Hardcoded based on assumption
        text_and_workflow_state_content=response_content_model,
        textContent=None # Ensure other content types are None
    )

    return ChatResponse(session_id=session_id, reply=assistant_reply_chatmessage)


@app.get("/api/chat/{session_id}/messages", response_model=FetchMessagesResponse)
async def get_session_messages(session_id: str):
    """
    Fetches message history stored in the session dictionary.
    Converts stored types.Content objects back to ChatMessage API models.
    """
    global chat_sessions
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Retrieve the history list (List[types.Content])
    history_content_list = chat_sessions.get(session_id, [])
    messages_as_api_models: List[ChatMessage] = []

    # Convert each stored Content object back to the ChatMessage format for the API
    for i, content_item in enumerate(history_content_list):
        chat_msg = content_to_chat_message(content_item, session_id)
        if chat_msg:
            messages_as_api_models.append(chat_msg)
            print(f"DEBUG: Converted history item {i} to ChatMessage (Type: {chat_msg.response_type})")
        else:
             print(f"DEBUG: Skipping history item {i} as conversion failed or item was empty.")


    print(f"Finished processing history. Returning {len(messages_as_api_models)} messages for session {session_id}.")
    return FetchMessagesResponse(messages=messages_as_api_models)


@app.get("/api/hello")
async def hello():
    """Simple endpoint to check if the API is running."""
    return {"message": "Hello from FastAPI Session Chat API (Stateless) - Gemini Powered!"}

static_files_path = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
assets_path = os.path.join(static_files_path, "assets")
if os.path.exists(assets_path) and os.path.isdir(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    print(f"Mounted /assets directory from: {assets_path}")
else:
    print(f"Warning: Assets directory not found or not a directory at {assets_path}")

@app.get("/")
async def serve_index():
    index_path = os.path.join(static_files_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    else:
        print(f"Error: index.html not found at {index_path}")
        raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/{full_path:path}")
async def serve_vue_app(full_path: str):
    # Basic security check
    if full_path.startswith("api/") or ".." in full_path:
        raise HTTPException(status_code=404, detail="Not Found")

    potential_file_path = os.path.normpath(os.path.join(static_files_path, full_path))
    index_path = os.path.join(static_files_path, "index.html")

    # Prevent path traversal
    if not potential_file_path.startswith(os.path.normpath(static_files_path)):
         raise HTTPException(status_code=404, detail="Not Found")

    if os.path.isfile(potential_file_path):
        # Determine mime type (optional but good practice)
        # import mimetypes
        # mime_type, _ = mimetypes.guess_type(potential_file_path)
        return FileResponse(potential_file_path) #, media_type=mime_type or 'application/octet-stream')
    elif os.path.exists(index_path):
         # Serve index.html for SPA routing
        return FileResponse(index_path, media_type="text/html")
    else:
        print(f"Error: File or index.html not found for path {full_path}")
        raise HTTPException(status_code=404, detail="Not Found")