# api/gemini_client.py
import os
import google.generativeai as genai
from typing import List, Dict, Tuple
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not set.")

# Configure the Gemini client library
try:
    genai.configure(api_key=API_KEY)

    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    print("Gemini model initialized successfully.")
except Exception as e:
    print(f"Error configuring or initializing Gemini model: {e}")
    model = None # Ensure model is None if initialization fails

# --- Helper Functions ---

def _format_history_for_gemini(chat_history: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """
    Formats the internal chat history (list of ChatMessage dicts)
    into the structure expected by the Gemini API (alternating user/model roles).
    """
    gemini_history = []
    for message in chat_history:
        role = message.get('role')
        # Find the actual content based on response_type
        content = ""
        # Prioritize text_content as it's the primary input/output for basic chat
        if message.get('text_content') and isinstance(message.get('text_content'), dict):
            content = message['text_content'].get('text', '')
        elif message.get('markdown_content') and isinstance(message.get('markdown_content'), dict):
             # Use markdown as text for history context if text_content is missing
            content = message['markdown_content'].get('markdown', '')
        # Add other content types if needed for context, converting them to text representation.
        # Example: If a form was submitted, you might want to represent the user's input.
        # elif message.get('form_content') and isinstance(message.get('form_content'), dict):
        #     # Represent form data as text (this is just an example)
        #     title = message['form_content'].get('title', 'Form')
        #     fields = message['form_content'].get('fields', [])
        #     field_summary = ", ".join([f"{f.get('label', f.get('field_id','?'))}: [User Input]" for f in fields]) # Placeholder for actual input
        #     content = f"Form Submitted: {title} ({field_summary})"

        if not content:
            print(f"Warning: Skipping message with no usable text/markdown content for Gemini history: {message}")
            continue

        # Map 'assistant' role to 'model' for Gemini API
        gemini_role = "model" if role == "assistant" else role

        # Ensure parts is a list containing a dict with 'text' key
        gemini_history.append({"role": gemini_role, "parts": [{"text": content}]})

    # Clean up history: Ensure alternating roles. Gemini requires this.
    cleaned_history = []
    if gemini_history:
        last_role = None
        merged_parts = []
        for item in gemini_history:
            current_role = item['role']
            current_parts = item.get('parts', [])

            if current_role == last_role:
                # Same role as before, merge parts
                merged_parts.extend(current_parts)
            else:
                # Different role, finalize the previous entry if it exists
                if last_role is not None:
                    # Filter out empty parts before adding
                    valid_merged_parts = [p for p in merged_parts if p.get('text', '').strip()]
                    if valid_merged_parts:
                         cleaned_history.append({"role": last_role, "parts": valid_merged_parts})
                    else:
                         print(f"Warning: Skipping entry for role '{last_role}' due to empty merged parts.")

                # Start new entry
                last_role = current_role
                merged_parts = current_parts

        # Add the last processed entry
        # Filter out empty parts before adding
        valid_merged_parts = [p for p in merged_parts if p.get('text', '').strip()]
        if last_role is not None and valid_merged_parts:
            cleaned_history.append({"role": last_role, "parts": valid_merged_parts})
        elif last_role is not None:
             print(f"Warning: Skipping final entry for role '{last_role}' due to empty merged parts.")


    # The history for a new turn should ideally end with a 'user' message.
    # If the cleaned history ends with 'model', the API might behave unexpectedly.
    # The calling function (`handle_chat`) should ensure the *new* user message
    # is appended *after* this history when calling the API.
    if cleaned_history and cleaned_history[-1]['role'] == 'model':
         print("Warning: Formatted history ends with a 'model' role. Ensure the next user message is appended before sending to API.")

    return cleaned_history


# --- Main Function ---

async def generate_gemini_chat_response(
    chat_history: List[Dict[str, any]], # Expects list of dicts from session storage
    user_content: str
) -> Tuple[str, Dict[str, any]]:
    """
    Generates a chat response using the Gemini API.

    Args:
        chat_history: List of previous ChatMessage objects (as dicts) in the session.
        user_content: The latest message text from the user.

    Returns:
        A tuple containing:
        - response_type: Currently always 'text'.
        - content_dict: A dictionary containing the response content, structured
                        for the ChatMessage model, e.g.,
                        {'text_content': {'text': response_text}}.
    Raises:
        HTTPException: If the API call fails or the model is not initialized.
    """
    if not model:
        raise HTTPException(status_code=503, detail="Gemini model not available or initialized.")

    # Format the history from list of dicts
    formatted_history = _format_history_for_gemini(chat_history)

    # Combine history with the new user message for the API call
    # The new user message MUST be the last item for a typical chat turn.
    current_turn_content = [
        *formatted_history,
        {"role": "user", "parts": [{"text": user_content}]}
    ]

    try:
        # Use generate_content for a stateless call (simpler for this backend)
        print(f"Sending to Gemini. History length: {len(formatted_history)}. New content: '{user_content[:50]}...'")
        # print(f"Full content being sent: {current_turn_content}") # Uncomment for detailed debugging

        response = await model.generate_content_async(
            contents=current_turn_content,
            # Optional: Add safety settings, generation config, etc.
            # generation_config=genai.types.GenerationConfig(...)
            # safety_settings=[...]
            )

        # --- Response Handling ---
        # Check for safety flags or blocks
        if not response.candidates:
             # Try to get prompt feedback for the reason
             reason = "Unknown"
             try:
                 reason = response.prompt_feedback.block_reason.name
             except Exception:
                 pass # Ignore if feedback isn't available
             print(f"Warning: Gemini response was blocked or empty. Reason: {reason}")
             # You could raise an HTTPException or return a specific message
             # raise HTTPException(status_code=400, detail=f"Content blocked by API. Reason: {reason}")
             response_text = f"(Response blocked by safety filters: {reason})"

        # Check if the first candidate has content parts
        elif not response.candidates[0].content.parts:
            # Try to get finish reason if available
            finish_reason = "Unknown"
            try:
                finish_reason = response.candidates[0].finish_reason.name
            except Exception:
                pass
            print(f"Warning: Gemini response candidate contained no parts. Finish Reason: {finish_reason}")
            response_text = f"(No response text received. Finish Reason: {finish_reason})"
        else:
            # Extract the text from the first part of the first candidate
            response_text = response.candidates[0].content.parts[0].text

        print(f"Received Gemini response: '{response_text[:100]}...'")

        # For now, always return as 'text' and structure for ChatMessage model
        response_type = 'text'
        # Create the nested structure expected by add_message_to_session
        content_dict = {'text_content': {'text': response_text}}

        return response_type, content_dict

    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        import traceback
        print(traceback.format_exc()) # Print full traceback for debugging
        # Consider more specific error handling based on Gemini API errors
        # e.g., handle google.api_core.exceptions.PermissionDenied, ResourceExhausted, etc.
        raise HTTPException(status_code=500, detail=f"Failed to get response from LLM: {e}")

