from google.genai import types
import re
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types as genai_types
from termcolor import colored

from agent.agent import FlightBookingAgent


from eval.assertion_types import (
    LLMCheckAssertion,
    AssertionResult,
    AgentTurnData,
    ToolCallState,
)


log = logging.getLogger(__name__)


class GeminiEvaluator:
    def __init__(
        self, api_key: str, eval_model_name: str = "gemini-2.5-flash-preview-04-17"
    ):
        if not api_key:
            raise ValueError("API key must be provided for evaluator.")

        try:

            self.client = genai.Client(api_key=api_key)

        except Exception as e:
            log.error(f"Failed to initialize Gemini Client: {e}")
            raise ValueError(
                f"Failed to initialize Gemini Client. Check API key and permissions. Error: {e}"
            )

        self.eval_model_name = eval_model_name
        log.info(f"Evaluator initialized with model: {self.eval_model_name}")

    def _format_history_for_prompt(self, history: List[Dict[str, Any]]) -> str:
        """Formats agent's internal history for the user simulator prompt."""
        formatted = []
        for turn_dict in history:
            role = turn_dict.get("role", "unknown").capitalize()

            text_content = ""
            if "parts" in turn_dict and isinstance(turn_dict["parts"], list):
                text_content = "".join(
                    p.get("text", "") for p in turn_dict["parts"] if isinstance(p, dict)
                )
            elif "text" in turn_dict:
                text_content = turn_dict["text"]

            if text_content:
                formatted.append(f"{role}: {text_content}")

        return "\n".join(formatted)

    def _simulate_user_turn(self, goal: str, history: List[Dict[str, Any]]) -> str:
        """Uses an LLM to simulate the user's next response."""
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

Your response:"""
        try:

            response = self.client.models.generate_content(
                model=self.eval_model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.7,
                    # thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            if response.candidates:

                simulated_response = "".join(
                    part.text
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "text")
                ).strip()

                simulated_response = re.sub(
                    r"^(User|You):\s*", "", simulated_response, flags=re.IGNORECASE
                ).strip()

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

    def evaluate_trace(
        self,
        agent: FlightBookingAgent,
        golden_trace: List[Dict[str, Any]],
        assertions: List[LLMCheckAssertion],
        goal_description: str,
        simulate_user: bool = False,
        max_turns: int = 15,
    ) -> Dict[str, Any]:
        """
        Runs agent, evaluates using LLM assertions, reports on facets.
        Accepts golden_trace as a list of dictionaries loaded via Pydantic.
        """
        log.info(
            f"Starting evaluation for goal: '{goal_description}' (Simulate User: {simulate_user})"
        )

        agent.history = []

        try:
            from agent.tools import reset_tool_states

            reset_tool_states()
        except ImportError:
            log.warning(
                "Could not import and call reset_tool_states(). Tool state might persist."
            )

        agent_turn_history: List[AgentTurnData] = []

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

        current_turn_index = 0
        user_input: Optional[str] = initial_user_input
        trace_index = 0
        total_tool_calls = 0

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

            agent_response_text = agent.interact(user_input)

            current_tool_states: Dict[str, Optional[ToolCallState]] = {}
            search_state = agent.get_last_search_call_details()
            book_state = agent.get_last_booking_call_details()
            turn_tool_calls = 0
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

            turn_data = AgentTurnData(
                turn_index=current_turn_index,
                user_input=user_input,
                agent_response_text=agent_response_text,
                tool_states=current_tool_states,
            )
            agent_turn_history.append(turn_data)

            if (
                agent_response_text is None
                or "[No Agent Response Found]" in agent_response_text
                or "Sorry, an error occurred" in agent_response_text
            ):
                log.warning(
                    f"Ending conversation loop due to missing or error in agent response on turn {current_turn_index}."
                )
                break

            if simulate_user:
                user_input = self._simulate_user_turn(
                    goal_description, agent.get_full_history()
                )

                if user_input.lower().strip().rstrip("!.") in [
                    "thanks",
                    "great thank you",
                    "thank you",
                    "ok thanks",
                    "perfect thanks",
                ]:
                    log.info("Simulated user seems finished. Ending conversation loop.")

                    final_turn_data = AgentTurnData(
                        turn_index=current_turn_index + 1,
                        user_input=user_input,
                        agent_response_text=None,
                        tool_states={},
                    )
                    agent_turn_history.append(final_turn_data)
                    break
            else:

                trace_index += 1
                user_input = None
                while trace_index < len(golden_trace):
                    step_dict = golden_trace[trace_index]
                    if isinstance(step_dict, dict) and step_dict.get("type") == "user":
                        user_input = step_dict.get("text")
                        if isinstance(user_input, str):
                            print(
                                colored(f"\nUser (from trace): {user_input}", "green")
                            )
                            break
                        else:
                            log.warning(
                                f"User turn dict at index {trace_index} has invalid 'text'. Skipping."
                            )
                            user_input = None

                    trace_index += 1

                if user_input is None:
                    log.info(
                        "No further user turn found in golden trace. Ending conversation loop."
                    )
                    break

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
                    llm_client=self.client,
                    eval_model_name=self.eval_model_name,
                )
                assertion_results.append(result)

                if result.is_outcome_check:

                    if outcome_passed is None:
                        outcome_passed = result.passed

                    elif not result.passed:
                        outcome_passed = False
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
                        description=assertion.description,
                        passed=False,
                        details=f"Evaluation failed with exception: {e}",
                        is_outcome_check=assertion.is_outcome_check,
                    )
                )

                if assertion.is_outcome_check and outcome_passed is None:
                    outcome_passed = False

        if outcome_passed is None:
            log.error(
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

            details: List[AssertionResult] = results.get("details", [])
            if details:
                print("\n--- Partial Assertion Results ---")

            return

        print("\n--- Facets ---")

        outcome_passed = results.get("outcome_passed", False)
        outcome_status = (
            colored("PASSED", "green") if outcome_passed else colored("FAILED", "red")
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

                print(f"    Desc: {check.description}")
                if not check.passed and check.details:

                    details_lines = check.details.split("\n")
                    print(f"    Details: {details_lines[0]}")
                    for line in details_lines[1:]:

                        print(f"             {line}")

        print("--- End Report ---")
