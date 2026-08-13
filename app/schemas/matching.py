"""Request and response schemas for internship matching."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rag import InternshipJob


class MatchingRequest(BaseModel):
    """Optional parsed-resume selection for matching."""

    model_config = ConfigDict(extra="forbid")

    user_detail_id: uuid.UUID | None = None


class MatchingProfile(BaseModel):
    """Resolved profile used to construct the RAG query."""

    user_id: uuid.UUID
    name: str
    email: str
    location_preference: str | None = None
    education: list[dict[str, object]] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[dict[str, object]] = Field(default_factory=list)
    experience: list[dict[str, object]] = Field(default_factory=list)
    profile_summary: str = ""
    certifications: list[dict[str, object]] = Field(default_factory=list)


class MatchCitation(BaseModel):
    """Source attribution for a retrieved internship."""

    source: str
    apply_url: str
    vector_document_id: str


class CompatibilityBreakdown(BaseModel):
    """Detailed match analysis and multi-factor scoring."""

    overall_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Overall compatibility percentage (0-100%)",
    )
    skills_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Skill overlap percentage (0-100%)",
    )
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    fit_level: str = "Medium"  # "High", "Medium", "Low"


class JobMatch(BaseModel):
    """Ranked internship result with retrieval score, citation, and compatibility breakdown."""

    score: float
    job: InternshipJob | None
    citation: MatchCitation
    compatibility: CompatibilityBreakdown | None = None


class MatchingResponse(BaseModel):
    """Resolved matching profile and ranked internship results."""

    profile: MatchingProfile
    matches: list[JobMatch]
