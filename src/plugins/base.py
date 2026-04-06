# src/plugins/base.py
from abc import ABC, abstractmethod
from src.models import ActionResult

class ActionPlugin(ABC):
    name: str
    
    @abstractmethod
    async def execute(self, params: dict, memory, user_id: str) -> ActionResult:
        pass
