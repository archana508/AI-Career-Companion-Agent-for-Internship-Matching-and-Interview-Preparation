"""Tests for Ollama structured extraction and general chat/completion."""

from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from app.core.exceptions import DocumentParsingError, LLMGenerationError
from app.llm.client import (
    ChatMessage,
    OllamaLLMClient,
    OllamaStructuredExtractionClient,
)
from app.schemas.user_detail import ResumeData


@dataclass
class FakeAIMessage:
    """Mock LangChain AIMessage response."""

    content: str


class FakeStructuredModel:
    """Deterministic structured-model runnable."""

    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def ainvoke(self, _prompt: str) -> object:
        """Return the configured result or raise the configured error."""
        if self._error is not None:
            raise self._error
        return self._result


class FakeChatModel:
    """Capture structured-output and direct chat calls without calling Ollama."""

    def __init__(
        self,
        runnable: FakeStructuredModel | None = None,
        chat_response: object = None,
        error: Exception | None = None,
    ) -> None:
        self._runnable = runnable or FakeStructuredModel()
        self._chat_response = chat_response
        self._error = error
        self.invoked_messages: list[tuple[str, str]] | None = None
        self.method: str | None = None

    async def ainvoke(self, messages: list[tuple[str, str]]) -> object:
        """Record input and return configured response or raise error."""
        self.invoked_messages = messages
        if self._error is not None:
            raise self._error
        return self._chat_response

    def with_structured_output(
        self,
        _schema: type[BaseModel],
        *,
        method: str,
    ) -> FakeStructuredModel:
        """Record the requested extraction method."""
        self.method = method
        return self._runnable


class TestOllamaStructuredExtractionClient:
    """Structured response and actionable failure behavior."""

    @staticmethod
    def _client(runnable: FakeStructuredModel) -> tuple[
        OllamaStructuredExtractionClient,
        FakeChatModel,
    ]:
        client = OllamaStructuredExtractionClient(
            model="llama3.2:1b",
            base_url="http://localhost:11434",
        )
        fake_model = FakeChatModel(runnable=runnable)
        client._model = fake_model  # type: ignore[assignment]
        return client, fake_model

    @pytest.mark.asyncio
    async def test_extracts_schema_with_json_mode(self) -> None:
        client, fake_model = self._client(FakeStructuredModel({"skills": ["Python"]}))

        result = await client.extract("Python developer", ResumeData, "Extract resume")

        assert result.skills == ["Python"]
        assert fake_model.method == "json_schema"

    @pytest.mark.asyncio
    async def test_reports_missing_model_action(self) -> None:
        client, _ = self._client(
            FakeStructuredModel(error=RuntimeError("model 'llama3.2:1b' not found"))
        )

        with pytest.raises(DocumentParsingError, match="ollama pull llama3.2:1b"):
            await client.extract("Resume", ResumeData, "Extract resume")


class TestOllamaLLMChatAndGeneration:
    """General text completion and multi-turn chat behavior."""

    @staticmethod
    def _client(
        chat_response: object = None,
        error: Exception | None = None,
    ) -> tuple[OllamaLLMClient, FakeChatModel]:
        client = OllamaLLMClient(
            model="llama3.2:1b",
            base_url="http://localhost:11434",
        )
        fake_model = FakeChatModel(chat_response=chat_response, error=error)
        client._model = fake_model  # type: ignore[assignment]
        return client, fake_model

    @pytest.mark.asyncio
    async def test_generate_text_without_system_prompt(self) -> None:
        client, fake_model = self._client(chat_response=FakeAIMessage("Hello from Ollama!"))

        response = await client.generate("Introduce yourself")

        assert response == "Hello from Ollama!"
        assert fake_model.invoked_messages == [("user", "Introduce yourself")]

    @pytest.mark.asyncio
    async def test_generate_text_with_system_prompt(self) -> None:
        client, fake_model = self._client(
            chat_response=FakeAIMessage("AI Career Assistant response")
        )

        response = await client.generate(
            "What should I prepare?",
            system_prompt="You are an expert career counselor.",
        )

        assert response == "AI Career Assistant response"
        assert fake_model.invoked_messages == [
            ("system", "You are an expert career counselor."),
            ("user", "What should I prepare?"),
        ]

    @pytest.mark.asyncio
    async def test_chat_with_message_objects(self) -> None:
        client, fake_model = self._client(chat_response=FakeAIMessage("You should learn FastAPI."))

        messages = [
            ChatMessage(role="system", content="You are a career coach."),
            ChatMessage(role="user", content="I want to be a backend engineer."),
            ChatMessage(role="assistant", content="Start with Python fundamentals."),
            ChatMessage(role="user", content="What framework next?"),
        ]
        response = await client.chat(messages)

        assert response == "You should learn FastAPI."
        assert fake_model.invoked_messages == [
            ("system", "You are a career coach."),
            ("user", "I want to be a backend engineer."),
            ("assistant", "Start with Python fundamentals."),
            ("user", "What framework next?"),
        ]

    @pytest.mark.asyncio
    async def test_chat_with_dict_and_tuple_messages(self) -> None:
        client, fake_model = self._client(chat_response=FakeAIMessage("Advice response"))

        messages = [
            {"role": "system", "content": "Coach prompt"},
            ("user", "Question here"),
        ]
        response = await client.chat(messages)

        assert response == "Advice response"
        assert fake_model.invoked_messages == [
            ("system", "Coach prompt"),
            ("user", "Question here"),
        ]

    @pytest.mark.asyncio
    async def test_chat_empty_messages_returns_empty_string(self) -> None:
        client, fake_model = self._client()

        response = await client.chat([])

        assert response == ""
        assert fake_model.invoked_messages is None

    @pytest.mark.asyncio
    async def test_generate_handles_missing_model_error(self) -> None:
        client, _ = self._client(error=RuntimeError("model 'llama3.2:1b' not found"))

        with pytest.raises(LLMGenerationError, match="ollama pull llama3.2:1b"):
            await client.generate("Hello")

    @pytest.mark.asyncio
    async def test_chat_handles_connection_error(self) -> None:
        client, _ = self._client(error=ConnectionError("Connection refused by Ollama"))

        with pytest.raises(LLMGenerationError, match="Ollama is unavailable"):
            await client.chat([ChatMessage(role="user", content="Hi")])
