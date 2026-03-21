"""
Configuration and Model Routing.
Handles API keys, retry logic, and cost-optimized model selection.
"""

import os
import asyncio
from dataclasses import dataclass
from typing import Optional, Literal, List, Dict, Any
from openai import AsyncOpenAI, RateLimitError, APIError, Timeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ModelConfig:
    name: str
    client: AsyncOpenAI
    model_id: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_tokens: int
    is_reasoning: bool = False

class Settings:
    """Centralized configuration with validation."""
    
    # API Keys
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
    
    # Paths
    DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/agent.db")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Gmail
    GMAIL_USER = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
    
    @classmethod
    def validate(cls) -> List[str]:
        """Return list of missing required settings."""
        missing = []
        if not cls.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY")
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.ADMIN_USER_ID:
            missing.append("ADMIN_USER_ID (your Telegram ID)")
        return missing

class ModelRouter:
    """
    Cost-optimized model routing with circuit breaker pattern.
    DeepSeek primary (cheap), OpenAI fallback (reliable).
    """
    
    def __init__(self):
        self.deepseek = AsyncOpenAI(
            api_key=Settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
            timeout=60.0  # Longer timeout for reasoning
        )
        self.openai = AsyncOpenAI(
            api_key=Settings.OPENAI_API_KEY,
            timeout=30.0
        )
        
        # Circuit breaker state
        self.deepseek_failures = 0
        self.circuit_open = False
        self.max_failures_before_fallback = 3
        
        self.models = {
            "deepseek_chat": ModelConfig(
                name="deepseek-chat",
                client=self.deepseek,
                model_id="deepseek-chat",
                cost_per_1k_input=0.0001,  # $0.0001 per 1K tokens
                cost_per_1k_output=0.0002,
                max_tokens=4096,
                is_reasoning=False
            ),
            "deepseek_reasoner": ModelConfig(
                name="deepseek-reasoner",
                client=self.deepseek,
                model_id="deepseek-reasoner",
                cost_per_1k_input=0.0005,
                cost_per_1k_output=0.0016,
                max_tokens=8192,
                is_reasoning=True
            ),
            "gpt4o_mini": ModelConfig(
                name="gpt-4o-mini",
                client=self.openai,
                model_id="gpt-4o-mini",
                cost_per_1k_input=0.0006,
                cost_per_1k_output=0.0009,
                max_tokens=4096,
                is_reasoning=False
            )
        }
    
    def select_model(self, complexity: Literal["simple", "medium", "complex", "reasoning"]) -> ModelConfig:
        """
        Select model based on complexity and circuit state.
        """
        # If circuit open (DeepSeek failing), use OpenAI
        if self.circuit_open and Settings.OPENAI_API_KEY:
            return self.models["gpt4o_mini"]
        
        if complexity == "simple":
            return self.models["deepseek_chat"]
        elif complexity == "medium":
            return self.models["deepseek_chat"]
        elif complexity == "complex":
            return self.models["deepseek_reasoner"]
        else:  # reasoning fallback
            return self.models["deepseek_reasoner"] if not self.circuit_open else self.models["gpt4o_mini"]
    
    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError, Timeout, asyncio.TimeoutError)),
        reraise=True
    )
    async def call(
        self, 
        messages: List[Dict[str, str]], 
        complexity: Literal["simple", "medium", "complex", "reasoning"] = "medium",
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Call LLM with automatic retries and circuit breaker.
        """
        model = self.select_model(complexity)
        
        try:
            # Prepare parameters
            params = {
                "model": model.model_id,
                "messages": messages,
                "max_tokens": model.max_tokens,
                "temperature": temperature,
            }
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            # Execute
            response = await model.client.chat.completions.create(**params)
            
            # Reset circuit on success
            if self.deepseek_failures > 0 and not self.circuit_open:
                self.deepseek_failures = 0
            
            # Calculate cost
            usage = response.usage
            cost = (
                (usage.prompt_tokens * model.cost_per_1k_input / 1000) +
                (usage.completion_tokens * model.cost_per_1k_output / 1000)
            )
            
            return {
                "success": True,
                "content": response.choices[0].message,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": round(cost, 6)
                },
                "model": model.name
            }
            
        except (RateLimitError, APIError, Timeout, asyncio.TimeoutError) as e:
            # Count failures for circuit breaker
            if "deepseek" in str(e).lower():
                self.deepseek_failures += 1
                if self.deepseek_failures >= self.max_failures_before_fallback:
                    self.circuit_open = True
                    print(f"CIRCUIT BREAKER OPEN: DeepSeek failing, falling back to OpenAI")
            
            raise  # Let tenacity retry
        
        except Exception as e:
            # Non-retryable error
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def close(self):
        """Cleanup connections."""
        await self.deepseek.close()
        await self.openai.close()

# Global instance
router = ModelRouter()
