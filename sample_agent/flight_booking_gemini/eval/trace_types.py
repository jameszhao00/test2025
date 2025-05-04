# eval/trace_types.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union

@dataclass
class UserTurn:
    """Represents a user's message in the trace."""
    text: str
    role: str = field(default="user", init=False)

@dataclass
class AgentTurn:
    """Represents an agent's text response in the trace."""
    text: str
    role: str = field(default="agent", init=False)

# Removed ToolCall and ToolResult classes

@dataclass
class ToolInteraction:
    """Represents a complete tool call and its result within the golden trace."""
    name: str
    args: Dict[str, Any]
    result: Any # The result is now part of the interaction object
    role: str = field(default="tool_interaction", init=False)

# Update the Union type to use the new class
TraceStep = Union[UserTurn, AgentTurn, ToolInteraction]