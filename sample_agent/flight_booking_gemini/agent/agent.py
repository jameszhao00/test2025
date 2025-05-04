from google.genai import types
from google import genai
from google.genai import types as genai_types
import logging
from termcolor import colored
from typing import List, Dict, Any

from agent.tools import (
    AGENT_TOOLS,
    reset_tool_states,
    get_last_search_call,
    get_last_booking_call,
)

log = logging.getLogger(__name__)


class FlightBookingAgent:
    # Accept api_key in constructor
    def __init__(
        self, api_key: str, model_name: str = "gemini-2.5-flash-preview-04-17"
    ):
        # Removed dotenv loading and os.getenv
        if not api_key:
            # This check is now mainly for programmatic use, run.py handles env loading
            raise ValueError("API key must be provided.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.history: List[Dict[str, Any]] = []

    # ... (rest of the _add_to_history method is unchanged) ...
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
        if parts:
            self.history.append({"role": role, "parts": parts})

    def interact(self, user_input: str) -> str:
        """
        Handles one turn of interaction using automatic function calling.
        """
        print(colored(f"\nUser: {user_input}", "green"))
        self._add_to_history("user", text=user_input)
        reset_tool_states()

        agent_response_text = "Sorry, something went wrong."

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=self.history,
                config=genai_types.GenerateContentConfig(
                    tools=AGENT_TOOLS,
                    # Disable thinking.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

            # --- Debugging ---
            # try:
            #      print(colored(f"DEBUG Raw Response:\n{response.model_dump_json(indent=2)}", "magenta"))
            # except Exception as e:
            #      print(colored(f"DEBUG Error printing raw response: {e}", "red"))
            # --- End Debugging ---

            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        log.debug(
                            f"SDK automatically called: {part.function_call.name}"
                        )

                agent_response_text = "".join(
                    part.text
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "text")
                )

            elif response.prompt_feedback:
                agent_response_text = f"I couldn't generate a response. Feedback: {response.prompt_feedback}"
                log.warning(
                    f"Received response with feedback: {response.prompt_feedback}"
                )

            print(colored(f"Agent: {agent_response_text}", "blue"))
            self._add_to_history("model", text=agent_response_text)

        except Exception as e:
            log.exception(f"Error during generate_content: {e}")
            agent_response_text = f"Sorry, an error occurred: {e}"
            print(colored(f"Agent: {agent_response_text}", "red"))

        return agent_response_text

    def get_full_history(self) -> list:
        """Returns the conversation history in the new format."""
        return self.history

    def get_last_search_call_details(self) -> Dict[str, Any] | None:
        return get_last_search_call()

    def get_last_booking_call_details(self) -> Dict[str, Any] | None:
        return get_last_booking_call()
