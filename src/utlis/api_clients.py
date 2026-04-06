import openai
from src.config import Config
import httpx

class DeepSeekClient:
    def __init__(self):
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {"Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}"}
    
    async def chat_completion(self, messages: list, temperature=0.7):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": Config.DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": temperature
                },
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

class OpenAIClient:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
    
    async def chat_completion(self, messages: list, temperature=0.7):
        resp = await self.client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=messages,
            temperature=temperature
        )
        return resp.choices[0].message.content
