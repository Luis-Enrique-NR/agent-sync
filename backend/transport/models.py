"""Strict transport models shared by ingestion, bus, and Portal adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MessageSnapshot(StrictModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    author_id: str = Field(min_length=1)
    seq: int = Field(ge=0)


class PortalEvent(StrictModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    time: datetime
    environment: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    message: MessageSnapshot | None = None


class TransportEnvelopeV1(StrictModel):
    schema_version: Literal[1] = 1
    event_id: str
    # Portal lifecycle events are admitted here as well as message events.
    # Keeping this as a string lets the integration catalog evolve without
    # making the transport parser silently discard events the EDA dispatcher
    # already knows how to handle.
    event_type: str = Field(min_length=1)
    event_time: datetime
    environment: str
    channel: str
    message: MessageSnapshot | None
    retracted: bool = False
