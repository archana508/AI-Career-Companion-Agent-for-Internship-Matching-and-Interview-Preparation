"""Tests for matching-agent coordination and citations."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agents.job_retrieval_agent import JobRetrievalAgent
from app.agents.orchestrator import MatchingOrchestrator
from app.core.exceptions import ResourceAccessDeniedError
from app.models.user import User, UserProfile
from app.models.user_detail import UserDetail
from app.schemas.matching import (
    JobMatch,
    MatchCitation,
    MatchingProfile,
    MatchingRequest,
)
from app.schemas.rag import InternshipJob, SearchResult


class FakeRetriever:
    """Deterministic retriever used by agent tests."""

    def __init__(self) -> None:
        self.query = ""

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        self.query = query
        job = InternshipJob(
            title="Backend Intern",
            company="Example",
            description="Build APIs",
            skills_required=["Python"],
            location="Remote",
            apply_url="https://example.com/apply",
        )
        return [
            SearchResult(
                job_id="job-1",
                score=0.91,
                document=job.to_document_text(),
                metadata=job.to_metadata(),
                job=job,
            )
        ][:top_k]


class TestJobRetrievalAgent:
    """Semantic query and citation behavior."""

    @pytest.mark.asyncio
    async def test_returns_cited_matches_without_embedding_identity(self) -> None:
        retriever = FakeRetriever()
        agent = JobRetrievalAgent(retriever)  # type: ignore[arg-type]
        profile = MatchingProfile(
            user_id=uuid4(),
            name="Candidate",
            email="private@example.com",
            location_preference="Remote",
            skills=["Python"],
        )

        matches = await agent.retrieve(profile, top_k=5)

        assert matches[0].score == 0.91
        assert matches[0].citation.apply_url == "https://example.com/apply"
        assert matches[0].citation.vector_document_id == "job-1"
        assert "private@example.com" not in retriever.query


class TestMatchingOrchestrator:
    """Candidate profile resolution behavior."""

    @staticmethod
    def _user() -> User:
        user_id = uuid4()
        user = User(
            id=user_id,
            name="Candidate",
            email="candidate@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        user.profile = UserProfile(
            id=uuid4(),
            user_id=user_id,
            location_preference="Remote",
            skills=["Python"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return user

    @pytest.mark.asyncio
    async def test_merges_profile_resume_and_request_data(self) -> None:
        user = self._user()
        detail = UserDetail(
            id=uuid4(),
            user_id=user.id,
            document_type="resume",
            file_name="resume.pdf",
            file_path="uploads/resume.pdf",
            education=[],
            skills=["FastAPI"],
            projects=[],
            experience=[],
            profile_summary="Backend developer",
            certifications=[],
            body_paragraphs=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        users = AsyncMock()
        users.get_by_id.return_value = user
        details = AsyncMock()
        details.get_by_id.return_value = detail
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = []
        orchestrator = MatchingOrchestrator(users, details, retrieval)

        response = await orchestrator.match(
            user.id,
            MatchingRequest(user_detail_id=detail.id),
        )

        assert response.profile.skills == ["Python", "FastAPI"]
        assert response.profile.profile_summary == "Backend developer"
        retrieval.retrieve.assert_awaited_once_with(response.profile, 5)

    @pytest.mark.asyncio
    async def test_rejects_document_owned_by_another_user(self) -> None:
        user = self._user()
        users = AsyncMock()
        users.get_by_id.return_value = user
        details = AsyncMock()
        details.get_by_id.return_value = UserDetail(
            id=uuid4(),
            user_id=uuid4(),
            document_type="resume",
        )
        orchestrator = MatchingOrchestrator(users, details, AsyncMock())

        with pytest.raises(ResourceAccessDeniedError):
            await orchestrator.match(
                user.id,
                MatchingRequest(
                    user_detail_id=details.get_by_id.return_value.id,
                ),
            )

    @pytest.mark.asyncio
    async def test_enriches_matches_with_compatibility_agent(self) -> None:
        user = self._user()
        users = AsyncMock()
        users.get_by_id.return_value = user
        details = AsyncMock()
        details.get_by_id.return_value = None

        job = InternshipJob(
            title="Backend Intern",
            company="Google",
            description="APIs",
            skills_required=["Python", "FastAPI"],
            location="Remote",
            apply_url="https://careers.google.com",
        )
        job_match = JobMatch(
            score=0.85,
            job=job,
            citation=MatchCitation(
                source="mock",
                apply_url="https://careers.google.com",
                vector_document_id="v1",
            ),
        )
        retrieval = AsyncMock()
        retrieval.retrieve.return_value = [job_match]

        compat_agent = AsyncMock()
        compat_agent.evaluate_matches.return_value = [
            JobMatch(
                score=0.85,
                job=job,
                citation=job_match.citation,
                compatibility=None,
            )
        ]

        orchestrator = MatchingOrchestrator(users, details, retrieval, compat_agent)
        response = await orchestrator.match(user.id, MatchingRequest())

        assert len(response.matches) == 1
        compat_agent.evaluate_matches.assert_awaited_once()


class TestCompatibilityAgent:
    """Skill overlap, overall scoring, and LLM reasoning behavior."""

    @staticmethod
    def _profile() -> MatchingProfile:
        return MatchingProfile(
            user_id=uuid4(),
            name="Candidate",
            email="candidate@example.com",
            location_preference="Bangalore",
            skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
            profile_summary="Passionate backend engineer with API experience.",
        )

    @staticmethod
    def _job() -> InternshipJob:
        return InternshipJob(
            title="Backend Engineering Intern",
            company="Tech Corp",
            description="Build scalable microservices with Python and Kubernetes.",
            skills_required=["Python", "FastAPI", "Kubernetes", "AWS"],
            location="Bangalore, India",
            apply_url="https://example.com/apply",
        )

    @pytest.mark.asyncio
    async def test_skill_analysis_identifies_matched_and_missing(self) -> None:
        from app.agents.compatibility_agent import CompatibilityAgent

        agent = CompatibilityAgent(llm_client=AsyncMock())
        matched, missing, score = agent._analyze_skills(
            candidate_skills=["Python", "FastAPI", "PostgreSQL"],
            required_skills=["Python", "FastAPI", "Kubernetes", "AWS"],
        )

        assert matched == ["Python", "FastAPI"]
        assert missing == ["Kubernetes", "AWS"]
        assert score == 50.0

    @pytest.mark.asyncio
    async def test_evaluate_with_llm_json_response(self) -> None:
        from app.agents.compatibility_agent import CompatibilityAgent

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            '{"reasons": ["Strong Python background", "Bangalore location match"], '
            '"recommendations": ["Learn basic Kubernetes concepts"]}'
        )

        agent = CompatibilityAgent(llm_client=mock_llm)
        breakdown = await agent.evaluate(self._profile(), self._job(), vector_score=0.9)

        assert breakdown.overall_score > 0
        assert breakdown.skills_score == 50.0
        assert "Strong Python background" in breakdown.match_reasons
        assert "Learn basic Kubernetes concepts" in breakdown.recommendations
        assert breakdown.fit_level in ["High", "Medium", "Low"]

    @pytest.mark.asyncio
    async def test_evaluate_resilient_fallback_on_llm_failure(self) -> None:
        from app.agents.compatibility_agent import CompatibilityAgent

        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = RuntimeError("Ollama connection failed")

        agent = CompatibilityAgent(llm_client=mock_llm)
        breakdown = await agent.evaluate(self._profile(), self._job(), vector_score=0.8)

        assert breakdown.overall_score > 0
        assert len(breakdown.match_reasons) > 0
        assert len(breakdown.recommendations) > 0
        assert "Python" in breakdown.matched_skills

    @pytest.mark.asyncio
    async def test_evaluate_matches_enriches_list(self) -> None:
        from app.agents.compatibility_agent import CompatibilityAgent

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            '{"reasons": ["Good fit"], "recommendations": ["Apply now"]}'
        )

        agent = CompatibilityAgent(llm_client=mock_llm)
        job = self._job()
        raw_match = JobMatch(
            score=0.9,
            job=job,
            citation=MatchCitation(
                source="mock",
                apply_url="https://example.com",
                vector_document_id="v1",
            ),
        )

        results = await agent.evaluate_matches(self._profile(), [raw_match])

        assert len(results) == 1
        assert results[0].compatibility is not None
        assert results[0].compatibility.skills_score == 50.0
        assert results[0].compatibility.matched_skills == ["Python", "FastAPI"]

