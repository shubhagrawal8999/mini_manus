from src.memory import MemoryManager
from src.utils.api_clients import OpenAIClient
import traceback

class ErrorHandler:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self.openai = OpenAIClient()
    
    async def handle(self, exception: Exception, context: dict, attempt: int) -> str | None:
        error_sig = self.memory.compute_signature(exception, str(context))
        error_type = type(exception).__name__
        error_msg = str(exception)
        
        # Check if we already have a known fix
        existing_fix = await self.memory.get_fix_for_error(error_sig)
        if existing_fix:
            # Return fix to executor
            return existing_fix
        
        # No fix known – ask model to generate one
        prompt = f"""
        You are a self‑repair engine. The AI agent encountered an error:
        Error type: {error_type}
        Message: {error_msg}
        Context: {context}
        Traceback: {traceback.format_exc()}
        
        Suggest a concrete fix (e.g., "switch API key", "add missing field X", "retry with delay 2s").
        Output only the fix action.
        """
        try:
            fix = await self.openai.chat_completion([{"role": "user", "content": prompt}], temperature=0.3)
            fix = fix.strip()
            # Store as unsuccessful for now (will be updated if later retry works)
            await self.memory.store_error_fix(error_sig, error_type, str(context), fix, False)
            return fix
        except:
            return None
