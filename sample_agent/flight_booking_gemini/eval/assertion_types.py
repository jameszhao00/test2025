import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from google.genai import Client as GenAIClient  # Alias for clarity
from google.genai import types as genai_types  # Import types

log = logging.getLogger(__name__)


# --- Runtime Data Structures --- (Keep existing dataclasses: ToolCallState, AgentTurnData)
# NOTE: AgentTurnData is no longer the primary input for assertion evaluation,
# but kept in case it's useful elsewhere or for future refactoring.
@dataclass
class ToolCallState:
    """Represents the state of a tool call captured during a turn."""

    args: Dict[str, Any]
    result: Any


# --- Assertion Result --- (Keep existing dataclass: AssertionResult)
@dataclass
class AssertionResult:
    """Result of evaluating an assertion."""

    name: str
    passed: bool
    details: str = ""
    is_outcome_check: bool = False  # Flag to identify the main outcome assertion


# --- Assertion Class (Now only LLM-based) ---


class LLMCheckAssertion:
    """Uses an LLM to evaluate a condition based on the trace."""

    # Define the standard history preamble here

    def __init__(
        self,
        name: str,
        prompt_template: str,  # This template now ONLY contains the specific question/instruction
        expected_response: str = "YES",
        is_outcome_check: bool = False,
    ):
        self.name = name
        # The prompt_template from the JSON should *not* include the history preamble anymore.
        # It should only be the specific question/instruction part.
        self.specific_prompt_template = prompt_template
        self.expected_response = expected_response.upper()  # Normalize expected
        self.is_outcome_check = (
            is_outcome_check  # Mark if this defines the overall outcome
        )

    def _format_tool_interactions_for_prompt(
        self, agent_history: List[tuple[str, genai_types.Part]]
    ) -> str:
        """Formats *only* the tool interactions from raw history."""
        formatted = []
        # Note: Turn index isn't directly available here, format without it.
        for role, part in agent_history:
            if (
                role == "model"
                and hasattr(part, "function_call")
                and part.function_call
            ):
                fc = part.function_call
                args_dict = dict(fc.args) if hasattr(fc, "args") else {}
                formatted.append(f"Tool Call: {fc.name}(args={args_dict})")
            # Function responses are now role 'user' in the history based on SDK flow
            elif (
                role == "user"
                and hasattr(part, "function_response")
                and part.function_response
            ):
                fr = part.function_response
                result_data = "[No Result]"
                if hasattr(fr, "response") and isinstance(fr.response, dict):
                    result_data = fr.response.get("result", "[Result Key Missing]")
                elif hasattr(fr, "response"):
                    result_data = str(fr.response)

                result_str = str(result_data)
                if len(result_str) > 150:
                    result_str = result_str[:150] + "..."
                formatted.append(f"Tool Result ({fr.name}): {result_str}")

        if not formatted:
            return "[No tool interactions recorded in trace]"
        return "\n".join(formatted)

    def _run_llm_check(
        self, prompt: str, llm_client: GenAIClient, eval_model_name: str
    ) -> str:
        """Runs the LLM check."""
        log.debug(f"Running LLM Check for assertion '{self.name}'. Prompt:\n{prompt}")
        try:
            response = llm_client.models.generate_content(
                model=eval_model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.0  # Use low temp for deterministic checks
                ),
                # safety_settings=...
            )
            if not response.candidates:
                log.error(
                    f"LLM check '{self.name}' failed: No candidates returned. Feedback: {response.prompt_feedback}"
                )
                return "[LLM_NO_CANDIDATES]"

            llm_answer = "".join(
                part.text
                for part in response.candidates[0].content.parts
                if hasattr(part, "text")
            )
            # Clean up potential markdown, list markers, etc.
            llm_answer = (
                llm_answer.strip()
                .upper()
                .removeprefix("YES")
                .removeprefix("NO")
                .strip(" .,:*-")
            )
            # Prioritize YES/NO at the beginning
            if llm_answer.startswith("YES"):
                llm_answer = "YES"
            elif llm_answer.startswith("NO"):
                llm_answer = "NO"
            # If only YES/NO remains, use it, otherwise keep the cleaned response
            if llm_answer not in ["YES", "NO"]:
                llm_answer = (
                    "".join(
                        part.text
                        for part in response.candidates[0].content.parts
                        if hasattr(part, "text")
                    )
                    .strip()
                    .upper()
                )  # Re-extract if cleaning was too aggressive

            log.debug(f"LLM Check '{self.name}' Response: '{llm_answer}'")
            return llm_answer
        except Exception as e:
            log.exception(f"LLM check '{self.name}' failed with exception: {e}")
            return f"[LLM_EXCEPTION: {type(e).__name__}]"

    def evaluate(
        self,
        agent_history: List[genai_types.Content],  # Changed input
        llm_client: GenAIClient,
        eval_model_name: str,
    ) -> AssertionResult:
        """Evaluates the assertion against the agent's raw history using an LLM."""
        if not llm_client or not eval_model_name:
            return AssertionResult(
                name=self.name,
                passed=False,
                details="LLM client/model not available.",
                is_outcome_check=self.is_outcome_check,
            )
        full_prompt = f"""Consider the following conversation history:
--- HISTORY START ---
{agent_history}
--- HISTORY END ---

Based *only* on the conversation history provided, answer the following question with 'YES' or 'NO'. 
If the answer is NO, optionally provide a brief reason after 'NO:'.

Question:{self.specific_prompt_template}"""
        llm_answer = self._run_llm_check(full_prompt, llm_client, eval_model_name)
        passed = llm_answer.startswith(self.expected_response)
        details = ""
        if not passed:
            details = f"LLM check failed. Expected prefix '{self.expected_response}', Got '{llm_answer}'."

        return AssertionResult(
            name=self.name,
            passed=passed,
            details=details,
            is_outcome_check=self.is_outcome_check,
        )
