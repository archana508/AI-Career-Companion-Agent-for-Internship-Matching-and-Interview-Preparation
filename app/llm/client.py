"""LLM chat, completion, and structured extraction contracts and Ollama implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_ollama import ChatOllama
from pydantic import BaseModel

from app.core.exceptions import DocumentParsingError, LLMGenerationError

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
MAX_DOCUMENT_CHARACTERS = 60_000


@dataclass(frozen=True)
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # e.g. "system", "user", "assistant"
    content: str

    def to_tuple(self) -> tuple[str, str]:
        """Convert to (role, content) tuple for LangChain models."""
        return (self.role, self.content)


class ChatClient(ABC):
    """Contract for text completion and conversational LLM operations."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text completion from a prompt and optional system prompt."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage | dict[str, str] | tuple[str, str]],
    ) -> str:
        """Generate text completion from a list of conversational messages."""


class StructuredExtractionClient(ABC):
    """Contract for extracting a Pydantic model from unstructured text."""

    @abstractmethod
    async def extract(
        self,
        text: str,
        schema: type[StructuredModel],
        instructions: str,
    ) -> StructuredModel:
        """Extract and validate structured data."""


class LLMClient(ChatClient, StructuredExtractionClient, ABC):
    """Unified contract supporting chat, completion, and structured extraction."""


class OllamaLLMClient(LLMClient):
    """Ollama implementation supporting text generation, chat, and structured extraction."""

    def __init__(self, *, model: str, base_url: str, temperature: float = 0.0) -> None:
        self._model_name = model
        self._base_url = base_url
        self._temperature = temperature
        self._model = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text completion from a single prompt and optional system prompt."""
        formatted_messages: list[tuple[str, str]] = []
        if system_prompt:
            formatted_messages.append(("system", system_prompt))
        formatted_messages.append(("user", prompt))

        try:
            response = await self._model.ainvoke(formatted_messages)
            return self._extract_content(response)
        except Exception as exc:
            raise LLMGenerationError(self._format_error("generate text", exc)) from exc

    async def chat(
        self,
        messages: list[ChatMessage | dict[str, str] | tuple[str, str]],
    ) -> str:
        """Generate a response given a conversation message history."""
        if not messages:
            return ""

        formatted_messages = [self._normalize_message(msg) for msg in messages]
        try:
            response = await self._model.ainvoke(formatted_messages)
            return self._extract_content(response)
        except Exception as exc:
            raise LLMGenerationError(self._format_error("complete chat", exc)) from exc

    async def extract(
        self,
        text: str,
        schema: type[StructuredModel],
        instructions: str,
    ) -> StructuredModel:
        """Extract a validated model from document text."""
        prompt = (
            f"{instructions}\n"
            "Use only facts present in the document. Use empty strings or lists "
            "when a field is absent; never invent information. Return exactly one "
            "JSON object matching the supplied response schema.\n\n"
            f"DOCUMENT:\n{text[:MAX_DOCUMENT_CHARACTERS]}"
        )
        try:
            structured_model = self._model.with_structured_output(
                schema,
                method="json_schema",
            )
            result = await structured_model.ainvoke(prompt)
            return result if isinstance(result, schema) else schema.model_validate(result)
        except Exception as exc:
            raise DocumentParsingError(self._format_error("extract structured data", exc)) from exc

    @staticmethod
    def _normalize_message(msg: ChatMessage | dict[str, str] | tuple[str, str]) -> tuple[str, str]:
        if isinstance(msg, ChatMessage):
            return msg.to_tuple()
        if isinstance(msg, dict):
            return (msg.get("role", "user"), msg.get("content", ""))
        if isinstance(msg, tuple) and len(msg) == 2:
            return (str(msg[0]), str(msg[1]))
        return ("user", str(msg))

    @staticmethod
    def _extract_content(response: Any) -> str:
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join(str(part) for part in content)
            return str(content)
        return str(response)

    def _format_error(self, operation: str, error: Exception) -> str:
        error_text = str(error).casefold()
        if "model" in error_text and "not found" in error_text:
            return (
                f"Ollama model '{self._model_name}' is not installed. "
                f"Run: ollama pull {self._model_name}"
            )
        if "connection" in error_text or "connect" in error_text:
            return "Ollama is unavailable. Start Ollama and retry the request"
        if operation == "extract structured data":
            return (
                f"Ollama model '{self._model_name}' could not produce the required "
                "structured document response"
            )
        return f"Ollama model '{self._model_name}' failed to {operation}: {error}"


# Backward compatibility alias
OllamaStructuredExtractionClient = OllamaLLMClient
