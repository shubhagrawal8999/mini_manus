from src.utils.api_clients import DeepSeekClient, OpenAIClient
from src.config import Config
from src.models import IntentType
import re

class IntentRouter:
    def __init__(self, memory):
        self.memory = memory
        self.deepseek = DeepSeekClient()
        self.openai = OpenAIClient()
    
    async def route(self, user_text: str, user_id: str) -> tuple[IntentType, dict]:
        # Simple keyword matching first (fast path)
        text_lower = user_text.lower()
        if "linkedin" in text_lower or "post on linkedin" in text_lower:
            return IntentType.POST_LINKEDIN, {"content": user_text}
        if "email" in text_lower and ("send" in text_lower or "mail" in text_lower):
            return IntentType.SEND_EMAIL, {"content": user_text}
        if "deep search" in text_lower or "research" in text_lower:
            return IntentType.DEEP_SEARCH, {"query": user_text}
        if "snapshot" in text_lower or "screenshot" in text_lower:
            return IntentType.SNAPSHOT, {"url": extract_url(user_text)}
        
        # Fallback to model
        intent = await self._classify_with_model(user_text, user_id)
        return intent, {"original_text": user_text}
    
    async def _classify_with_model(self, text: str, user_id: str) -> IntentType:
        # Retrieve user preferences to bias classification
        prefs = await self.memory.retrieve_preferences(user_id, text, top_k=2)
        pref_context = "\n".join([p["text"] for p in prefs]) if prefs else ""
        messages = [
            {"role": "system", "content": f"You are an intent classifier. User preferences: {pref_context}. Output only one of: post_linkedin, send_email, deep_search, snapshot, unknown."},
            {"role": "user", "content": text}
        ]
        # Use DeepSeek by default, OpenAI for complex
        model = self.deepseek
        if "?" in text and len(text) > 100:
            model = self.openai
        response = await model.chat_completion(messages, temperature=0.0)
        try:
            return IntentType(response.strip().lower())
        except ValueError:
            return IntentType.UNKNOWN

def extract_url(text: str) -> str:
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0) if match else ""
