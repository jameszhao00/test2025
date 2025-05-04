# eval/evaluator.py
import re
import logging
from typing import List, Dict, Any, Optional, Callable  # Added Callable
from google import genai
from google.genai import types as genai_types
from termcolor import colored
import json  # For comparing args

from agent.agent import FlightBookingAgent
from eval.assertion_types import (
    LLMCheckAssertion,
    AssertionResult,
    AgentTurnData,
    ToolCallState,
)

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

    def _format_history_for_prompt(
        self, history: list[tuple[str, genai_types.Part]]
    ) -> str:
        """Formats agent's internal history for the user simulator prompt."""
        formatted = []
        for role, part in history:
            content_str = ""
            if part.text:  # Handle Part objects
                content_str += part.text or "[No Text]"
            elif part.function_call:
                fc = part.function_call
                content_str += f"[Tool Call: {fc.name}({dict(fc.args)})]"
            elif part.function_response:
                fr = part.function_response
                # Extract result carefully from Struct
                result_data = "[No Result]"
                if hasattr(fr, "response") and isinstance(
                    fr.response, dict
                ):  # Check if it's already a dict
                    result_data = fr.response.get("result", "[No Result]")

                content_str += (
                    f"[Tool Result: {fr.name} -> {str(result_data)[:100]}]"  # Truncate
                )

            if content_str:
                # Avoid printing empty turns
                formatted.append(f"{role}: {content_str}")

        return "\n".join(formatted)

    def _simulate_user_turn(
        self, goal: str, history: list[tuple[str, genai_types.Part]]
    ) -> str | None:
        """Uses an LLM to simulate the user's next response."""
        # If the return is None, it indicates the simulation requested we stop.
        log.info("Simulating user turn...")
        formatted_history = self._format_history_for_prompt(history)
        prompt = f"""You are simulating a user interacting with a flight booking agent.
Your overall goal is: "{goal}"

Here is the conversation history so far:
--- HISTORY START ---
{formatted_history}
--- HISTORY END ---

Based on the agent's last message and your goal, what would you say next?
- Behave like a normal user. Provide necessary information when asked or when logical.
- Don't reveal all your constraints at once unless asked directly.
- If the agent has successfully booked your flight and confirmed it with an ID, respond with a simple thank you or acknowledgment like "Thanks!" or "Great, thank you!".
- If the agent asks a clarifying question, answer it relevantly.
- If the agent presents options, make a choice (e.g., pick one, ask for cheapest/fastest, or ask for more details if needed).
- Keep your response concise and focused on the booking task.
- If you're done with the conversation, say the special string "EXIT" to exit out of the simulation.

Your response:"""
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
        golden_trace: List[Dict[str, Any]],
    ) -> Optional[Any]:
        """Searches the golden trace for a matching tool call and returns its result."""
        log.debug(f"Searching golden trace for: {tool_name} with args {tool_args}")
        for step in golden_trace:
            if step.get("type") == "tool_interaction":
                # Normalize args for comparison (e.g., handle None vs missing)
                # Simple comparison for now, might need more robust logic
                # Convert args to comparable format (e.g., JSON string)
                try:
                    current_args_json = json.dumps(tool_args, sort_keys=True)
                    trace_args_json = json.dumps(step.get("args", {}), sort_keys=True)
                    logging.info(
                        f"Comparing tool request vs golden: request: {current_args_json}, trace: {trace_args_json}"
                    )
                except TypeError:
                    log.warning(
                        f"Could not serialize args for comparison: {tool_args} vs {step.get('args')}"
                    )
                    continue  # Skip if args aren't comparable

                if (
                    step.get("name") == tool_name
                    and current_args_json == trace_args_json
                ):
                    log.info(
                        f"Found matching tool call in golden trace for {tool_name}. Replaying result."
                    )
                    # Return the stored result
                    return step.get("result")
        log.warning(
            f"No matching tool call found in golden trace for {tool_name} with args {tool_args}"
        )
        return None

    def evaluate_trace(
        self,
        agent: FlightBookingAgent,
        golden_trace: List[Dict[str, Any]],  # List of dicts from Pydantic
        assertions: List[LLMCheckAssertion],
        goal_description: str,
        simulate_user: bool = False,
        max_turns: int = 15,
        agent_tool_map: Optional[
            Dict[str, Callable]
        ] = None,  # Get agent's tool functions
    ) -> Dict[str, Any]:
        """
        Runs agent, evaluates using LLM assertions, reports on facets.
        Handles tool response replay in non-simulated mode.
        """
        log.info(
            f"Starting evaluation for goal: '{goal_description}' (Simulate User: {simulate_user})"
        )

        # --- Setup Tool Executor ---
        if not agent_tool_map:
            log.error("Agent tool map not provided to evaluator. Cannot execute tools.")
            return {
                "error": "Agent tool map missing.",
                "details": [],
            }  # Return error early

            # In non-simulated (golden trace) mode, replay or fail

        def tool_executor_replay(name: str, args: Dict[str, Any]) -> Any:
            log.debug(f"[Replay Run] Intercepting tool call: {name}")
            result = self._find_matching_tool_call_in_trace(name, args, golden_trace)
            if result is not None:
                log.info(f"[Replay Run] Replaying result for {name} from trace.")
                # Need to update the agent's *internal* state tracking as if the tool ran
                # This relies on the tool functions updating the global state correctly.
                # We might need to manually update _last_search_call/_last_booking_call here.
                # For now, assume the assertion checks the agent's *output*, not internal state directly.
                # Or, we rely on the fact that get_last_... is called *after* interact finishes.
                # Let's manually update the state tracking here for consistency.
                global _last_search_call, _last_booking_call  # Access globals from tools.py
                if name == "search_flights":
                    _last_search_call = {"args": args, "result": result}
                elif name == "book_flight":
                    _last_booking_call = {"args": args, "result": result}
                return result
            else:
                raise EvalToolMismatchError(
                    f"Agent tried to call tool '{name}' with args {args}, "
                    f"but no matching call was found in the golden trace."
                )

        agent.set_tool_executor(tool_executor_replay)

        # --- Reset Agent and State ---
        agent.history = []  # Clear history
        try:
            # Reset tool state tracking at the beginning of evaluation
            from agent.tools import reset_tool_states

            reset_tool_states()
        except ImportError:
            log.warning(
                "Could not import and call reset_tool_states(). Tool state might persist."
            )

        agent_turn_history: List[AgentTurnData] = []  # For assertion evaluation

        # --- Get Initial User Input ---
        initial_user_input: Optional[str] = None
        if (
            golden_trace
            and isinstance(golden_trace[0], dict)
            and golden_trace[0].get("type") == "user"
        ):
            initial_user_input = golden_trace[0].get("text")
            if not isinstance(initial_user_input, str):
                log.warning(
                    f"Initial user turn text is not a string: {initial_user_input}. Treating as missing."
                )
                initial_user_input = None

        if not initial_user_input:
            log.error(
                "Cannot start evaluation: Golden trace is empty, doesn't start with a user turn, or initial text is invalid."
            )
            return {
                "goal": goal_description,
                "outcome_passed": False,
                "trajectory_quality": 0.0,
                "tool_calls": 0,
                "error": "Missing or invalid initial UserTurn in trace.",
                "details": [],
            }

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
            if "[Simulation Error" in user_input:
                log.warning(
                    f"Ending conversation loop due to simulation error on turn {current_turn_index}."
                )
                break

            # Agent interacts (handles internal function calls now)
            # The tool_executor configured above handles replay/execution
            agent_response_text = agent.interact(user_input)

            # Capture tool state *after* the interact call using the getters
            current_tool_states: Dict[str, Optional[ToolCallState]] = {}
            search_state = agent.get_last_search_call_details()
            book_state = agent.get_last_booking_call_details()
            turn_tool_calls = 0  # Tools called *in this turn*
            if search_state:
                if isinstance(search_state, dict):
                    current_tool_states["search_flights"] = ToolCallState(
                        **search_state
                    )
                    turn_tool_calls += 1
                else:
                    log.warning(f"Unexpected format for search_state: {search_state}")
            if book_state:
                if isinstance(book_state, dict):
                    current_tool_states["book_flight"] = ToolCallState(**book_state)
                    turn_tool_calls += 1
                else:
                    log.warning(f"Unexpected format for book_state: {book_state}")

            total_tool_calls += turn_tool_calls

            # Record turn data for assertions
            turn_data = AgentTurnData(
                turn_index=current_turn_index,
                user_input=user_input,
                agent_response_text=agent_response_text,
                tool_states=current_tool_states,  # State *after* the turn
            )
            agent_turn_history.append(turn_data)

            # Check for conversation end conditions
            if (
                agent_response_text is None
                or "[No Agent Response Found]" in agent_response_text
                or "Sorry, an error occurred" in agent_response_text
                or "[Agent provided no response]" in agent_response_text
            ):
                log.warning(
                    f"Ending conversation loop due to missing or error in agent response on turn {current_turn_index}."
                )
                break

            # --- Determine Next User Input ---
            if simulate_user:
                user_input = self._simulate_user_turn(
                    goal_description, agent.get_full_history()
                )
                # Check if simulated user seems finished
                if not user_input:
                    log.info("Simulated user seems finished. Ending conversation loop.")
                    # Add final user utterance for context in assertions
                    final_turn_data = AgentTurnData(
                        turn_index=current_turn_index + 1,
                        user_input=user_input,
                        agent_response_text=None,
                        tool_states={},
                    )
                    agent_turn_history.append(final_turn_data)
                    break
            else:
                # Get next user input from golden trace
                trace_index += 1  # Move past the user input we just used
                user_input = None
                # Find the *next* user turn, skipping agent/tool steps
                while trace_index < len(golden_trace):
                    step_dict = golden_trace[trace_index]
                    if isinstance(step_dict, dict) and step_dict.get("type") == "user":
                        user_input = step_dict.get("text")
                        if isinstance(user_input, str):
                            print(
                                colored(f"\nUser (from trace): {user_input}", "green")
                            )
                            break  # Found next user input
                        else:
                            log.warning(
                                f"User turn dict at index {trace_index} has invalid 'text'. Skipping."
                            )
                            user_input = (
                                None  # Reset to ensure loop continues searching
                            )
                    trace_index += 1  # Move to the next step in the trace

                if user_input is None:
                    log.info(
                        "No further user turn found in golden trace. Ending conversation loop."
                    )
                    break  # End loop if no more user input in trace

        # --- Evaluate Assertions ---
        log.info(
            f"--- Evaluating {len(assertions)} LLM Assertions Against Full Trace ({len(agent_turn_history)} recorded turns) ---"
        )
        assertion_results: List[AssertionResult] = []
        outcome_passed: Optional[bool] = None
        trajectory_checks_passed = 0
        trajectory_checks_total = 0

        if not agent_turn_history:
            log.error("Evaluation cannot proceed: No agent turns were recorded.")
            return {
                "goal": goal_description,
                "outcome_passed": False,
                "trajectory_quality": 0.0,
                "tool_calls": total_tool_calls,
                "error": "No agent turns recorded during execution.",
                "details": [],
            }

        for assertion in assertions:
            log.info(f"Evaluating assertion: {assertion.name}")
            try:
                result = assertion.evaluate(
                    trace=agent_turn_history,
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
                    outcome_passed = (
                        False  # Mark outcome as failed if the check itself errors
                    )

        # Determine final outcome
        if outcome_passed is None:
            log.warning(
                "Evaluation completed, but no assertion was marked as the outcome check (is_outcome_check=True) or the check errored."
            )
            final_outcome_passed = (
                False  # Default to False if no outcome check defined/run
            )
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
            # Add note to results?

        log.info(
            f"Evaluation finished. Outcome: {'PASSED' if final_outcome_passed else 'FAILED'}, Trajectory: {trajectory_quality:.2%}, Tool Calls: {total_tool_calls}"
        )

        return {
            "goal": goal_description,
            "outcome_passed": final_outcome_passed,
            "trajectory_quality": trajectory_quality,
            "tool_calls": total_tool_calls,
            "details": assertion_results,
            "error": None,  # No error if we reached here
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
