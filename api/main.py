import os
import uuid
# import random # No longer needed for simulated responses
from typing import List, Literal, Dict, Optional, Any, Union # Keep Union for helper property type hints

from fastapi import FastAPI, HTTPException # Query removed
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator, root_validator

# --- Import Gemini Client ---
from gemini_client import generate_gemini_chat_response

# --- Pydantic Models ---

class TextContent(BaseModel):
    text: str

class MarkdownContent(BaseModel):
    markdown: str

# --- Form Field Definitions ---
class BaseField(BaseModel):
    label: str
    field_id: str

class TextField(BaseField):
    type: Literal['text'] = 'text'
    placeholder: Optional[str] = None
    initial_value: Optional[str] = None

class DropdownField(BaseField):
    type: Literal['dropdown'] = 'dropdown'
    options: List[str]
    default_option: Optional[str] = None

    @validator('default_option')
    def check_default(cls, v, values):
        if v is not None and 'options' in values and v not in values['options']:
            raise ValueError('default_option must be one of the available options')
        return v

# --- NEW: Form Field Wrapper ---
# This wrapper replaces the Union/Annotated type for FormField
# to potentially improve OpenAPI generator compatibility.
class FormFieldWrapper(BaseModel):
    text_field: Optional[TextField] = Field(default=None, description="Contains data if the field is a text input.")
    dropdown_field: Optional[DropdownField] = Field(default=None, description="Contains data if the field is a dropdown.")

    @root_validator(pre=False, skip_on_failure=True)
    def check_exactly_one_field(cls, values):
        """Ensures that exactly one field type (text_field or dropdown_field) is populated."""
        populated = [k for k, v in values.items() if v is not None]
        if len(populated) != 1:
            raise ValueError(f"Exactly one field type (text_field or dropdown_field) must be provided per FormFieldWrapper. Found: {populated}")
        return values

    # --- Optional Helper Properties (Not directly part of the schema, but useful internally) ---
    # These properties help access common attributes without checking the type everywhere in Python code.
    # Note: These might not be reflected in the OpenAPI schema depending on the generator.

    @property
    def field(self) -> Union[TextField, DropdownField]:
        """Returns the actual populated field object (TextField or DropdownField)."""
        if self.text_field:
            return self.text_field
        elif self.dropdown_field:
            return self.dropdown_field
        else:
            # This case should be prevented by the root_validator
            raise ValueError("FormFieldWrapper is unexpectedly empty")

    @property
    def field_id(self) -> str:
        """Returns the field_id of the populated field."""
        return self.field.field_id

    @property
    def type(self) -> Literal['text', 'dropdown']:
        """Returns the type ('text' or 'dropdown') of the populated field."""
        # Access the 'type' attribute which exists on both TextField and DropdownField
        return self.field.type

    @property
    def label(self) -> str:
         """Returns the label of the populated field."""
         return self.field.label

# --- Form Content Definition (Updated) ---
class FormContent(BaseModel):
    title: str
    # Use a list of the wrapper objects instead of the direct Union
    fields: List[FormFieldWrapper] = Field(description="A list of fields in the form, each wrapped to specify its type.")
    submit_button_text: str = "Submit"

# --- SxS Definitions (Unchanged) ---
class SxSRow(BaseModel):
    key: str
    label: str
    value_model_a: str
    value_model_b: str

class SxSContent(BaseModel):
    title: str
    model_a_label: str = "Model A"
    model_b_label: str = "Model B"
    rows: List[SxSRow]

# --- Chat Message Model (No ID) ---
# This model remains largely the same, using Optional fields for different content types.
class ChatMessage(BaseModel):
    """ Represents a single message in the chat (without a server-side ID). """
    session_id: str
    role: Literal['user', 'assistant']
    response_type: Literal['text', 'markdown', 'form', 'sxs'] # Discriminator for content

    # Optional fields for content types - FormContent here uses the updated definition
    text_content: Optional[TextContent] = None
    markdown_content: Optional[MarkdownContent] = None
    form_content: Optional[FormContent] = None # This now contains List[FormFieldWrapper]
    sxs_content: Optional[SxSContent] = None

    @root_validator(pre=False, skip_on_failure=True)
    def check_content_consistency(cls, values):
        response_type = values.get('response_type')
        content_fields = {
            'text': values.get('text_content'),
            'markdown': values.get('markdown_content'),
            'form': values.get('form_content'),
            'sxs': values.get('sxs_content'),
        }
        populated_fields = [k for k, v in content_fields.items() if v is not None]

        # Allow zero populated fields during construction (might be set later)
        if len(populated_fields) == 0:
             pass
        # Ensure only one content field is populated if any are set
        elif len(populated_fields) > 1:
            raise ValueError(f"Multiple content fields populated: {', '.join(populated_fields)}")
        # Ensure the populated field matches the response_type
        elif populated_fields[0] != response_type:
            raise ValueError(f"Content field '{populated_fields[0]}' does not match response_type '{response_type}'")
        return values

# --- API Request/Response Models (Unchanged) ---
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    content: str

class ChatResponse(BaseModel):
    session_id: str
    reply: ChatMessage # Contains the potentially updated ChatMessage structure

class FetchMessagesResponse(BaseModel):
    messages: List[ChatMessage] # Contains the potentially updated ChatMessage structure

# --- FastAPI App Setup ---
app = FastAPI(title="Session-Based Chatty LLM API (No IDs) - Gemini Powered")

# --- In-Memory Session Storage (Unchanged) ---
chat_sessions: Dict[str, Dict[str, Any]] = {}

# --- Helper Functions (Unchanged logic, types adapt) ---

def get_or_create_session(session_id: Optional[str]) -> tuple[str, Dict[str, Any]]:
    """ Retrieves or creates a session. """
    global chat_sessions
    if session_id and session_id in chat_sessions:
        return session_id, chat_sessions[session_id]
    elif session_id:
        # Check if session exists before raising error
        if session_id not in chat_sessions:
             raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        # This path should ideally not be reached if the check above works, but added for safety.
        return session_id, chat_sessions[session_id]
    else:
        new_session_id = str(uuid.uuid4())
        chat_sessions[new_session_id] = {"messages": []}
        print(f"Created new session: {new_session_id}")
        return new_session_id, chat_sessions[new_session_id]

def add_message_to_session(
    session_data: Dict[str, Any],
    session_id: str,
    role: Literal['user', 'assistant'],
    response_type: Literal['text', 'markdown', 'form', 'sxs'],
    content_fields: Dict[str, Any] # Expects {'text_content': {...}, 'form_content': FormContent(...), etc.}
) -> ChatMessage:
    """ Adds a message (without ID) to the session history. """
    # The content_fields dict should already contain correctly structured Pydantic models
    # (e.g., an instance of the updated FormContent if response_type is 'form').
    # Pydantic validation within ChatMessage handles the structure check.
    try:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            response_type=response_type,
            **content_fields # Unpack: text_content=..., form_content=..., etc.
        )
        # Store the message as a dictionary in the session history
        session_data["messages"].append(message.model_dump(mode='json')) # Use mode='json' for better serialization if needed
        print(f"Added {role} message to session {session_id}. Total messages: {len(session_data['messages'])}")
        # Return the Pydantic model instance for use in the API response
        return message
    except Exception as e:
        # Catch potential validation errors or other issues during message creation
        print(f"Error creating or adding ChatMessage: {e}")
        print(f"Session Data (keys): {session_data.keys()}")
        print(f"Content Fields trying to add: {content_fields}")
        raise HTTPException(status_code=500, detail=f"Internal error creating chat message: {e}")


# --- API Endpoints (Unchanged logic, types adapt) ---

@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """ Handles chat requests using Gemini, adds user and assistant message. """
    try:
        current_session_id, session_data = get_or_create_session(request.session_id)
        # History contains dict representations of ChatMessages
        history = session_data.get("messages", [])

        # 1. Add user message (always text)
        user_content_dict = {'text_content': TextContent(text=request.content)}
        add_message_to_session(
            session_data, current_session_id, 'user', 'text', user_content_dict
        )
        # Refresh history *after* adding the user message so Gemini gets the latest turn
        history = session_data.get("messages", [])


        # 2. Generate response using Gemini
        # Pass the history (list of dicts) and new user content
        assistant_response_type, assistant_content_dict = await generate_gemini_chat_response(
            history, request.content
        )
        # assistant_content_dict will be like {'text_content': {'text': '...'}}


        # 3. Add assistant reply to history and get the message object for the response
        assistant_reply = add_message_to_session(
            session_data,
            current_session_id,
            'assistant',
            assistant_response_type, # Currently 'text' from gemini_client
            assistant_content_dict   # e.g., {'text_content': TextContent(text=...)}
        )

        # Return the response containing the session ID and the assistant's reply message object
        return ChatResponse(session_id=current_session_id, reply=assistant_reply)

    except HTTPException as e:
        # Re-raise known HTTP exceptions (like 404 Session Not Found, 503 Gemini unavailable)
        raise e
    except Exception as e:
        import traceback
        print(f"Error handling chat: {e}\n{traceback.format_exc()}")
        # Return a generic 500 error for unexpected issues
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")


@app.get("/api/chat/{session_id}/messages", response_model=FetchMessagesResponse)
async def get_session_messages(session_id: str):
    """ Fetches ALL messages for a given session ID. """
    global chat_sessions
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session_data = chat_sessions[session_id]
    # Messages are stored as dicts, convert back to ChatMessage models for the response
    # Pydantic will validate the structure based on the ChatMessage definition (including the updated FormContent)
    try:
        messages_as_models = [ChatMessage(**msg_dict) for msg_dict in session_data.get("messages", [])]
    except Exception as e:
        print(f"Error parsing stored messages for session {session_id}: {e}")
        # Decide how to handle: return empty, raise error, etc.
        raise HTTPException(status_code=500, detail=f"Error retrieving message history for session {session_id}.")

    print(f"Fetching all {len(messages_as_models)} messages for session {session_id}")
    return FetchMessagesResponse(messages=messages_as_models)


@app.get("/api/hello")
async def hello():
    return {"message": "Hello from FastAPI Session Chat API (No IDs) - Gemini Powered!"}


# --- Static File Serving (Unchanged) ---
static_files_path = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.exists(os.path.join(static_files_path, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_files_path, "assets")), name="assets")
else:
    print(f"Warning: Assets directory not found at {os.path.join(static_files_path, 'assets')}")

@app.get("/{full_path:path}")
async def serve_vue_app(full_path: str):
    index_path = os.path.join(static_files_path, "index.html")
    potential_file_path = os.path.join(static_files_path, full_path)
    # Basic security: prevent access outside static dir (though FastAPI/Starlette handle this)
    if ".." in full_path:
         raise HTTPException(status_code=404, detail="Not Found")
    # Don't serve API routes as files
    if full_path.startswith("api/"):
         raise HTTPException(status_code=404, detail="Not Found")
    # Serve index.html for directories or non-existent paths (SPA routing)
    if not os.path.isfile(potential_file_path) or full_path == "" or os.path.isdir(potential_file_path):
        if os.path.exists(index_path):
             return FileResponse(index_path, media_type='text/html')
        else:
             raise HTTPException(status_code=404, detail="index.html not found")
    # Serve the specific file if it exists
    else:
         return FileResponse(potential_file_path)


@app.get("/")
async def serve_index():
    index_path = os.path.join(static_files_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type='text/html')
    else:
        raise HTTPException(status_code=404, detail="index.html not found")

# --- Run Instruction (for local development) ---
# You would typically run this using: uvicorn api.main:app --reload --port 8000
