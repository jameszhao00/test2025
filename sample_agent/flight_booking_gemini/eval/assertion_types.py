# eval/assertion_types.py
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from google.genai import Client as GenAIClient  # Alias for clarity

log = logging.getLogger(__name__)

# --- Runtime Data Structures --- (Keep existing dataclasses: ToolCallState, AgentTurnData)
@dataclass
class ToolCallState:
    """Represents the state of a tool call captured during a turn."""
    args: Dict[str, Any]
    result: Any

@dataclass
class AgentTurnData:
    """Holds data captured for a single turn of the conversation."""
    turn_index: int
    user_input: Optional[str]
    agent_response_text: Optional[str]
    # Stores the state of tools *after* this turn's interaction completed
    tool_states: Dict[str, Optional[ToolCallState]] = field(default_factory=dict)


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
    HISTORY_PREAMBLE = "Consider the following conversation history:\n--- HISTORY START ---\n{history}\n--- HISTORY END ---\n\n"

    def __init__(
        self,
        name: str,
        prompt_template: str, # This template now ONLY contains the specific question/instruction
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

    def _format_conversation_history_for_prompt(self, trace: List[AgentTurnData]) -> str:
        """Formats the main conversation history (user/agent turns) for the prompt."""
        formatted = []
        for turn in trace:
            if turn.user_input:
                formatted.append(f"User: {turn.user_input}")
            # Include tool calls/results *within* the agent turn context
            if turn.agent_response_text:
                tool_info_lines = []
                for tool_name, state in turn.tool_states.items():
                    if state:
                        tool_info_lines.append(
                            f"  [Agent Tool Call: {tool_name} with args {state.args}]"
                        )
                        # Represent result concisely
                        result_repr = "[Result Omitted]" # Default
                        if isinstance(state.result, dict) and "status" in state.result:
                             result_repr = f"status={state.result.get('status')}"
                        elif isinstance(state.result, list):
                             result_repr = f"found {len(state.result)} items"
                        elif state.result is not None:
                             result_repr = str(state.result)[:100] # Truncate long results

                        tool_info_lines.append(
                            f"  [Agent Tool Result: {tool_name} -> {result_repr}]"
                        )

                agent_line = ""
                # Add tool info *before* the agent's text response for clarity
                if tool_info_lines:
                    agent_line += "\n".join(tool_info_lines) + "\n"
                agent_line += f"Agent: {turn.agent_response_text}"
                formatted.append(agent_line)

        return "\n".join(formatted)

    def _format_tool_interactions_for_prompt(self, trace: List[AgentTurnData]) -> str:
        """Formats *only* the tool interactions, potentially for a {tool_history} placeholder."""
        formatted = []
        for turn_index, turn in enumerate(trace):
            if turn.tool_states:
                for tool_name, state in turn.tool_states.items():
                     if state:
                        formatted.append(f"Turn {turn.turn_index} Tool Call: {tool_name}(args={state.args})")
                        # Represent result concisely
                        result_repr = "[Result Omitted]" # Default
                        if isinstance(state.result, dict) and "status" in state.result:
                             result_repr = f"status={state.result.get('status')}"
                        elif isinstance(state.result, list):
                             result_repr = f"found {len(state.result)} items"
                        elif state.result is not None:
                             result_repr = str(state.result)[:100] # Truncate long results
                        formatted.append(f"Turn {turn.turn_index} Tool Result: {result_repr}")
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
                # config=... # Consider adding generation config if needed (temp, top_p etc)
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
            llm_answer = llm_answer.strip().upper()
            log.debug(f"LLM Check '{self.name}' Response: '{llm_answer}'")
            return llm_answer
        except Exception as e:
            log.exception(f"LLM check '{self.name}' failed with exception: {e}")
            return f"[LLM_EXCEPTION: {type(e).__name__}]"

    def evaluate(
        self, trace: List[AgentTurnData], llm_client: GenAIClient, eval_model_name: str
    ) -> AssertionResult:
        """Evaluates the assertion against the trace using an LLM."""
        if not llm_client or not eval_model_name:
            return AssertionResult(
                name=self.name,
                passed=False,
                details="LLM client/model not available.",
                is_outcome_check=self.is_outcome_check,
            )

        # 1. Format the main conversation history
        formatted_conversation_history = self._format_conversation_history_for_prompt(trace)

        # 2. Create the history part of the prompt using the standard preamble
        history_prompt_part = self.HISTORY_PREAMBLE.format(history=formatted_conversation_history)

        # 3. Prepare keyword arguments for formatting the specific prompt template
        #    This allows the specific template to potentially use other placeholders.
        format_kwargs = {}

        # 4. Optional: Format tool interactions separately if '{tool_history}' placeholder is used
        #    in the specific_prompt_template.
        formatted_tool_interactions = self._format_tool_interactions_for_prompt(trace)
        format_kwargs['tool_history'] = formatted_tool_interactions
        # Add any other potential placeholders and their formatted values here
        # format_kwargs['goal_description'] = goal_description # If needed, pass goal from evaluator

        # 5. Format the specific question/instruction part
        try:
            # Use the template stored during __init__
            specific_question_part = self.specific_prompt_template.format(**format_kwargs)
        except KeyError as e:
            log.error(f"Assertion '{self.name}': Prompt template expects placeholder '{e}' which was not provided. Template: '{self.specific_prompt_template}'")
            return AssertionResult(
                name=self.name,
                passed=False,
                details=f"Prompt template formatting error: Missing key {e}. Check assertion definition.",
                is_outcome_check=self.is_outcome_check,
            )
        except Exception as e:
             log.exception(f"Assertion '{self.name}': Error formatting specific prompt template: {e}")
             return AssertionResult(
                name=self.name,
                passed=False,
                details=f"Prompt template formatting error: {e}. Template: '{self.specific_prompt_template}'",
                is_outcome_check=self.is_outcome_check,
            )


        # 6. Combine the history preamble and the specific formatted question
        full_prompt = f"{history_prompt_part}{specific_question_part}"

        # 7. Run the LLM check with the combined prompt
        llm_answer = self._run_llm_check(full_prompt, llm_client, eval_model_name)

        # 8. Determine pass/fail based on the response
        passed = llm_answer.startswith(self.expected_response)

        details = ""
        if not passed:
            # Make details more informative, include the full prompt for debugging
            details = (f"LLM check failed. Expected prefix '{self.expected_response}', Got '{llm_answer}'.\n")


        return AssertionResult(
            name=self.name,
            passed=passed,
            details=details,
            is_outcome_check=self.is_outcome_check,
        )