"""Agent for analyzing compatibility between candidate profiles and internships."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.llm.client import ChatClient
from app.schemas.matching import CompatibilityBreakdown, JobMatch, MatchingProfile
from app.schemas.rag import InternshipJob

logger = logging.getLogger(__name__)


class CompatibilityAgent:
    """Evaluate candidate qualifications against internship requirements."""

    def __init__(self, llm_client: ChatClient) -> None:
        self._llm = llm_client

    async def evaluate_matches(
        self,
        profile: MatchingProfile,
        matches: list[JobMatch],
    ) -> list[JobMatch]:
        """Enrich a list of retrieved job matches with compatibility breakdowns."""
        evaluated: list[JobMatch] = []
        for match in matches:
            if match.job is None:
                evaluated.append(match)
                continue

            breakdown = await self.evaluate(profile, match.job, vector_score=match.score)
            evaluated.append(
                JobMatch(
                    score=match.score,
                    job=match.job,
                    citation=match.citation,
                    compatibility=breakdown,
                )
            )
        return evaluated

    async def evaluate(
        self,
        profile: MatchingProfile,
        job: InternshipJob,
        vector_score: float | None = None,
    ) -> CompatibilityBreakdown:
        """Compute quantitative and qualitative compatibility for a candidate and job."""
        matched_skills, missing_skills, skills_score = self._analyze_skills(
            profile.skills, job.skills_required
        )

        v_score = (vector_score if vector_score is not None else 0.5) * 100.0
        base_overall = round(max(0.0, min(100.0, (v_score * 0.4) + (skills_score * 0.6))), 1)

        fit_level = "High" if base_overall >= 75 else ("Medium" if base_overall >= 45 else "Low")

        match_reasons, recommendations = await self._generate_llm_insights(
            profile=profile,
            job=job,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            fit_level=fit_level,
        )

        return CompatibilityBreakdown(
            overall_score=base_overall,
            skills_score=skills_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            match_reasons=match_reasons,
            recommendations=recommendations,
            fit_level=fit_level,
        )

    @staticmethod
    def _analyze_skills(
        candidate_skills: list[str],
        required_skills: list[str],
    ) -> tuple[list[str], list[str], float]:
        """Compute matching skills, missing skills, and skill overlap score."""
        if not required_skills:
            return list(candidate_skills), [], 100.0

        normalized_candidate = {
            s.strip().casefold(): s.strip()
            for s in candidate_skills
            if s.strip()
        }
        matched: list[str] = []
        missing: list[str] = []

        for req in required_skills:
            clean_req = req.strip()
            if not clean_req:
                continue
            req_fold = clean_req.casefold()

            found = False
            for cand_fold in normalized_candidate:
                if req_fold == cand_fold or req_fold in cand_fold or cand_fold in req_fold:
                    matched.append(clean_req)
                    found = True
                    break
            if not found:
                missing.append(clean_req)

        overlap_ratio = len(matched) / len(required_skills) if required_skills else 1.0
        skills_score = round(max(0.0, min(100.0, overlap_ratio * 100.0)), 1)
        return matched, missing, skills_score

    async def _generate_llm_insights(
        self,
        profile: MatchingProfile,
        job: InternshipJob,
        matched_skills: list[str],
        missing_skills: list[str],
        fit_level: str,
    ) -> tuple[list[str], list[str]]:
        """Query the LLM for concise match reasons and application recommendations."""
        prompt = (
            f"Candidate: {profile.name}\n"
            f"Candidate Skills: {', '.join(profile.skills) or 'None listed'}\n"
            f"Candidate Profile Summary: {profile.profile_summary or 'None'}\n"
            f"Job Title: {job.title} at {job.company}\n"
            f"Job Required Skills: {', '.join(job.skills_required)}\n"
            f"Job Description: {job.description}\n"
            f"Matched Skills: {', '.join(matched_skills) or 'None'}\n"
            f"Missing Skills: {', '.join(missing_skills) or 'None'}\n"
            f"Fit Level: {fit_level}\n\n"
            "Provide:\n"
            "1. Two to three concise bullet reasons why the candidate fits this role.\n"
            "2. One to two actionable recommendations to improve their candidacy.\n"
            "Respond strictly in valid JSON with this schema:\n"
            '{"reasons": ["reason 1", "reason 2"], "recommendations": ["rec 1"]}'
        )

        system_prompt = (
            "You are an expert AI Career Matchmaker. Evaluate internship compatibility "
            "objectively, highlighting concrete candidate strengths and actionable gap-closing "
            "steps. Always output valid JSON."
        )

        try:
            raw_response = await self._llm.generate(prompt, system_prompt=system_prompt)
            data = self._parse_json_response(raw_response)
            reasons = data.get("reasons", [])
            recommendations = data.get("recommendations", [])
            if reasons and isinstance(reasons, list):
                return [str(r) for r in reasons], [str(rec) for rec in recommendations]
        except Exception as exc:
            logger.warning("LLM compatibility insight generation failed: %s", exc)

        # Resilient fallback reasons
        fallback_reasons: list[str] = []
        if matched_skills:
            fallback_reasons.append(
                f"Possesses key required skills: {', '.join(matched_skills[:4])}."
            )
        if (
            profile.location_preference
            and profile.location_preference.casefold() in job.location.casefold()
        ):
            fallback_reasons.append(f"Matches preferred location: {job.location}.")
        if not fallback_reasons:
            fallback_reasons.append(
                f"Semantic match found based on candidate background in {job.title} domain."
            )

        fallback_recs: list[str] = []
        if missing_skills:
            fallback_recs.append(
                f"Gain familiarity with {', '.join(missing_skills[:3])} to strengthen your profile."
            )
        else:
            fallback_recs.append("Highlight your relevant projects in your application.")

        return fallback_reasons, fallback_recs

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict[str, Any]:
        """Extract and parse JSON object from LLM response text."""
        cleaned = raw_text.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)
