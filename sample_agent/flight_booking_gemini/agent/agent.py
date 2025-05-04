# agent/agent.py
from google.genai import types
from google import genai
from google.genai import types as genai_types
import logging
from termcolor import colored
from typing import List, Dict, Any, Optional  # Added Optional
import datetime  # Import datetime for default date

from agent.tools import (
    AGENT_TOOLS,
    reset_tool_states,
    get_last_search_call,
    get_last_booking_call,
)

log = logging.getLogger(__name__)


class FlightBookingAgent:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash-latest",
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        if not api_key:
            raise ValueError("API key must be provided.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.history: List[Dict[str, Any]] = []
        # Initialize state, providing a default current_date if none is given
        self.state = initial_state or {}
        if "current_date" not in self.state:
            self.state["current_date"] = datetime.date.today().isoformat()
            log.info(
                f"Agent state initialized with default current_date: {self.state['current_date']}"
            )
        else:
            log.info(f"Agent state initialized with provided state: {self.state}")

    def _add_to_history(
        self,
        role: str,
        text: str = None,
        function_call: Any = None,
        function_response: Any = None,
    ):
        """Adds a turn to the conversation history using the new format."""
        parts = []
        if text:
            parts.append({"text": text})
        # Note: The SDK automatically adds function calls/responses to history
        # when using automatic function calling. Manually adding them here
        # might duplicate information if not handled carefully.
        # Let's rely on the SDK's history management for function calls/responses.
        if parts:
            self.history.append({"role": role, "parts": parts})

    def _build_system_prompt(self) -> Optional[str]:
        """Builds the system prompt string using the agent's state."""
        prompts = ["You are a helpful and friendly flight booking assistant."]

        # Add state information
        current_date = self.state.get("current_date")
        if current_date:
            prompts.append(f"Assume the current date is {current_date}.")
        # Add other state variables here as needed
        # e.g., user_preferences = self.state.get('preferences')
        # if user_preferences: prompts.append(f"User preferences: {user_preferences}")

        if len(prompts) > 1:  # Only return if we added state info beyond the base role
            system_prompt = "\n".join(prompts)
            log.debug(f"Using system prompt: {system_prompt}")
            return system_prompt
        else:
            log.debug("No specific state found to add to system prompt.")
            return None  # Or return the base role if desired

    def interact(self, user_input: str) -> str:
        """
        Handles one turn of interaction using automatic function calling,
        incorporating agent state via system prompt.
        """
        print(colored(f"\nUser: {user_input}", "green"))
        # Add user message to history *before* the API call
        self._add_to_history("user", text=user_input)
        reset_tool_states()  # Reset tool state tracking for this turn

        agent_response_text = "Sorry, something went wrong."
        system_instruction = self._build_system_prompt()

        try:
            # Make the API call
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=self.history,  # Pass the current history
                config=genai_types.GenerateContentConfig(
                    tools=AGENT_TOOLS,
                    # Disable thinking.
                    # thinking_config=types.ThinkingConfig(thinking_budget=0),
                    system_instruction=system_instruction
                ),
                # The SDK automatically handles history updates with function calls/results
            )

            # --- Debugging ---
            # try:
            #      print(colored(f"DEBUG Raw Response:\n{response.model_dump_json(indent=2)}", "magenta"))
            # except Exception as e:
            #      print(colored(f"DEBUG Error printing raw response: {e}", "red"))
            # --- End Debugging ---

            # Process the response
            if response.candidates:
                response_content = response.candidates[0].content
                # Extract text parts for the agent's reply
                agent_response_text = "".join(
                    part.text
                    for part in response_content.parts
                    if hasattr(part, "text")
                )

                # Add the *final* agent text response to history AFTER processing
                # (The SDK handles intermediate function call/response history)
                if agent_response_text:
                    self._add_to_history("model", text=agent_response_text)
                else:
                    # Handle cases where the response might *only* be a function call
                    # The SDK should add the function call to history automatically.
                    # We might want a placeholder text if *no* text response is generated.
                    agent_response_text = (
                        "[Agent decided to use a tool]"  # Or handle as needed
                    )
                    log.info("Agent response contained only function calls/no text.")
                    # Don't add this placeholder to history, let SDK manage tool history

            elif response.prompt_feedback:
                agent_response_text = f"I couldn't generate a response. Feedback: {response.prompt_feedback}"
                log.warning(
                    f"Received response with feedback: {response.prompt_feedback}"
                )
                # Add this error feedback as the agent's turn in history
                self._add_to_history("model", text=agent_response_text)

            print(colored(f"Agent: {agent_response_text}", "blue"))

        except Exception as e:
            log.exception(f"Error during generate_content: {e}")
            agent_response_text = f"Sorry, an error occurred: {e}"
            print(colored(f"Agent: {agent_response_text}", "red"))
            # Add the error message to history
            self._add_to_history("model", text=agent_response_text)

        # Update self.history based on the SDK's response handling if needed
        # For automatic function calling, the SDK *should* update the history passed
        # back in the `response` object, but `self.history` might need manual sync
        # if the SDK doesn't modify the list in-place. Let's assume for now
        # we manually added user/final model turns, and SDK handles tool turns.
        # A more robust approach might involve rebuilding history from response.parts.

        return agent_response_text

    def get_full_history(self) -> list:
        """Returns the conversation history."""
        # Consider returning a copy to prevent external modification
        return list(self.history)

    def get_last_search_call_details(self) -> Dict[str, Any] | None:
        return get_last_search_call()

    def get_last_booking_call_details(self) -> Dict[str, Any] | None:
        return get_last_booking_call()
