from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    role: Literal["operator", "engineer", "planner", "admin"]
    password: str = Field(min_length=1, max_length=256)


class Acknowledge(Input):
    note: str = Field(min_length=5, max_length=2000)


class Transition(Input):
    status: str = Field(max_length=24)
    note: str = Field(min_length=5, max_length=2000)
    verification_evidence: str | None = Field(default=None, max_length=4000)


class ActionCreate(Input):
    incident_id: str = Field(max_length=160)
    assignee_id: str = Field(max_length=160)
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    description: str = Field(min_length=10, max_length=4000)
    due_at: datetime

    @field_validator("due_at")
    @classmethod
    def utc_required(cls, v):
        if v.tzinfo is None: raise ValueError("Use an ISO 8601 timestamp with timezone")
        return v


class Assignment(Input):
    assignee_id: str = Field(max_length=160)
    note: str = Field(min_length=5, max_length=2000)


class IncidentCreate(Input):
    alarm_id: str = Field(max_length=160)
    title: str = Field(min_length=10, max_length=240)


class PlantCreate(Input):
    name: str = Field(min_length=3, max_length=120)
    location: str = Field(min_length=2, max_length=120)
    timezone: str = Field(default="Asia/Kolkata", max_length=80)

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, v):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: ZoneInfo(v)
        except ZoneInfoNotFoundError: raise ValueError("Unknown IANA timezone")
        return v


class MachineCreate(Input):
    plant_id: str = Field(max_length=160)
    name: str = Field(min_length=3, max_length=120)
    kind: str = Field(min_length=3, max_length=80)


class ZoneCreate(Input):
    plant_id: str = Field(max_length=160)
    machine_id: str = Field(max_length=160)
    name: str = Field(min_length=3, max_length=120)
    restriction: str = Field(min_length=5, max_length=240)


class InterlockCreate(Input):
    machine_id: str = Field(max_length=160)
    zone_id: str = Field(max_length=160)
    name: str = Field(min_length=3, max_length=120)
    mandatory: bool = True


class DefinitionCreate(Input):
    machine_id: str = Field(max_length=160)
    name: str = Field(min_length=3, max_length=160)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    ack_deadline_seconds: int = Field(ge=10, le=86400)
    source: str = Field(default="PLC", min_length=2, max_length=80)


class MachineStateCreate(Input):
    state: Literal["RUNNING", "STOPPED", "MAINTENANCE", "FAULT"]
    interlock_state: Literal["ENGAGED", "RELEASED", "BYPASSED", "FAILED"]
    guard_state: Literal["OPEN", "CLOSED"]
    reason: str = Field(min_length=5, max_length=240)
