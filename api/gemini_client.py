import os
from google import genai
from google.genai import types
from typing import List, Optional
from dotenv import load_dotenv
from models import TextAndWorkflowState

load_dotenv()

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

client = genai.Client(api_key=API_KEY)

model_name = "gemini-2.5-flash-preview-04-17"

async def generate_gemini_response_stateless(
    system_instructions: str,
    history: List[types.Content], # Expects a list of Content objects
    latest_user_content: str,
) -> Optional[TextAndWorkflowState]:
    """
    Generates a chat response using the stateless generate_content_stream method,
    expecting a response matching the TextAndWorkflowState schema.

    Args:
        system_instructions: The system prompt/instructions for the chat model.
        history: The conversation history as a list of genai.types.Content objects.
                 Each Content object should have role ('user' or 'model') and parts.
        latest_user_content: The latest message text from the user to be added.

    Returns:
        An instance of TextAndWorkflowState if the response matches the schema,
        otherwise None or raises an error.

    Note: This function is now stateless. The calling code (e.g., FastAPI endpoint)
          is responsible for managing and passing the full conversation history.
    """
    current_contents = history + [
        types.Content(role="user", parts=[types.Part.from_text(text=latest_user_content)])
    ]
    generation_config = types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=TextAndWorkflowState, # Specify the expected Pydantic schema
        system_instruction=system_instructions,
    )
    
    response = client.models.generate_content(
        model=model_name,
        contents=current_contents, # Pass the full history + new message
        config=generation_config,
    )
    return response.parsed
