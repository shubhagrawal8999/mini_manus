from src.memory import MemoryManager
from src.error_handler import ErrorHandler
from src.plugins.linkedin import LinkedInPlugin
from src.plugins.email import EmailPlugin
from src.plugins.deepsearch import DeepSearchPlugin
from src.plugins.snapshot import SnapshotPlugin
from src.models import IntentType, ActionResult
from src.validation import validate_generated_code
from src.config import Config

class ActionExecutor:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self.error_handler = ErrorHandler(memory)
        self.plugins = {
            IntentType.POST_LINKEDIN: LinkedInPlugin(),
            IntentType.SEND_EMAIL: EmailPlugin(),
            IntentType.DEEP_SEARCH: DeepSearchPlugin(),
            IntentType.SNAPSHOT: SnapshotPlugin(),
        }
    
    async def execute_with_repair(self, intent: IntentType, params: dict, user_id: str) -> str:
        if intent not in self.plugins:
            return "I don't know how to do that yet."
        
        plugin = self.plugins[intent]
        context = {"user_id": user_id, "intent": intent, "params": params}
        
        for attempt in range(Config.MAX_RETRIES):
            try:
                # 1. Retrieve any prior error fix for similar context
                error_sig = None
                if attempt > 0:
                    # On retry, get fix from error memory
                    error_sig = MemoryManager.compute_signature(Exception("previous failure"), str(params))
                    fix = await self.memory.get_fix_for_error(error_sig)
                    if fix:
                        params["_fix"] = fix
                
                # 2. Execute plugin action
                result: ActionResult = await plugin.execute(params, self.memory, user_id)
                
                # 3. Validate result (if it includes generated code)
                if result.data and "code" in result.data:
                    valid, msg = validate_generated_code(result.data["code"])
                    if not valid:
                        raise ValueError(f"Code validation failed: {msg}")
                
                # 4. On success, store any fix that worked
                if attempt > 0 and error_sig:
                    await self.memory.store_error_fix(error_sig, "RETRY_SUCCESS", str(params), params.get("_fix", ""), True)
                
                return f"✅ {result.message}"
            
            except Exception as e:
                # Log error and attempt repair
                error_sig = MemoryManager.compute_signature(e, str(params))
                fix = await self.error_handler.handle(e, context, attempt)
                if fix:
                    params["_fix"] = fix
                    continue   # retry with fix
                else:
                    return f"❌ Unrecoverable error: {str(e)}"
        
        return "❌ Max retries exceeded. Please try again later."
