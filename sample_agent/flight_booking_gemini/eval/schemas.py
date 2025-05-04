# eval/schemas.py
from pydantic import BaseModel, Field
from typing import Any, Optional
from google.genai import types as genai_types
class LLMCheckAssertionModel(BaseModel):
    name: str
    prompt_template: str
    expected_response: str = "YES"
    is_outcome_check: bool = False

class TestCaseModel(BaseModel):
    goal_description: str
    initial_state: Optional[dict[str, Any]] = Field(
        default=None,
        description="Initial key-value state for the agent (e.g., current_date)."
    )
    golden_trace: list[genai_types.Content]
    assertions: list[LLMCheckAssertionModel]