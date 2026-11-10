"""Initial relational safety schema."""
from alembic import op
from safeops.models import Base

revision = "0001"
down_revision = None


def upgrade():
    Base.metadata.create_all(op.get_bind())
    # Protect authoritative histories from application-level update/delete mistakes.
    op.execute("""CREATE FUNCTION reject_safety_history_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Safety history is immutable'; END; $$ LANGUAGE plpgsql""")
    for table in ("alarm_events", "acknowledgements", "machine_state_events", "interlock_state_events",
                  "incident_status_history", "corrective_action_status_history", "audit_events"):
        op.execute(f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_safety_history_mutation()")


def downgrade():
    raise RuntimeError("Destructive downgrades require a separately reviewed database recovery procedure")
