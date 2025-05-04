from google.genai import types as genai_types
from google import genai
import argparse
import logging
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from termcolor import colored
from pydantic import ValidationError
import datetime

from agent.agent import FlightBookingAgent
from eval.evaluator import GeminiEvaluator, EvalToolMismatchError
from eval.schemas import (
    TestCaseModel,
    LLMCheckAssertionModel,  # Import assertion model
)
from eval.assertion_types import LLMCheckAssertion
from typing import List, Optional, Dict, Any, Tuple  # Added Tuple

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    logging.error(
        "FATAL: GOOGLE_API_KEY not found in environment variables or .env file."
    )
    exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


# --- Trace Conversion and Generation Logic ---


def generate_goal_and_assertions(
    formatted_trace_str: list[genai_types.Content],  # Updated type hint
    initial_state: Dict[str, Any],
    generation_model_name: str = "gemini-2.5-flash-preview-04-17",  # Use a powerful model for this
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Uses an LLM to generate a goal description and assertions based on the conversation trace.
    """
    log.info(
        f"Attempting to generate goal and assertions using model: {generation_model_name}"
    )

    # Prepare the prompt
    initial_state_str = json.dumps(initial_state, indent=2)
    prompt = f"""You are an expert test case designer for AI agents specialized in flight booking.
Your task is to analyze the following flight booking conversation and generate a concise goal description and a set of relevant test assertions based *only* on this specific interaction.

Initial Agent State (e.g., the date the conversation started):
```json
{initial_state_str}
```

Conversation History:
--- HISTORY START ---
{formatted_trace_str}
--- HISTORY END ---

Instructions:
1.  **Goal Description:** A first person account (i.e. speaking from the user's perspective) of what they wanted to accomplish, baed on this conversation. Be specific about origin, destination, dates, and any key constraints mentioned (e.g., cheapest, specific airline).
2.  **Assertions:** Generate a list of 3-5 key assertions to verify the agent's performance *within this specific trace*. Each assertion must be a dictionary with the following keys:
    *   `name`: A short, descriptive CamelCase name (e.g., "CorrectDateInterpretation", "OfferedFlightOptions", "BookedCorrectFlight").
    *   `description`: A brief explanation of what the assertion checks *in the context of this trace*.
    *   `prompt_template`: A specific question or instruction for *another* LLM to evaluate based *only* on the conversation history provided above. This template MUST ask a specific YES/NO question about the agent's behavior or the conversation outcome *as observed in this trace*. It MUST incorporate relevant details (like specific dates, flight IDs, locations mentioned in *this* trace) directly into the question itself. Do *not* use placeholders like `{{date}}`. Refer explicitly to the initial state or specific turns if necessary (e.g., "Given the initial state date was {initial_state.get('current_date', 'YYYY-MM-DD')}, did the agent correctly search for flights on the absolute date YYYY-MM-DD when the user asked for 'relative_term'?").
    *   `expected_response`: Should be "YES", as the assertion should describe correct behavior *observed* in this trace. If a step clearly failed in the trace (e.g., booking tool failed), an assertion could check *if the agent reported the failure* (expected: YES).
    *   `is_outcome_check`: Set to `true` for the single assertion that best represents the successful completion of the user's *apparent primary goal* in this trace (e.g., booking confirmed with ID, search results provided if booking wasn't requested/completed). Set to `false` for intermediate checks or if the primary goal wasn't achieved. Only one assertion should have `is_outcome_check: true`.

Output Format:
Provide your response *only* as a single, valid JSON object containing two keys: "goal_description" (string) and "assertions" (list of assertion objects as described above). Do not include any introductory text, explanations, or markdown formatting outside the JSON structure.

--- EXAMPLE 1 START ---
Input Initial State:
  {{
    "current_date": "2024-10-26"
  }}

Input Conversation History:
  User: book a flight from SFO to NYC for tomorrow.
  Agent: Okay, I can help with that. Searching for flights from SFO to JFK for tomorrow, October 27th, 2024.
  Tool Call: search_flights(args={{"origin": "SFO", "destination": "JFK", "departure_date": "2024-10-27"}})
  Tool Result: [{{"flight_id": "UA456", "airline": "UA", "departure_time": "09:15", "arrival_time": "17:30", "price": 420}}, {{"flight_id": "AA123", "airline": "AA", "departure_time": "11:00", "arrival_time": "19:15", "price": 395}}]
  Agent: I found a couple of flights for tomorrow, October 27th. UA456 departs at 9:15 AM for $420, and AA123 departs at 11:00 AM for $395. Do either of those work for you?
  User: book AA123
  Agent: Alright, booking flight AA123 from SFO to JFK for tomorrow, October 27th.
  Tool Call: book_flight(args={{"flight_id": "AA123"}})
  Tool Result: {{"booking_id": "BK78910", "status": "confirmed", "message": "Flight AA123 booked successfully."}}
  Agent: Great! Your flight AA123 is confirmed for tomorrow, October 27th. Your booking ID is BK78910. Anything else?
  User: no

Output JSON:
  {{
    "goal_description": "Book the cheapest flight from SFO to JFK for tomorrow.",
    "assertions": [
      {{
        "name": "CorrectDateInterpretation",
        "description": "Checks if the agent correctly interpreted 'tomorrow' based on the initial state's current_date (2024-10-26) and used the absolute date 2024-10-27 in the search.",
        "prompt_template": "Based on the conversation and knowing the initial current date was 2024-10-26, did the agent correctly use the absolute date 2024-10-27 in its first 'search_flights' tool call args?",
        "expected_response": "YES",
        "is_outcome_check": false
      }},
      {{
        "name": "OfferedFlightOptions",
        "description": "Checks if the agent offered specific flight options (UA456, AA123) after searching.",
        "prompt_template": "Did the agent's response after the first 'search_flights' tool call present the specific flight options UA456 and AA123 found in the tool result?",
        "expected_response": "YES",
        "is_outcome_check": false
      }},
      {{
        "name": "CorrectFlightBooked",
        "description": "Checks if the agent attempted to book the specific flight the user selected (AA123).",
        "prompt_template": "Did the agent call the 'book_flight' tool with the exact flight ID 'AA123' after the user explicitly requested it?",
        "expected_response": "YES",
        "is_outcome_check": false
      }},
      {{
        "name": "BookingConfirmedWithID",
        "description": "Checks if the agent confirmed the booking successfully and provided the booking ID from the tool result.",
        "prompt_template": "Did the agent's final response state that the booking for flight AA123 was confirmed and include the booking ID 'BK78910'?",
        "expected_response": "YES",
        "is_outcome_check": true
      }}
    ]
  }}
--- EXAMPLE 1 END ---

--- EXAMPLE 2 START ---

Input Initial State:
  {{
    "current_date": "2024-11-15"
  }}

Input Conversation History:
  User: Any flights from London Heathrow to Paris CDG 5 days from now?
  Agent: Sure, let me check flights from LHR to CDG for November 20th, 2024.
  Tool Call: search_flights(args={{"origin": "LHR", "destination": "CDG", "departure_date": "2024-11-20"}})
  Tool Result: [{{"flight_id": "BA308", "airline": "BA", "departure_time": "10:00", "arrival_time": "12:15", "price": 150}}, {{"flight_id": "AF101", "airline": "AF", "departure_time": "14:30", "arrival_time": "16:45", "price": 165}}]
  Agent: Yes, I found a couple: British Airways BA308 for £150 and Air France AF101 for £165.
  User: Okay thanks.

Output JSON:
  {{
    "goal_description": "lookup flights from London Heathrow to Paris CDG for 5 days in the future.",
    "assertions": [
      {{
        "name": "CorrectSearchParameters",
        "description": "Checks if the agent used the correct origin (LHR), destination (CDG), and specific date (2024-11-20) provided by the user in the 'search_flights' tool call.",
        "prompt_template": "Did the agent's 'search_flights' tool call use origin 'LHR', destination 'CDG', and departure_date '2024-11-20' exactly as specified in the first user turn?",
        "expected_response": "YES",
        "is_outcome_check": false
      }},
      {{
        "name": "PresentedSearchResults",
        "description": "Checks if the agent presented the specific flight options found (BA308 and AF101) to the user after the search.",
        "prompt_template": "Did the agent's response after the 'search_flights' tool call mention the specific flight options found, including BA308 and AF101?",
        "expected_response": "YES",
        "is_outcome_check": true
      }},
      {{
        "name": "NoBookingAttempt",
        "description": "Checks that the agent did not attempt to book a flight, as the user did not request it in this short conversation.",
        "prompt_template": "Did the agent avoid calling the 'book_flight' tool during this conversation?",
        "expected_response": "YES",
        "is_outcome_check": false
      }}
    ]
  }}
--- EXAMPLE 2 END ---

Now, analyze the actual conversation history provided at the beginning and generate the JSON output for it.

"""

    try:
        # Use the globally configured client
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=generation_model_name, contents=prompt
        )

        if not response.candidates:
            log.error(
                f"Goal/Assertion generation failed: No candidates returned. Feedback: {response.prompt_feedback}"
            )
            return None, []

        # Extract JSON - response.text should contain the JSON string
        response_text = response.text.strip()
        log.debug(f"Raw LLM response for goal/assertions:\n{response_text}")

        # Clean potential markdown fences
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse the JSON
        generated_data = json.loads(response_text)

        # Validate basic structure
        goal = generated_data.get("goal_description")
        assertions = generated_data.get("assertions", [])

        if not isinstance(goal, str) or not isinstance(assertions, list):
            raise ValueError(
                "LLM response JSON does not match expected structure (goal_description: str, assertions: list)."
            )

        # Basic validation of assertion structure (can be enhanced)
        validated_assertions = []
        for i, assert_data in enumerate(assertions):
            if isinstance(assert_data, dict) and all(
                k in assert_data
                for k in [
                    "name",
                    "description",
                    "prompt_template",
                    "expected_response",
                    "is_outcome_check",
                ]
            ):
                # Further validation could check types here
                validated_assertions.append(assert_data)
            else:
                log.warning(
                    f"Skipping invalid assertion structure at index {i} in LLM response: {assert_data}"
                )

        log.info(
            f"Successfully generated goal: '{goal}' and {len(validated_assertions)} assertions."
        )
        return goal, validated_assertions

    except json.JSONDecodeError as e:
        log.error(f"Failed to parse JSON response from LLM for goal/assertions: {e}")
        log.error(f"LLM Raw Response was:\n{response_text}")
        return None, []
    except Exception as e:
        log.exception(
            f"An unexpected error occurred during goal/assertion generation: {e}"
        )
        # Log the full traceback for debugging
        # traceback.print_exc() # Uncomment if needed, log.exception usually includes it
        return None, []


def save_interactive_trace(
    initial_state: Dict[str, Any],
    history: list[genai_types.Content],  # Updated type hint
):
    """Saves the interactive session trace, attempting to auto-generate goal/assertions."""
    log.info("Saving interactive trace...")
    trace_dir = Path(__file__).parent / "eval" / "test_cases" / "unvalidated"
    trace_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"interactive_trace_{timestamp}.json"
    filepath = trace_dir / filename

    try:
        generated_goal, generated_assertions = generate_goal_and_assertions(
            history, initial_state
        )
        # Use generated goal if available, otherwise fallback
        final_goal = generated_goal or "[Error: Failed to generate goal]"

        final_assertions = generated_assertions
        if generated_assertions:
            log.info(
                f"Using {len(generated_assertions)} automatically generated assertions."
            )
        else:
            log.warning(
                "No assertions were generated, saving trace without assertions."
            )

        # Validate generated assertions against the Pydantic model (optional but good practice)
        validated_assertion_models = []
        for assertion_dict in final_assertions:
            try:
                # Create the Pydantic model instance to validate
                LLMCheckAssertionModel(**assertion_dict)
                validated_assertion_models.append(
                    assertion_dict
                )  # Keep as dict for saving
            except ValidationError as e:
                log.warning(
                    f"Generated assertion failed Pydantic validation, skipping: {assertion_dict.get('name', 'N/A')}\nError: {e}"
                )

        test_case_data = TestCaseModel(
            goal_description=final_goal,
            initial_state=initial_state,
            golden_trace=history,
            assertions=[
                LLMCheckAssertionModel(**a) for a in validated_assertion_models
            ],
        )

        with open(filepath, "w") as f:
            # Use .dict() with exclude_unset=True for cleaner output if needed
            json.dump(test_case_data.dict(exclude_unset=True), f, indent=2)
        log.info(f"Interactive trace saved successfully to: {filepath}")
        if generated_goal or validated_assertion_models:
            print(
                colored(
                    f"Trace saved with auto-generated goal/assertions: {filepath}",
                    "cyan",
                )
            )
        else:
            print(
                colored(
                    f"Trace saved (generation failed/skipped): {filepath}", "yellow"
                )
            )

    except Exception as e:
        log.exception(f"Failed to save interactive trace to {filepath}: {e}")
        print(colored(f"Error saving trace: {e}", "red"))


# --- Main Execution Modes ---


def run_interactive_agent():
    """Runs the agent in interactive chat mode."""
    log.info("Starting interactive agent...")
    try:
        # Create default state for interactive mode
        interactive_state = {"current_date": datetime.date.today().isoformat()}
        agent = FlightBookingAgent(
            api_key=GEMINI_API_KEY, initial_state=interactive_state
        )

        date_info = f"(Assuming today is {interactive_state['current_date']})"
        print(colored(date_info, "cyan"))

        while True:
            user_input = input(colored("You: ", "green"))
            if user_input.lower() in ["quit", "exit", "bye"]:
                print(colored("Agent: Goodbye!", "blue"))
                break
            if not user_input:
                continue

            response = agent.interact(user_input)
            print(colored(f"Agent: {response}", "blue"))

    except Exception as e:
        logging.exception("An error occurred during interactive session.")
        print(colored(f"Error: {e}", "red"))
    finally:
        if "agent" in locals():
            final_history = agent.get_full_history()
            # Pass the user's initial note as a fallback goal
            save_interactive_trace(interactive_state, final_history)
        else:
            log.warning("Agent not initialized, cannot save trace.")


# --- Load Test Case (Unchanged) ---
def load_test_case(test_case_name: str) -> Optional[TestCaseModel]:
    """Loads a test case from its JSON file."""
    test_case_dir = Path(__file__).parent / "eval" / "test_cases"
    file_path = test_case_dir / f"{test_case_name}.json"
    if not file_path.is_file():
        unvalidated_path = (
            Path(__file__).parent
            / "eval"
            / "test_cases"
            / "unvalidated"
            / f"{test_case_name}.json"
        )
        if unvalidated_path.is_file():
            file_path = unvalidated_path
            log.info(f"Loading test case from unvalidated folder: {file_path}")
        else:
            log.error(
                f"Test case file not found in primary or unvalidated directory: {test_case_name}"
            )
            available_cases = [f.stem for f in test_case_dir.glob("*.json")] + [
                f"unvalidated/{f.stem}"
                for f in (
                    Path(__file__).parent / "eval" / "test_cases" / "unvalidated"
                ).glob("*.json")
            ]
            print(colored(f"Error: Test case '{test_case_name}' not found.", "red"))
            if available_cases:
                print(f"Available cases: {', '.join(available_cases)}")
            return None

    try:
        test_case_model = TestCaseModel.parse_file(file_path)
        log.info(f"Successfully loaded test case: {test_case_name} from {file_path}")
        return test_case_model
    except ValidationError as e:
        log.exception(
            f"Validation error loading test case '{test_case_name}' from {file_path}: {e}"
        )
        print(
            colored(
                f"Error: Invalid format in test case file '{file_path}'.\n{e}", "red"
            )
        )
        return None
    except json.JSONDecodeError as e:
        log.exception(
            f"JSON decoding error loading test case '{test_case_name}' from {file_path}: {e}"
        )
        print(
            colored(f"Error: Invalid JSON in test case file '{file_path}'.\n{e}", "red")
        )
        return None


# --- Run Evaluation (Small modification to handle assertion loading) ---
def run_evaluation(test_case_name: str):
    """Runs the evaluation for a specific test case loaded from JSON."""
    log.info(
        f"Starting evaluation for test case: {test_case_name}"
    )

    test_case_data = load_test_case(test_case_name)
    if not test_case_data:
        return

    goal_desc = test_case_data.goal_description
    initial_agent_state = test_case_data.initial_state or {}

    assertions: List[LLMCheckAssertion] = []
    # Directly use the assertion models loaded from the TestCaseModel
    for assertion_model in test_case_data.assertions:
        try:
            # The model already has the correct fields
            assertions.append(
                LLMCheckAssertion(
                    name=assertion_model.name,
                    prompt_template=assertion_model.prompt_template,
                    expected_response=assertion_model.expected_response,
                    is_outcome_check=assertion_model.is_outcome_check,
                )
            )
        except Exception as e:
            log.error(
                f"Failed to instantiate LLMCheckAssertion for '{assertion_model.name}': {e}"
            )
            print(
                colored(
                    f"Error creating assertion object '{assertion_model.name}'. Check definition in JSON.",
                    "red",
                )
            )
            return

    if not assertions:
        print(
            colored(
                f"Warning: No assertions found or loaded for test case '{test_case_name}'. Running trace execution only.",
                "yellow",
            )
        )
        # Allow running without assertions if desired

    try:
        agent = FlightBookingAgent(
            api_key=GEMINI_API_KEY, initial_state=initial_agent_state
        )
        evaluator = GeminiEvaluator(api_key=GEMINI_API_KEY)

        results = evaluator.evaluate_trace(
            agent=agent,
            golden_trace=test_case_data.golden_trace,
            assertions=assertions,
            goal_description=goal_desc,
            agent_tool_map=agent.tool_function_map,
        )
        evaluator.display_results(results)

    except EvalToolMismatchError as e:
        log.error(f"Evaluation failed due to tool mismatch: {e}")
        print(
            colored(
                f"\nEvaluation Error: Tool call mismatch in non-simulated run.\n{e}",
                "red",
            )
        )
    except Exception as e:
        logging.exception(f"An error occurred during evaluation of {test_case_name}.")
        print(colored(f"Evaluation Error: {e}", "red"))


# --- Main Guard (Unchanged) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Flight Booking Agent or Evaluation"
    )
    parser.add_argument(
        "mode",
        choices=["interactive", "eval"],
        help="Mode to run: 'interactive' for chat, 'eval' for evaluation.",
    )
    parser.add_argument(
        "--test_case",
        type=str,
        default=None,
        help="Name of the test case JSON file (without .json extension) to run in 'eval' mode (e.g., simple_booking, unvalidated/interactive_trace_...).",
    )
    args = parser.parse_args()

    if args.mode == "interactive":
        run_interactive_agent()
    elif args.mode == "eval":
        if not args.test_case:
            print(
                colored(
                    "Error: --test_case argument is required for 'eval' mode.", "red"
                )
            )
            test_case_dir = Path(__file__).parent / "eval" / "test_cases"
            available_cases = [f.stem for f in test_case_dir.glob("*.json")] + [
                f"unvalidated/{f.stem}"
                for f in (
                    Path(__file__).parent / "eval" / "test_cases" / "unvalidated"
                ).glob("*.json")
            ]
            if available_cases:
                print(f"Available cases: {', '.join(available_cases)}")
            exit(1)
        run_evaluation(args.test_case)
