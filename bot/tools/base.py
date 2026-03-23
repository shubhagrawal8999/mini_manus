"""
Base class for all tools.
Ensures consistent interface and error handling.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List,Optional, Literal
from pydantic import BaseModel, ValidationError

class ToolResult(BaseModel):
    """Standardized tool output."""
    status: Literal["success", "error", "partial"]
    message: str
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    retryable: bool = False  # Can LLM retry with modified params?

class Tool(ABC):
    """Base class for all tools."""
    
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool. Must be implemented."""
        pass
    
    def validate_params(self, params: Dict) -> tuple[bool, str]:
        """Basic parameter validation."""
        try:
            # Check required fields
            required = self.parameters.get("required", [])
            for field in required:
                if field not in params:
                    return False, f"Missing required parameter: {field}"
            return True, ""
        except Exception as e:
            return False, str(e)
    
    async def run(self, **kwargs) -> ToolResult:
        """Wrapper with validation and error handling."""
        # Validate
        valid, error = self.validate_params(kwargs)
        if not valid:
            return ToolResult(
                status="error",
                message="Parameter validation failed",
                error=error,
                retryable=True
            )
        
        try:
            # Execute
            return await self.execute(**kwargs)
        except Exception as e:
            return ToolResult(
                status="error",
                message=f"Tool execution failed: {str(e)}",
                error=str(e),
                retryable=True  # LLM can retry with different params
            )
