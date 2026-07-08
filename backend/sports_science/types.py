# sports_science/types.py
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Immutable result returned by every sports-science tool function."""

    value: Any
    unit: str
    methodology: str
    inputs: dict

    model_config = {"frozen": True}

    def to_tool_response(self) -> dict:
        """Serialize for Anthropic tool_result content block."""
        return self.model_dump()
