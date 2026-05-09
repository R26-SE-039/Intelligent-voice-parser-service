"""Pydantic schemas for speech-to-text API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CaptionLine(BaseModel):
    """Normalized caption line returned by the service."""

    id: str
    speaker: str
    text: str
    created_at: str


class MeetingCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    mode: str = "instant"
    scheduled_at: str | None = None


class MeetingJoinRequest(BaseModel):
    meeting_id: str
    passcode: str


class MeetingResponse(BaseModel):
    status: str
    meeting_id: str
    passcode: str
    invite_link: str
    name: str | None = None
