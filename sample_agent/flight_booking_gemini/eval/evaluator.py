# eval/evaluator.py
import re
import logging
from typing import List, Dict, Any, Optional, Callable  # Added Callable
from google import genai
from google.genai import types as genai_types
from termcolor import colored
import json  # For comparing args

# Import the *real* tool functions to get their signatures for wrappers
from agent.tools import reset_tool_states

from agent.agent import FlightBookingAgent
from eval.assertion_types import (
    LLMCheckAssertion,
    AssertionResult,
)
import dataclasses


@dataclasses.dataclass
class FunctionCall:
    """Represents a function call request and its corresponding response."""

    request: genai_types.FunctionCall
    response: genai_types.FunctionResponse


def flatten_content_list_to_role_and_parts(
    content_list: List[genai_types.Content],
) -> List[tuple[str, genai_types.Part]]:

    role_and_parts = [
        (content.role, part)
        for content in content_list
        if content.parts and content.role in ["user", "model"]
        for part in content.parts
    ]
    return role_and_parts


def extract_function_calls(
    content_list: List[genai_types.Content],
) -> List[FunctionCall]:
    """
    Extracts pairs of FunctionCall (request and response) from a list of Content objects.

    Args:
        content_list: A list of types.Content objects.

    Returns:
        A list of FunctionCall objects, where each object contains the model's
        function_call Content and the user's function_response Content.
    """

    extracted_calls: List[FunctionCall] = []

    role_and_parts = flatten_content_list_to_role_and_parts(content_list)
    # We can't simply look at the next Content to find the response, as the model may make multiple calls in one Content.
    calls = [
        p.function_call for r, p in role_and_parts if r == "model" and p.function_call
    ]
    responses = [
        p.function_response
        for r, p in role_and_parts
        if r == "user" and p.function_response
    ]
    if len(calls) != len(responses):
        raise ValueError(
            f"Mismatch in function call and response counts: {len(calls)} calls, {len(responses)} responses."
        )
    for function_call, function_response in zip(calls, responses):
        extracted_calls.append(
            FunctionCall(
                request=function_call,
                response=function_response,
            )
        )
    return extracted_calls


def pretty_print_text_content_parts(
    content_list: list[genai_types.Content], model_role_alias: str = "Agent"
) -> str:
    """
    Converts a list of Content objects into a formatted string.

    Args:
        content_list: A list of Content objects (or mock objects with role and text).
        model_role_alias: The alias used for the model's role (e.g., 'Agent').

    Returns:
        A string with the content formatted as specified.
    """
    formatted_text = ""
    for content in content_list:
        # Extract text from the first part (assuming text is in the first part)
        if not content.parts:
            continue
        for part in content.parts:
            if part.text:
                if content.role == "user":
                    formatted_text += f"""--- User ---
{part.text}
--- End User ---
                    
"""
                elif content.role == "model":
                    formatted_text += f"""--- {model_role_alias} ---
{part.text}
--- End {model_role_alias} ---

"""
                else:
                    raise ValueError(
                        f"Unknown role {content.role} in content {content}."
                    )
    return formatted_text.strip()  # Use strip() to remove trailing newline


log = logging.getLogger(__name__)


# Custom exception for tool replay mismatch
class EvalToolMismatchError(Exception):
    pass


class GeminiEvaluator:
    def __init__(
        self,
        api_key: str,
        eval_model_name: str = "gemini-2.5-flash-preview-04-17",  # Updated default
    ):
        if not api_key:
            raise ValueError("API key must be provided for evaluator.")

        try:
            # Use Client for evaluator's own LLM calls (simulation, assertions)
            self.client = genai.Client(api_key=api_key)
            # Test connection? Maybe not necessary here.
        except Exception as e:
            log.error(f"Failed to initialize Gemini Client for Evaluator: {e}")
            raise ValueError(
                f"Failed to initialize Gemini Client for Evaluator. Check API key and permissions. Error: {e}"
            )

        self.eval_model_name = eval_model_name
        log.info(f"Evaluator initialized with model: {self.eval_model_name}")

    def _simulate_user_turn(
        self, goal: str, history: list[genai_types.Content]
    ) -> str | None:
        """Uses an LLM to simulate the user's next response."""
        # If the return is None, it indicates the simulation requested we stop.
        log.info("Simulating user turn...")
        chat_history = pretty_print_text_content_parts(
            history, model_role_alias="Agent"
        )

        prompt = f"""You are a english speaking person (who knows nothing about LLMs) interacting with a flight booking agent.
Your overall goal is: "{goal}"

Here is the conversation history so far:
--- HISTORY START ---
{chat_history}
--- HISTORY END ---

Based on the agent's last message and your goal, what would you say next?
- Provide necessary information only when asked or when logical. Do not provide more details than needed.
- Respond as concisely as possible. Assume the agent remembers previous options and context, and refer to them implicitly rather than restating details unless absolutely necessary for clarity.
- Don't reveal all your constraints at once unless asked directly.
- If the agent asks a clarifying question, answer it relevantly.
- If the agent presents options, make a choice.
- If you're done with the conversation, say the special string "EXIT" and nothing else to exit out of the simulation.

--- EXAMPLE RESPONSE ---
book flight from SFO to JFK tomorrow.
--- END EXAMPLE RESPONSE ---

Your response:"""
        # log.info(colored(f"Simulating User Prompt: {prompt}", "yellow"))
        try:
            # Use the evaluator's client
            response = self.client.models.generate_content(
                model=self.eval_model_name,
                contents=prompt,
            )
            if response.candidates:
                simulated_response = "".join(
                    part.text
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "text")
                ).strip()
                # Clean up potential prefixes
                simulated_response = re.sub(
                    r"^(User|You|Your response):\s*",
                    "",
                    simulated_response,
                    flags=re.IGNORECASE,
                ).strip()

                if simulated_response.lower() == "exit":
                    log.info("Simulated user indicated they are done.")
                    return None

                if not simulated_response:
                    log.warning("User simulation returned an empty response.")
                    return "[Simulation Error: Empty response]"
                log.info(colored(f"Simulated User: {simulated_response}", "cyan"))

                return simulated_response
            else:
                feedback_info = (
                    response.prompt_feedback
                    if hasattr(response, "prompt_feedback")
                    else "No feedback available"
                )
                log.error(
                    f"User simulation failed: No candidates. Feedback: {feedback_info}"
                )
                return f"[Simulation Error: No response. Feedback: {feedback_info}]"
        except Exception as e:
            log.exception(f"User simulation failed with exception: {e}")
            return f"[Simulation Error: Exception - {type(e).__name__}]"

    def _find_matching_tool_call_in_trace(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        golden_trace: List[genai_types.Content],
    ) -> Optional[dict[str, Any]]:
        """Searches the golden trace for a matching tool call and returns its result."""
        log.info(
            colored(
                f"Searching golden trace for: {tool_name} with args {tool_args}", "grey"
            )
        )

        golden_calls = extract_function_calls(golden_trace)

        for call in golden_calls:
            if not call.request.name == tool_name:
                continue
            request_args = call.request.args
            current_args_json = json.dumps(tool_args, sort_keys=True)
            trace_args_json = json.dumps(request_args, sort_keys=True)

            log.info(
                colored(
                    f"Comparing tool request vs golden: request: {current_args_json}, trace: {trace_args_json}",
                    "grey",
                )
            )

            if current_args_json == trace_args_json:
                log.info(
                    f"Found matching tool call in golden trace for {tool_name}. Replaying result."
                )
                return call.response.response

        log.info(
            colored("Did not find any matching tool calls in the golden trace.", "red")
        )
        return None

    def evaluate_trace(
        self,
        agent: FlightBookingAgent,
        golden_trace: List[genai_types.Content],  # List of dicts from Pydantic
        assertions: List[LLMCheckAssertion],
        goal_description: str,
        max_turns: int = 15,
        agent_tool_map: Optional[
            Dict[str, Callable]
        ] = None,  # Keep for reference, but not used directly
    ) -> Dict[str, Any]:
        """
        Runs agent using automatic function calling, evaluates using LLM assertions.
        Always passes wrapper functions to the agent to replay tool results from the golden trace.
        """
        log.info(f"Starting evaluation for goal: '{goal_description}'")

        # --- Setup Tool Replay Wrappers ---
        # These wrappers intercept calls and replay results from the golden trace.
        # Their signatures MUST exactly match the real tools for automatic function calling.
        global _last_search_call, _last_booking_call  # Need access to update state for assertions

        def replay_tool_executor(name: str, args: Dict[str, Any]) -> Any:
            """Finds result in trace or raises error."""
            log.debug(f"[Replay Run] Intercepting tool call via wrapper: {name}")
            result = self._find_matching_tool_call_in_trace(name, args, golden_trace)
            if result is not None:
                log.info(f"[Replay Run] Replaying result for {name} from trace.")
                if name == "search_flights":
                    _last_search_call = {"args": args, "result": result}
                elif name == "book_flight":
                    _last_booking_call = {"args": args, "result": result}
                return result
            else:
                # Log the specific call that failed to find a match
                log.error(
                    f"EvalToolMismatchError: Agent tried to call tool '{name}' with args {args}, but no matching call was found in the golden trace."
                )
                # Log the golden trace for comparison (optional, can be verbose)
                # log.debug(f"Golden Trace Searched:\n{json.dumps(golden_trace, indent=2)}")
                raise EvalToolMismatchError(
                    f"Agent tried to call tool '{name}' with args {args}, "
                    f"but no matching call was found in the golden trace."
                )

        # Create wrapper functions with correct signatures that call the replay executor
        # Ensure signature (name, params, types, docstring) matches the original tool exactly.
        def search_flights(
            origin: str, destination: str, departure_date: str
        ) -> list[dict]:
            """
            Searches for available flights based on criteria.

            Args:
                origin: The departure airport code (e.g., "SFO").
                destination: The arrival airport code (e.g., "JFK").
                departure_date: The desired departure date (YYYY-MM-DD).

            Returns:
                A list of flight dictionaries, each containing flight_id, airline,
                departure_time, arrival_time, and price. Returns an empty list if no
                flights match or date is invalid.
            """
            # Manually construct args dict to avoid capturing replay_tool_executor from locals()
            args = {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
            }
            # Docstring is copied from the original function for the LLM's schema generation
            return replay_tool_executor("search_flights", args)

        def book_flight(flight_id: str) -> dict:
            """
            Books the flight specified by the flight_id.

            Args:
                flight_id: The unique identifier of the flight to book.

            Returns:
                A dictionary containing the booking confirmation details, including
                booking_id and status. Returns failure status if flight_id is invalid.
            """
            # Manually construct args dict
            args = {"flight_id": flight_id}
            # Docstring is copied from the original function for the LLM's schema generation
            return replay_tool_executor("book_flight", args)

        # List of tools to pass to the agent during evaluation replay
        # Always use the replay tools, even in simulation mode, to ensure
        replay_tools = [search_flights, book_flight]
        tools_for_this_run = replay_tools

        # --- Reset Agent and State ---
        try:
            # Reset tool state tracking at the beginning of evaluation
            reset_tool_states()
        except ImportError:
            log.warning(
                "Could not import and call reset_tool_states(). Tool state might persist."
            )

        # --- Get Initial User Input ---
        initial_user_input: Optional[str] = "hey"

        log.info(f"Using initial user input: {initial_user_input}")

        # --- Conversation Loop ---
        current_turn_index = 0
        user_input: Optional[str] = initial_user_input
        trace_index = (
            0  # Index for iterating through golden_trace in non-simulated mode
        )
        total_tool_calls = 0  # Count actual tool executions/replays

        while current_turn_index < max_turns:
            current_turn_index += 1
            log.info(f"--- Running Turn {current_turn_index} ---")

            if user_input is None:
                log.warning(
                    f"Ending conversation loop: No user input for turn {current_turn_index}."
                )
                break

            agent_response_text = agent.interact(
                user_input, tools_override=tools_for_this_run
            )
            log.info(colored(f"Agent: {agent_response_text}", "blue"))

            if (
                agent_response_text is None
                or "[No Agent Response Found]" in agent_response_text
                or "Sorry, an error occurred" in agent_response_text
                or "[Agent provided no response]" in agent_response_text
                or "[Agent provided no text response]"
                in agent_response_text  # Added check
                or "[Agent provided no response candidates]"
                in agent_response_text  # Added check
            ):
                log.warning(
                    f"Ending conversation loop due to missing or error in agent response on turn {current_turn_index}."
                )
                break

            # --- Determine Next User Input ---

            user_input = self._simulate_user_turn(
                goal_description, agent.get_full_history()
            )
            if not user_input:
                log.info("Simulated user seems finished. Ending conversation loop.")
                break

        log.info(
            f"--- Evaluating {len(assertions)} LLM Assertions Against Full Trace ({len(agent.get_full_history())} recorded turns) ---"
        )
        assertion_results: List[AssertionResult] = []
        outcome_passed: Optional[bool] = None
        trajectory_checks_passed = 0
        trajectory_checks_total = 0

        for assertion in assertions:
            log.info(f"Evaluating assertion: {assertion.name}")
            try:
                # Pass the agent's raw history directly to the assertion evaluator
                result = assertion.evaluate(
                    agent_history=agent.get_full_history(),  # Pass raw history
                    llm_client=self.client,  # Use evaluator's client
                    eval_model_name=self.eval_model_name,
                )
                assertion_results.append(result)

                if result.is_outcome_check:
                    if outcome_passed is None:
                        outcome_passed = (
                            result.passed
                        )  # First outcome check sets initial status
                    elif not result.passed:
                        outcome_passed = (
                            False  # Any failed outcome check makes overall outcome fail
                        )
                    log.info(
                        f"Outcome Check ({result.name}): {'PASSED' if result.passed else 'FAILED'}"
                    )
                else:
                    trajectory_checks_total += 1
                    if result.passed:
                        trajectory_checks_passed += 1
                    log.info(
                        f"Trajectory Check ({result.name}): {'PASSED' if result.passed else 'FAILED'}"
                    )
            except Exception as e:
                log.exception(f"Error evaluating assertion '{assertion.name}': {e}")
                assertion_results.append(
                    AssertionResult(
                        name=assertion.name,
                        passed=False,
                        details=f"Evaluation failed with exception: {e}",
                        is_outcome_check=assertion.is_outcome_check,
                    )
                )
                if assertion.is_outcome_check and outcome_passed is None:
                    outcome_passed = False

        if outcome_passed is None:
            log.warning(
                "Evaluation completed, but no assertion was marked as the outcome check (is_outcome_check=True) or the check errored."
            )
            final_outcome_passed = False
        else:
            final_outcome_passed = outcome_passed

        trajectory_quality = (
            (trajectory_checks_passed / trajectory_checks_total)
            if trajectory_checks_total > 0
            else 1.0
        )

        max_turns_hit = current_turn_index >= max_turns
        if max_turns_hit and not final_outcome_passed:
            log.warning(
                f"Evaluation reached max turns ({max_turns}) without achieving the goal (Outcome: FAILED)."
            )

        # Uncomment if you want to log the full history
        # log.info("--- Chat and tool use history ---")
        # for h in agent.get_full_history():
        #     logging.info(
        #         colored(h.model_dump_json(indent=2, exclude_unset=True), "light_blue")
        #     )

        log.info(
            f"Evaluation finished. Outcome: {'PASSED' if final_outcome_passed else 'FAILED'}, Trajectory: {trajectory_quality:.2%}, Tool Calls: {total_tool_calls}"
        )

        return {
            "goal": goal_description,
            "outcome_passed": final_outcome_passed,
            "trajectory_quality": trajectory_quality,
            "tool_calls": total_tool_calls,
            "details": assertion_results,
            "error": None,
        }

    def display_results(self, results: Dict[str, Any]):
        """Prints evaluation results focusing on the three facets."""
        print("\n--- Evaluation Report ---")
        print(f"Goal: {results.get('goal', 'N/A')}")

        if results.get("error"):
            print(colored(f"\nEvaluation Error: {results['error']}", "red"))
            # Don't print facets if there was a setup error
        else:
            print("\n--- Facets ---")
            outcome_passed = results.get("outcome_passed", False)
            outcome_status = (
                colored("PASSED", "green")
                if outcome_passed
                else colored("FAILED", "red")
            )
            print(f"1. Outcome Achieved: {outcome_status}")

            quality_perc = results.get("trajectory_quality", 0.0) * 100
            if quality_perc >= 90:
                traj_color = "green"
            elif quality_perc >= 70:
                traj_color = "yellow"
            else:
                traj_color = "red"
            print(
                f"2. Trajectory Quality: {colored(f'{quality_perc:.1f}%', traj_color)} (% non-outcome assertions passed)"
            )

            tool_calls = results.get("tool_calls", 0)
            # Adjust cost coloring thresholds if needed
            if tool_calls <= 2:
                cost_color = "green"
            elif tool_calls <= 4:
                cost_color = "yellow"
            else:
                cost_color = "red"
            print(f"3. Cost/UX (Tool Calls): {colored(tool_calls, cost_color)}")

        print("\n--- Detailed Assertion Results ---")
        details: List[AssertionResult] = results.get("details", [])
        if not details:
            print("No detailed assertion results available.")
        else:
            # Sort: Outcome checks first, then by name
            sorted_details = sorted(
                details, key=lambda x: (not x.is_outcome_check, x.name)
            )
            for check in sorted_details:
                status = (
                    colored("PASS", "green") if check.passed else colored("FAIL", "red")
                )
                outcome_marker = (
                    "[OUTCOME]" if check.is_outcome_check else "[TRAJECTORY]"
                )
                print(f"- {outcome_marker} {check.name}: {status}")
                if not check.passed and check.details:
                    # Indent details for readability
                    details_lines = check.details.split("\n")
                    print(f"    Details: {details_lines[0]}")
                    for line in details_lines[1:]:
                        print(f"             {line}")  # Increased indent

        print("--- End Report ---")
