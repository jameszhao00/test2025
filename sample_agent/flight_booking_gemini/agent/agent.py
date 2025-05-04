# agent/agent.py
from google import genai
from google.genai import types as genai_types
import logging
from termcolor import colored
from typing import List, Dict, Any, Optional, Callable  # Added Callable

import datetime

from agent.tools import (
    AGENT_TOOL_DECLARATIONS,  # Import declarations
    TOOL_FUNCTION_MAP,  # Import function map
    reset_tool_states,
    get_last_search_call,
    get_last_booking_call,
)


def convert_history_to_content(history):
    return [genai_types.Content(role=role, parts=[part]) for role, part in history]


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
        self.model_name = model_name  # Keep for logging/reference
        self.history: List[tuple[str, genai_types.Part]] = (
            []
        )  # History will store dicts matching API Content structure

        # Store tool declarations and implementation map
        self.tool_declarations = AGENT_TOOL_DECLARATIONS
        self.tool_function_map = TOOL_FUNCTION_MAP

        # Default tool executor calls the real functions
        self._tool_executor: Callable[[str, Dict[str, Any]], Any] = (
            self._default_tool_executor
        )

        # Initialize state
        self.state = initial_state or {}
        if "current_date" not in self.state:
            self.state["current_date"] = datetime.date.today().isoformat()
            log.info(
                f"Agent state initialized with default current_date: {self.state['current_date']}"
            )
        else:
            log.info(f"Agent state initialized with provided state: {self.state}")

    def set_tool_executor(self, executor: Callable[[str, Dict[str, Any]], Any]):
        """Sets a custom function to execute tools (used for evaluation replay)."""
        log.info(f"Setting custom tool executor: {executor.__name__}")
        self._tool_executor = executor

    def _default_tool_executor(self, name: str, args: Dict[str, Any]) -> Any:
        """The default executor that calls the actual Python functions."""
        if name in self.tool_function_map:
            func = self.tool_function_map[name]
            result = func(**args)
            return result
        else:
            log.error(f"Attempted to execute unknown tool: {name}")
            return {"error": f"Unknown tool name: {name}"}

    def _add_to_history(self, role: str, parts: List[genai_types.Part]):
        """Adds a turn to the conversation history using the API's Content structure."""
        for part in parts:
            self.history.append((role, part))

    def _build_system_prompt(self) -> Optional[str]:
        """Builds the system prompt string using the agent's state."""
        prompts = ["You are a helpful and friendly flight booking assistant."]
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

    def _extract_text_response(
        self, response: genai_types.GenerateContentResponse
    ) -> Optional[str]:
        """Safely extracts text from the response candidates."""
        text_parts = [
            part.text for part in response.candidates[0].content.parts if part.text
        ]
        return "".join(text_parts) if text_parts else None

    def _find_function_call(
        self, response: genai_types.GenerateContentResponse
    ) -> Optional[genai_types.FunctionCall]:
        """Finds the first function call in the response candidates."""
        for part in response.candidates[0].content.parts:
            if part.function_call:
                return part.function_call
        return None

    def interact(self, user_input: str) -> str:
        """
        Handles one turn of interaction using manual function calling.
        """
        print(colored(f"\nUser: {user_input}", "green"))
        # Add user message to history *before* the first API call
        self._add_to_history("user", parts=[genai_types.Part(text=user_input)])
        reset_tool_states()  # Reset tool state tracking for this turn

        system_instruction = self._build_system_prompt()
        final_agent_response_text = (
            "Sorry, something went wrong processing your request."  # Default error
        )

        try:
            set_light_values_declaration = {
                "name": "set_light_values",
                "description": "Sets the brightness and color temperature of a light.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "brightness": {
                            "type": "integer",
                            "description": "Light level from 0 to 100. Zero is off and 100 is full brightness",
                        },
                        "color_temp": {
                            "type": "string",
                            "enum": ["daylight", "cool", "warm"],
                            "description": "Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.",
                        },
                    },
                    "required": ["brightness", "color_temp"],
                },
            }
            # --- First API Call: Get response or function call ---
            log.debug("Sending initial request to LLM...")

            response1 = self.client.models.generate_content(
                model=self.model_name,
                contents=convert_history_to_content(self.history),
                config=genai_types.GenerateContentConfig(
                    # No automatic_function_calling config needed here
                    # Temperature, etc., can be added if desired
                    system_instruction=system_instruction,
                    tools=AGENT_TOOL_DECLARATIONS,
                    # tools = [genai_types.Tool(function_declarations=[set_light_values_declaration])]
                ),
            )

            # --- Check for Function Call ---
            function_call = self._find_function_call(response1)

            if function_call:
                log.info(f"LLM requested function call: {function_call.name}")
                # Add the model's turn containing the function call to history
                # The part containing the function call comes directly from the response
                model_part_with_call = next(
                    (
                        p
                        for p in response1.candidates[0].content.parts
                        if p.function_call
                    ),
                    None,
                )
                if model_part_with_call:
                    self._add_to_history("model", parts=[model_part_with_call])
                else:
                    # Should not happen if function_call was found, but log defensively
                    log.error(
                        "Could not find the model part containing the function call to add to history."
                    )
                    # Fallback: manually create the part (might lose some internal details)
                    # self._add_to_history("model", parts=[genai_types.Part(function_call=function_call)])

                # --- Execute the Function ---
                tool_name = function_call.name
                # Convert FunctionCallArgs (google.protobuf.struct_pb2.Struct) to dict
                tool_args = dict(function_call.args)

                log.debug(
                    f"Executing tool '{tool_name}' with args: {tool_args} via executor."
                )
                # Use the configured executor (handles eval replay or default execution)
                tool_result = self._tool_executor(tool_name, tool_args)
                log.info(
                    f"Tool '{tool_name}' executed. Result: {str(tool_result)[:200]}..."
                )  # Log truncated result

                function_response_part = genai_types.Part.from_function_response(
                    name=tool_name,
                    response={"result": tool_result},  # Pass the Struct directly
                )

                # Add the function response part to history (API expects role 'user' for this)
                self._add_to_history("user", parts=[function_response_part])

                # --- Second API Call: Get final text response ---
                log.debug("Sending function result back to LLM...")
                response2 = self.client.models.generate_content(
                    model=self.model_name,
                    contents=convert_history_to_content(self.history),
                    config=genai_types.GenerateContentConfig(
                        tools=self.tool_declarations,
                        system_instruction=system_instruction,
                    ),  # Can add config if needed
                )

                # --- Process Final Response ---
                final_agent_response_text = self._extract_text_response(response2)
                if final_agent_response_text:
                    log.info("LLM generated final text response after function call.")
                    # Add the *final* agent text response to history
                    self._add_to_history(
                        "model",
                        parts=[genai_types.Part(text=final_agent_response_text)],
                    )
                else:
                    log.warning(
                        "LLM did not provide text response after function call."
                    )
                    final_agent_response_text = (
                        "[Agent processed tool result, but provided no further text]"
                    )
                    # Optionally add a placeholder to history, or rely on the function call/response history
                    # Let's not add this placeholder to history.

            else:
                # --- No Function Call: Process direct text response ---
                log.info("LLM provided direct text response.")
                final_agent_response_text = self._extract_text_response(response1)
                if final_agent_response_text:
                    # Add the agent's text response to history
                    self._add_to_history(
                        "model",
                        parts=[genai_types.Part(text=final_agent_response_text)],
                    )
                else:
                    log.warning("LLM did not provide function call or text response.")
                    final_agent_response_text = "[Agent provided no response]"
                    # Add placeholder to history?
                    # self._add_to_history("model", parts=[genai_types.Part(text=final_agent_response_text)])

        except Exception as e:
            log.exception(f"Error during agent interaction: {e}")
            final_agent_response_text = f"Sorry, an error occurred: {e}"
            print(colored(f"Agent Error: {final_agent_response_text}", "red"))
            # Add the error message to history if possible
            try:
                self._add_to_history(
                    "model", parts=[genai_types.Part(text=final_agent_response_text)]
                )
            except Exception as hist_e:
                log.error(f"Failed to add error message to history: {hist_e}")

        # Print final response
        print(colored(f"Agent: {final_agent_response_text}", "blue"))
        return final_agent_response_text

    def get_full_history(self) -> list[tuple[str, genai_types.Part]]:
        """Returns the conversation history (list of dicts matching API Content structure)."""
        # Return a deep copy to prevent external modification? For now, return list directly.
        return self.history

    # Keep these methods as they are used by the evaluator to check tool usage *within* a turn
    def get_last_search_call_details(self) -> Dict[str, Any] | None:
        return get_last_search_call()

    def get_last_booking_call_details(self) -> Dict[str, Any] | None:
        return get_last_booking_call()
