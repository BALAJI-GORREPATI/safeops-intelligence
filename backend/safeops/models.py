"""Relational schema. Operational events are append-only through the service layer."""
from datetime import datetime, timezone
from sqlalchemy import (String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey,
                        UniqueConstraint, CheckConstraint, Index)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[str] = mapped_column(String(160), primary_key=True, comment="Immutable canonical identifier")
    workspace_id: Mapped[str] = mapped_column(String(80), index=True, comment="Dataset run identifier or manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, comment="UTC record ingestion time")


def enum_check(field, values):
    return CheckConstraint(f"{field} IN ({','.join(repr(v) for v in values.split())})", name=f"ck_{field}")


class Plant(Record, Base):
    __tablename__ = "plants"
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)


class Machine(Record, Base):
    __tablename__ = "machines"
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("plant_id", "name"),)


class SafetyZone(Record, Base):
    __tablename__ = "safety_zones"
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    restriction: Mapped[str] = mapped_column(String(240), default="Guard must be closed during operation")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MachineSafetyZone(Record, Base):
    __tablename__ = "machine_safety_zones"
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("safety_zones.id"))
    __table_args__ = (UniqueConstraint("machine_id", "zone_id"),)


class Interlock(Record, Base):
    __tablename__ = "interlocks"
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("safety_zones.id"))
    name: Mapped[str] = mapped_column(String(120))
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


SEVERITIES = "LOW MEDIUM HIGH CRITICAL"
class AlarmDefinition(Record, Base):
    __tablename__ = "alarm_definitions"
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    severity: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(80), default="PLC")
    ack_deadline_seconds: Mapped[int] = mapped_column(Integer, comment="Project demo response deadline in seconds")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (enum_check("severity", SEVERITIES), CheckConstraint("ack_deadline_seconds > 0"))


class ApplicationUser(Record, Base):
    __tablename__ = "application_users"
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    __table_args__ = (enum_check("role", "operator engineer planner admin"),)


class OperatorShift(Record, Base):
    __tablename__ = "operator_shifts"
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("application_users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("ends_at > starts_at"),)


class MachineStateEvent(Record, Base):
    __tablename__ = "machine_state_events"
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    state: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str] = mapped_column(String(240))
    __table_args__ = (enum_check("state", "RUNNING STOPPED MAINTENANCE FAULT"),)


class InterlockStateEvent(Record, Base):
    __tablename__ = "interlock_state_events"
    interlock_id: Mapped[str] = mapped_column(ForeignKey("interlocks.id"), index=True)
    machine_state_id: Mapped[str] = mapped_column(ForeignKey("machine_state_events.id"), index=True)
    state: Mapped[str] = mapped_column(String(20))
    guard_state: Mapped[str] = mapped_column(String(12))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (enum_check("state", "ENGAGED RELEASED BYPASSED FAILED"), enum_check("guard_state", "OPEN CLOSED"))


class AlarmEvent(Record, Base):
    __tablename__ = "alarm_events"
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    definition_id: Mapped[str] = mapped_column(ForeignKey("alarm_definitions.id"), index=True)
    machine_state_id: Mapped[str] = mapped_column(ForeignKey("machine_state_events.id"))
    shift_id: Mapped[str] = mapped_column(ForeignKey("operator_shifts.id"))
    source_event_id: Mapped[str] = mapped_column(String(160), index=True, comment="Physical source identity; repeats indicate replay")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    message: Mapped[str] = mapped_column(String(240))
    value: Mapped[float | None] = mapped_column(Float, comment="Sensor reading, degrees C for temperature definitions")
    __table_args__ = (Index("ix_alarm_workspace_machine_time", "workspace_id", "machine_id", "occurred_at"),)


class Acknowledgement(Record, Base):
    __tablename__ = "acknowledgements"
    alarm_id: Mapped[str] = mapped_column(ForeignKey("alarm_events.id"), index=True, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("application_users.id"))
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text)


class Incident(Record, Base):
    __tablename__ = "incidents"
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rule_id: Mapped[str] = mapped_column(String(80))
    __table_args__ = (enum_check("severity", SEVERITIES), enum_check("status", "OPEN INVESTIGATING ACTION_PENDING RESOLVED CLOSED"))


class IncidentAlarm(Record, Base):
    __tablename__ = "incident_alarms"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    alarm_id: Mapped[str] = mapped_column(ForeignKey("alarm_events.id"), index=True)
    __table_args__ = (UniqueConstraint("incident_id", "alarm_id"),)


class CorrectiveAction(Record, Base):
    __tablename__ = "corrective_actions"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    assignee_id: Mapped[str] = mapped_column(ForeignKey("application_users.id"))
    priority: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("application_users.id"))
    verification_evidence: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (enum_check("priority", SEVERITIES), enum_check("status", "OPEN IN_PROGRESS COMPLETED VERIFIED CLOSED"))


class IncidentStatusHistory(Record, Base):
    __tablename__ = "incident_status_history"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    user_id: Mapped[str] = mapped_column(ForeignKey("application_users.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text)


class CorrectiveActionStatusHistory(Record, Base):
    __tablename__ = "corrective_action_status_history"
    action_id: Mapped[str] = mapped_column(ForeignKey("corrective_actions.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    user_id: Mapped[str] = mapped_column(ForeignKey("application_users.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text)


class AuditEvent(Record, Base):
    __tablename__ = "audit_events"
    entity: Mapped[str] = mapped_column(String(80))
    record_id: Mapped[str] = mapped_column(String(160), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("application_users.id"))
    operation: Mapped[str] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(JSON)


class DatasetGenerationRun(Base):
    __tablename__ = "dataset_generation_runs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSON)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    checksum: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ValidationResult(Base):
    __tablename__ = "validation_results"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("dataset_generation_runs.id"), index=True)
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Deliberately not a column of any operational table. The detector never receives this table.
class GroundTruth(Base):
    __tablename__ = "ground_truth"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(80), index=True)
    target_entity: Mapped[str] = mapped_column(String(80))
    target_record_id: Mapped[str] = mapped_column(String(160))
    anomaly_type: Mapped[str] = mapped_column(String(80))
    expected_decision: Mapped[bool] = mapped_column(Boolean, default=True)
    rule_id: Mapped[str] = mapped_column(String(80))
    explanation: Mapped[str] = mapped_column(Text)
    related_record_ids: Mapped[list] = mapped_column(JSON)


OPERATIONAL = {t.name: t for t in Base.metadata.sorted_tables if t.name not in {
    "ground_truth", "dataset_generation_runs", "validation_results"}}
