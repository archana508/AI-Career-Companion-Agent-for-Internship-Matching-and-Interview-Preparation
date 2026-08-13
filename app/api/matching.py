"""Internship matching HTTP endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import MatchingOrchestrator
from app.api.dependencies import get_matching_orchestrator, get_user_detail_service
from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    DocumentParsingError,
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidDocumentError,
    InvalidDocumentSelectionError,
    ResourceAccessDeniedError,
    ResourceNotFoundError,
    UnsupportedDocumentTypeError,
)
from app.database.connection import get_db
from app.database.repositories.job_repository import JobRepository
from app.rag.exceptions import RAGError
from app.schemas.auth import UserPublic
from app.schemas.matching import CompatibilityBreakdown, MatchingRequest, MatchingResponse
from app.schemas.rag import InternshipJob
from app.services.user_detail_service import UserDetailService

router = APIRouter(prefix="/matching", tags=["matching"])


async def _read_upload(file: UploadFile, settings: Settings) -> bytes:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    try:
        return await file.read(max_bytes + 1)
    finally:
        await file.close()


def _raise_document_http_error(exc: Exception) -> None:
    if isinstance(exc, DocumentTooLargeError):
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc))
    if isinstance(exc, UnsupportedDocumentTypeError):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        )
    if isinstance(exc, (EmptyDocumentError, InvalidDocumentError)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    if isinstance(exc, DocumentParsingError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    raise exc


def _parse_optional_uuid(value: str, field_name: str) -> uuid.UUID | None:
    if not value.strip():
        return None
    try:
        return uuid.UUID(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must be a valid UUID",
        ) from exc


@router.post("", response_model=MatchingResponse)
async def match_internships(
    file: UploadFile | None = File(
        default=None,
        description="Optional PDF/DOCX resume. Parsed, saved, then used for matching.",
    ),
    user_detail_id: str = Form(
        default="",
        description="Optional existing parsed resume ID. Do not send with file.",
    ),
    current_user: UserPublic = Depends(get_current_user),
    orchestrator: MatchingOrchestrator = Depends(get_matching_orchestrator),
    detail_service: UserDetailService = Depends(get_user_detail_service),
    settings: Settings = Depends(get_settings),
) -> MatchingResponse:
    """Match internships using an existing parsed resume or a new upload."""
    selected_detail_id = _parse_optional_uuid(user_detail_id, "user_detail_id")
    has_upload = file is not None and bool((file.filename or "").strip())
    if selected_detail_id is not None and has_upload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide either user_detail_id or file, not both",
        )

    if has_upload and file is not None:
        content = await _read_upload(file, settings)
        try:
            parsed = await detail_service.parse_resume(
                current_user.id,
                file.filename or "",
                content,
            )
        except (
            DocumentParsingError,
            DocumentTooLargeError,
            EmptyDocumentError,
            InvalidDocumentError,
            UnsupportedDocumentTypeError,
        ) as exc:
            _raise_document_http_error(exc)
            raise AssertionError("unreachable") from exc
        selected_detail_id = parsed.id

    try:
        return await orchestrator.match(
            current_user.id,
            MatchingRequest(user_detail_id=selected_detail_id),
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ResourceAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidDocumentSelectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RAGError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internship retrieval is temporarily unavailable",
        ) from exc


@router.post("/compare/{job_id}", response_model=CompatibilityBreakdown)
async def compare_job_compatibility(
    job_id: uuid.UUID,
    user_detail_id: str = Form(
        default="",
        description="Optional existing parsed resume ID.",
    ),
    current_user: UserPublic = Depends(get_current_user),
    orchestrator: MatchingOrchestrator = Depends(get_matching_orchestrator),
    db: AsyncSession = Depends(get_db),
) -> CompatibilityBreakdown:
    """Compare the authenticated candidate against a specific internship listing."""
    selected_detail_id = _parse_optional_uuid(user_detail_id, "user_detail_id")
    job_model = await JobRepository(db).get_by_id(job_id)
    if job_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    job_schema = InternshipJob(
        title=job_model.title,
        company=job_model.company,
        description=job_model.description,
        skills_required=job_model.required_skills,
        location=job_model.location,
        apply_url=job_model.apply_url,
        source=job_model.source,
        job_type=job_model.job_type,
        stipend=job_model.salary,
        duration=job_model.duration,
    )
    try:
        return await orchestrator.compare_job(
            current_user.id,
            job_schema,
            MatchingRequest(user_detail_id=selected_detail_id),
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ResourceAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidDocumentSelectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
