"""
LLM Service — Abstraction layer supporting Ollama, Anthropic Claude, and OpenAI.

All providers support streaming for real-time chat UX.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional

import httpx

from app.config import LLMProvider, settings

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        """Generate a complete response."""
        ...

    @abstractmethod
    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response, yielding tokens."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM provider is reachable."""
        ...


class OllamaLLM(BaseLLM):
    """Ollama local LLM provider."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        msgs = self._prepare_messages(messages, system_prompt)
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": msgs, "stream": False},
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        msgs = self._prepare_messages(messages, system_prompt)
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": msgs, "stream": True},
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            token = data["message"]["content"]
                            if token:
                                yield token
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _prepare_messages(self, messages: List[dict], system_prompt: str) -> List[dict]:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        return msgs


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM provider."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY in .env")

    def _get_client(self):
        import anthropic
        return anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        client = self._get_client()
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": self._filter_messages(messages),
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await client.messages.create(**kwargs)
        return response.content[0].text

    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": self._filter_messages(messages),
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            # Minimal request to verify key
            await client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False

    def _filter_messages(self, messages: List[dict]) -> List[dict]:
        """Anthropic doesn't accept 'system' role in messages array."""
        return [m for m in messages if m["role"] in ("user", "assistant")]


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in .env")

    def _get_client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self.api_key)

    async def generate(self, messages: List[dict], system_prompt: str = "") -> str:
        client = self._get_client()
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        response = await client.chat.completions.create(
            model=self.model,
            messages=msgs,
            max_tokens=4096,
        )
        return response.choices[0].message.content

    async def generate_stream(
        self, messages: List[dict], system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=msgs,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False


# ─── Factory & Runtime State ─────────────────────────────

class LLMManager:
    """Manages the active LLM provider with runtime switching."""

    def __init__(self):
        self._provider: LLMProvider = settings.llm_provider
        self._custom_model: Optional[str] = None
        self._custom_api_key: Optional[str] = None
        self._instance: Optional[BaseLLM] = None

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @property
    def model_name(self) -> str:
        if self._custom_model:
            return self._custom_model
        if self._provider == LLMProvider.OLLAMA:
            return settings.ollama_model
        elif self._provider == LLMProvider.ANTHROPIC:
            return settings.anthropic_model
        else:
            return settings.openai_model

    def get_llm(self) -> BaseLLM:
        """Get the current LLM instance (creates lazily)."""
        if self._instance is None:
            self._instance = self._create_instance()
        return self._instance

    def switch_provider(
        self, provider: str, model: str = None, api_key: str = None
    ):
        """Switch the active LLM provider at runtime."""
        self._provider = LLMProvider(provider)
        self._custom_model = model
        self._custom_api_key = api_key
        self._instance = None  # Force re-creation
        logger.info(f"Switched LLM provider to {provider} (model: {model or 'default'})")

    def _create_instance(self) -> BaseLLM:
        if self._provider == LLMProvider.OLLAMA:
            return OllamaLLM(model=self._custom_model)
        elif self._provider == LLMProvider.ANTHROPIC:
            return AnthropicLLM(
                api_key=self._custom_api_key,
                model=self._custom_model,
            )
        elif self._provider == LLMProvider.OPENAI:
            return OpenAILLM(
                api_key=self._custom_api_key,
                model=self._custom_model,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {self._provider}")


# Singleton manager
llm_manager = LLMManager()
