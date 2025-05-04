from google import genai
from google.genai import types as genai_types
import logging
from termcolor import colored
from typing import List, Dict, Any, Optional, Callable

import datetime
import re  # Import re for cleaning response text

from agent.tools import (
    AGENT_TOOLS,
    TOOL_FUNCTION_MAP,
    reset_tool_states,
    get_last_search_call,
    get_last_booking_call,
)

# Removed convert_history_to_content function

log = logging.getLogger(__name__)


class FlightBookingAgent:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash-preview-04-17",
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        if not api_key:
            raise ValueError("API key must be provided.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

        # Store tool functions for automatic calling
        self.agent_tools = AGENT_TOOLS
        self.tool_function_map = TOOL_FUNCTION_MAP  # Keep for evaluator reference

        # Initialize state
        self.state = initial_state or {}
        if "current_date" not in self.state:
            self.state["current_date"] = datetime.date.today().isoformat()
            log.info(
                f"Agent state initialized with default current_date: {self.state['current_date']}"
            )
        else:
            log.info(f"Agent state initialized with provided state: {self.state}")

        # --- Create Chat Session ---
        system_instruction = self._build_system_prompt()
        try:
            # Create the chat session with system prompt and default tools
            self.chat = self.client.chats.create(
                model=self.model_name,
                # History starts empty, first user message will populate it via send_message
                history=[],
                config=genai_types.GenerateContentConfig(  # Use ChatConfig for chat sessions
                    system_instruction=system_instruction,
                    tools=self.agent_tools,
                ),
            )
            log.info(f"Chat session created with model {self.model_name}")
        except Exception as e:
            log.exception(f"Failed to create chat session: {e}")
            raise RuntimeError(f"Could not initialize chat session: {e}")

    # _add_to_history removed - chat object manages history

    def _build_system_prompt(self) -> Optional[str]:
        """Builds the system prompt string using the agent's state."""
        prompts = [
            "You are a helpful and friendly flight booking assistant.",
            "If it's helpful, you can call multiple tools before responding to the user. For example, if the user asks for flights to all airports in London, you can invoke the search flights tool for each airport, and then respond to the user with the summary.",
        ]
        current_date = self.state.get("current_date")
        if current_date:
            prompts.append(f"Assume the current date is {current_date}.")
        # Add other state variables here if needed

        if len(prompts) > 1:
            system_prompt = "\n".join(prompts)
            log.debug(f"Using system prompt: {system_prompt}")
            return system_prompt
        else:
            log.debug("No specific state found to add to system prompt.")
            return prompts[0]  # Return base role even if no state added

    # _extract_text_response removed - response.text is simpler

    def interact(
        self, user_input: str, tools_override: Optional[List[Callable]] = None
    ) -> str:
        """
        Handles one turn of interaction using the chat session's send_message.
        Accepts an optional list of tool functions to override the defaults (for eval).
        """
        print(colored(f"\nUser: {user_input}", "green"))
        # No need to manually add user input to history - send_message does this.
        reset_tool_states()  # Reset tool state tracking for this turn

        final_agent_response_text = (
            "Sorry, something went wrong processing your request."  # Default error
        )

        # Determine which tools to use (default or override for this specific call)
        # Note: The chat session was initialized with default tools, but send_message
        # can override them for a single turn.
        current_tools = (
            tools_override if tools_override is not None else self.agent_tools
        )
        log.info(colored(f"Using tools for this turn: {[t.__name__ for t in current_tools]}", "grey"))


        response = self.chat.send_message(
            user_input,
            config=genai_types.GenerateContentConfig(
                system_instruction=self._build_system_prompt(), tools=current_tools
            ),
        )
        return response.text or "[NO_RESPONSE]"

    def get_full_history(self) -> List[genai_types.Content]:
        """Returns the conversation history from the chat object."""
        # Ensure history exists before returning
        return self.chat.get_history()

    # Keep tool state getters
    def get_last_search_call_details(self) -> Dict[str, Any] | None:
        return get_last_search_call()

    def get_last_booking_call_details(self) -> Dict[str, Any] | None:
        return get_last_booking_call()
