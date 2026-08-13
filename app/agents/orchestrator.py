"""Orchestrator for profile resolution and internship retrieval."""

from __future__ import annotations

from uuid import UUID

from app.agents.compatibility_agent import CompatibilityAgent
from app.agents.job_retrieval_agent import JobRetrievalAgent
from app.core.exceptions import (
    InvalidDocumentSelectionError,
    ResourceAccessDeniedError,
    ResourceNotFoundError,
)
from app.database.repositories.user_detail_repository import UserDetailRepository
from app.database.repositories.user_repository import UserRepository
from app.models.user_detail import UserDetail
from app.schemas.matching import (
    CompatibilityBreakdown,
    MatchingProfile,
    MatchingRequest,
    MatchingResponse,
)
from app.schemas.rag import InternshipJob
from app.schemas.user_detail import DocumentType

DEFAULT_MATCH_COUNT = 5


class MatchingOrchestrator:
    """Resolve candidate data and coordinate semantic retrieval and compatibility scoring."""

    def __init__(
        self,
        user_repository: UserRepository,
        detail_repository: UserDetailRepository,
        retrieval_agent: JobRetrievalAgent,
        compatibility_agent: CompatibilityAgent | None = None,
    ) -> None:
        self._users = user_repository
        self._details = detail_repository
        self._retrieval_agent = retrieval_agent
        self._compatibility_agent = compatibility_agent

    async def match(self, user_id: UUID, request: MatchingRequest) -> MatchingResponse:
        """Build a candidate profile and return ranked matches with compatibility analysis."""
        profile = await self.build_profile(user_id, request.user_detail_id)
        matches = await self._retrieval_agent.retrieve(profile, DEFAULT_MATCH_COUNT)
        if self._compatibility_agent is not None:
            matches = await self._compatibility_agent.evaluate_matches(profile, matches)
        return MatchingResponse(profile=profile, matches=matches)

    async def compare_job(
        self,
        user_id: UUID,
        job: InternshipJob,
        request: MatchingRequest,
    ) -> CompatibilityBreakdown:
        """Compare a candidate profile against a specific internship listing."""
        profile = await self.build_profile(user_id, request.user_detail_id)
        if self._compatibility_agent is None:
            raise ResourceNotFoundError("Compatibility agent is not configured")
        return await self._compatibility_agent.evaluate(profile, job)

    async def build_profile(
        self,
        user_id: UUID,
        user_detail_id: UUID | None,
    ) -> MatchingProfile:
        """Resolve candidate identity, manual preferences, and parsed resume data."""
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError("User not found")

        detail = await self._resolve_detail(user_id, user_detail_id)
        profile_skills = user.profile.skills if user.profile else []
        resume_skills = detail.skills if detail is not None else []
        return MatchingProfile(
            user_id=user.id,
            name=user.name,
            email=user.email,
            location_preference=(user.profile.location_preference if user.profile else None),
            education=detail.education if detail is not None else [],
            skills=self._merge_skills(profile_skills, resume_skills),
            projects=detail.projects if detail is not None else [],
            experience=detail.experience if detail is not None else [],
            profile_summary=(detail.profile_summary or "") if detail is not None else "",
            certifications=detail.certifications if detail is not None else [],
        )

    async def _resolve_detail(
        self,
        user_id: UUID,
        user_detail_id: UUID | None,
    ) -> UserDetail | None:
        if user_detail_id is None:
            return None
        detail = await self._details.get_by_id(user_detail_id)
        if detail is None:
            raise ResourceNotFoundError("User detail not found")
        if detail.user_id != user_id:
            raise ResourceAccessDeniedError("The selected document does not belong to this user")
        if detail.document_type != DocumentType.RESUME.value:
            raise InvalidDocumentSelectionError("Only a parsed resume can be used for matching")
        return detail

    @staticmethod
    def _merge_skills(profile_skills: list[str], selected_skills: list[str]) -> list[str]:
        unique_skills: dict[str, str] = {}
        for skill in [*profile_skills, *selected_skills]:
            normalized = skill.strip()
            if normalized:
                unique_skills.setdefault(normalized.casefold(), normalized)
        return list(unique_skills.values())
