import argparse
import logging
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from termcolor import colored
from pydantic import ValidationError

from agent.agent import FlightBookingAgent
from eval.evaluator import GeminiEvaluator
from eval.schemas import TestCaseModel
from eval.assertion_types import LLMCheckAssertion
from typing import List, Optional

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


def run_interactive_agent():
    """Runs the agent in interactive chat mode."""
    log.info("Starting interactive agent...")
    try:
        agent = FlightBookingAgent(api_key=GEMINI_API_KEY)
        print(
            colored(
                "Agent: Hello! How can I help you with your flight booking today?",
                "blue",
            )
        )
        while True:
            user_input = input(colored("You: ", "green"))
            if user_input.lower() in ["quit", "exit", "bye"]:
                print(colored("Agent: Goodbye!", "blue"))
                break
            if not user_input:
                continue
            agent.interact(user_input)
    except Exception as e:
        logging.exception("An error occurred during interactive session.")
        print(colored(f"Error: {e}", "red"))


def load_test_case(test_case_name: str) -> Optional[TestCaseModel]:
    """Loads a test case from its JSON file."""
    test_case_dir = Path(__file__).parent / "eval" / "test_cases"
    file_path = test_case_dir / f"{test_case_name}.json"
    if not file_path.is_file():
        log.error(f"Test case file not found: {file_path}")
        available_cases = [f.stem for f in test_case_dir.glob("*.json")]
        print(colored(f"Error: Test case '{test_case_name}' not found.", "red"))
        print(f"Available cases: {', '.join(available_cases)}")
        return None
    try:
        test_case_model = TestCaseModel.parse_file(file_path)
        log.info(f"Successfully loaded test case: {test_case_name}")
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


def run_evaluation(test_case_name: str, simulate_user: bool):
    """Runs the evaluation for a specific test case loaded from JSON."""
    log.info(
        f"Starting evaluation for test case: {test_case_name} (Simulate User: {simulate_user})"
    )

    test_case_data = load_test_case(test_case_name)
    if not test_case_data:
        return

    goal_desc = test_case_data.goal_description

    golden_trace_steps = [step.dict() for step in test_case_data.golden_trace]

    assertions: List[LLMCheckAssertion] = []
    for assertion_model in test_case_data.assertions:
        try:

            assertions.append(LLMCheckAssertion(**assertion_model.dict()))
        except Exception as e:
            log.error(
                f"Failed to instantiate LLMCheckAssertion for '{assertion_model.name}': {e}"
            )
            print(
                colored(
                    f"Error creating assertion object '{assertion_model.name}'. Check definition.",
                    "red",
                )
            )
            return

    if not assertions:
        print(
            colored(
                f"Error: No assertions found or loaded for test case '{test_case_name}'.",
                "red",
            )
        )
        return

    try:
        agent = FlightBookingAgent(api_key=GEMINI_API_KEY)
        evaluator = GeminiEvaluator(api_key=GEMINI_API_KEY)

        results = evaluator.evaluate_trace(
            agent=agent,
            golden_trace=golden_trace_steps,
            assertions=assertions,
            goal_description=goal_desc,
            simulate_user=simulate_user,
        )
        evaluator.display_results(results)
    except Exception as e:
        logging.exception(f"An error occurred during evaluation of {test_case_name}.")
        print(colored(f"Evaluation Error: {e}", "red"))


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
        help="Name of the test case JSON file (without .json extension) to run in 'eval' mode (e.g., simple_booking, clarification_booking).",
    )
    parser.add_argument(
        "--simulate_user",
        action="store_true",
        help="If set, use an LLM to simulate user responses during evaluation instead of golden trace.",
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
            available_cases = [f.stem for f in test_case_dir.glob("*.json")]
            if available_cases:
                print(f"Available cases: {', '.join(available_cases)}")
            exit(1)
        run_evaluation(args.test_case, args.simulate_user)
