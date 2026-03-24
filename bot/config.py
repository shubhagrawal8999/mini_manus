"""
Configuration and Model Routing.

BUG FIXED:
  Circuit breaker reset logic was inverted:
    if self.deepseek_failures > 0 and not self.circuit_open:
        self.deepseek_failures = 0
  This reset the failure counter BEFORE the circuit ever opened, and once the
  circuit opened it could never reset (because the condition required
  `not self.circuit_open`).

  Fix: reset both `deepseek_failures` AND `circuit_open` on a successful call
  so DeepSeek can recover after a transient outage.
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Optional, Literal, List, Dict, Any

from openai import AsyncOpenAI, RateLimitError, APIError, Timeout
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
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
    """Centralised configuration with validation."""

    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_USER_ID: int = int(os.getenv("ADMIN_USER_ID", "0"))

    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/data/agent.db")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    GMAIL_USER: str = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")

    LINKEDIN_ACCESS_TOKEN: str = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    LINKEDIN_PERSON_URN: str = os.getenv("LINKEDIN_PERSON_URN", "")

    @classmethod
    def validate(cls) -> List[str]:
        missing = []
        if not cls.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY")
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.ADMIN_USER_ID:
            missing.append("ADMIN_USER_ID (your Telegram numeric ID)")
        return missing


class ModelRouter:
    """
    Cost-optimised routing with circuit breaker.
    DeepSeek is primary (cheap); OpenAI is the fallback.
    """

    MAX_FAILURES_BEFORE_FALLBACK = 3

    def __init__(self):
        self.deepseek = AsyncOpenAI(
            api_key=Settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
            timeout=60.0,
        )
        self.openai = AsyncOpenAI(
            api_key=Settings.OPENAI_API_KEY,
            timeout=30.0,
        )

        self.deepseek_failures = 0
        self.circuit_open = False  # True = skip DeepSeek, use OpenAI

        self.models: Dict[str, ModelConfig] = {
            "deepseek_chat": ModelConfig(
                name="deepseek-chat",
                client=self.deepseek,
                model_id="deepseek-chat",
                cost_per_1k_input=0.0001,
                cost_per_1k_output=0.0002,
                max_tokens=4096,
            ),
            "deepseek_reasoner": ModelConfig(
                name="deepseek-reasoner",
                client=self.deepseek,
                model_id="deepseek-reasoner",
                cost_per_1k_input=0.0005,
                cost_per_1k_output=0.0016,
                max_tokens=8192,
                is_reasoning=True,
            ),
            "gpt4o_mini": ModelConfig(
                name="gpt-4o-mini",
                client=self.openai,
                model_id="gpt-4o-mini",
                cost_per_1k_input=0.00015,
                cost_per_1k_output=0.0006,
                max_tokens=4096,
            ),
        }

    def select_model(
        self, complexity: Literal["simple", "medium", "complex", "reasoning"]
    ) -> ModelConfig:
        if self.circuit_open and Settings.OPENAI_API_KEY:
            return self.models["gpt4o_mini"]

        if complexity in ("simple", "medium"):
            return self.models["deepseek_chat"]
        return self.models["deepseek_reasoner"]

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (RateLimitError, APIError, Timeout, asyncio.TimeoutError)
        ),
        reraise=True,
    )
    async def call(
        self,
        messages: List[Dict[str, str]],
        complexity: Literal["simple", "medium", "complex", "reasoning"] = "medium",
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        model = self.select_model(complexity)

        try:
            params: Dict[str, Any] = {
                "model": model.model_id,
                "messages": messages,
                "max_tokens": model.max_tokens,
                "temperature": temperature,
            }
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"

            response = await model.client.chat.completions.create(**params)

            # BUG FIX: reset circuit on ANY successful call, regardless of
            # whether the circuit was open.
            self.deepseek_failures = 0
            self.circuit_open = False

            usage = response.usage
            cost = (
                usage.prompt_tokens * model.cost_per_1k_input / 1000
                + usage.completion_tokens * model.cost_per_1k_output / 1000
            )

            return {
                "success": True,
                "content": response.choices[0].message,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": round(cost, 6),
                },
                "model": model.name,
            }

        except (RateLimitError, APIError, Timeout, asyncio.TimeoutError) as exc:
            # Only count failures against DeepSeek (not OpenAI)
            if "deepseek" in model.name.lower():
                self.deepseek_failures += 1
                if self.deepseek_failures >= self.MAX_FAILURES_BEFORE_FALLBACK:
                    self.circuit_open = True
                    print(
                        f"[CircuitBreaker] OPEN — DeepSeek failed "
                        f"{self.deepseek_failures}x, falling back to OpenAI"
                    )
            raise  # let tenacity retry

        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    async def close(self):
        await self.deepseek.close()
        await self.openai.close()


# Singletons
router = ModelRouter()
