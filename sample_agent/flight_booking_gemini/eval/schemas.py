# eval/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Union, Literal, Annotated, Optional # Added Optional

# ... (Keep existing models: UserTurnModel, AgentTurnModel, ToolInteractionModel, LLMCheckAssertionModel) ...

class UserTurnModel(BaseModel):
    type: Literal["user"] = "user"
    text: str

class AgentTurnModel(BaseModel):
    type: Literal["agent"] = "agent"
    text: str

class ToolInteractionModel(BaseModel):
    type: Literal["tool_interaction"] = "tool_interaction"
    name: str
    args: Dict[str, Any]
    result: Any

TraceStepModel = Union[UserTurnModel, AgentTurnModel, ToolInteractionModel]

class LLMCheckAssertionModel(BaseModel):
    name: str
    description: str
    prompt_template: str # This is now the specific question/instruction part
    expected_response: str = "YES"
    is_outcome_check: bool = False

DiscriminatedTraceStep = Annotated[TraceStepModel, Field(discriminator="type")]

class TestCaseModel(BaseModel):
    goal_description: str
    # Add initial_state field
    initial_state: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Initial key-value state for the agent (e.g., current_date)."
    )
    golden_trace: List[DiscriminatedTraceStep]
    assertions: List[LLMCheckAssertionModel]