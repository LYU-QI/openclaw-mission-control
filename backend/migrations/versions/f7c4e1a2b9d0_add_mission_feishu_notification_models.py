"""add mission feishu notification models and task extension fields

Revision ID: f7c4e1a2b9d0
Revises: a9b1c2d3e4f7
Create Date: 2026-03-07 21:25:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7c4e1a2b9d0"
down_revision = "a9b1c2d3e4f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def table_exists(name: str) -> bool:
        return name in inspector.get_table_names()

    def column_exists(table: str, column: str) -> bool:
        return column in {item["name"] for item in inspector.get_columns(table)}

    def index_exists(table: str, index: str) -> bool:
        return index in {item["name"] for item in inspector.get_indexes(table)}

    if not column_exists("tasks", "external_source"):
        op.add_column("tasks", sa.Column("external_source", sa.String(), nullable=True))
    if not column_exists("tasks", "external_id"):
        op.add_column("tasks", sa.Column("external_id", sa.String(), nullable=True))
    if not column_exists("tasks", "result_summary"):
        op.add_column("tasks", sa.Column("result_summary", sa.String(), nullable=True))
    if not column_exists("tasks", "result_evidence_link"):
        op.add_column("tasks", sa.Column("result_evidence_link", sa.String(), nullable=True))
    if not column_exists("tasks", "result_risk"):
        op.add_column("tasks", sa.Column("result_risk", sa.String(), nullable=True))
    if not column_exists("tasks", "result_next_action"):
        op.add_column("tasks", sa.Column("result_next_action", sa.String(), nullable=True))
    if not column_exists("tasks", "owner_name"):
        op.add_column("tasks", sa.Column("owner_name", sa.String(), nullable=True))
    if not column_exists("tasks", "owner_feishu_id"):
        op.add_column("tasks", sa.Column("owner_feishu_id", sa.String(), nullable=True))
    if not column_exists("tasks", "milestone"):
        op.add_column("tasks", sa.Column("milestone", sa.String(), nullable=True))
    if not index_exists("tasks", op.f("ix_tasks_external_id")):
        op.create_index(op.f("ix_tasks_external_id"), "tasks", ["external_id"], unique=False)

    if not table_exists("missions"):
        op.create_table(
            "missions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("task_id", sa.Uuid(), nullable=False),
            sa.Column("board_id", sa.Uuid(), nullable=False),
            sa.Column("agent_id", sa.Uuid(), nullable=True),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("constraints", sa.JSON(), nullable=True),
            sa.Column("context_refs", sa.JSON(), nullable=True),
            sa.Column("approval_policy", sa.String(), nullable=False),
            sa.Column("approval_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("dispatched_at", sa.DateTime(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("result_summary", sa.Text(), nullable=True),
            sa.Column("result_evidence", sa.JSON(), nullable=True),
            sa.Column("result_risk", sa.String(), nullable=True),
            sa.Column("result_next_action", sa.Text(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False),
            sa.Column("max_retries", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
            sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not index_exists("missions", op.f("ix_missions_task_id")):
        op.create_index(op.f("ix_missions_task_id"), "missions", ["task_id"], unique=False)
    if not index_exists("missions", op.f("ix_missions_board_id")):
        op.create_index(op.f("ix_missions_board_id"), "missions", ["board_id"], unique=False)
    if not index_exists("missions", op.f("ix_missions_agent_id")):
        op.create_index(op.f("ix_missions_agent_id"), "missions", ["agent_id"], unique=False)
    if not index_exists("missions", op.f("ix_missions_status")):
        op.create_index(op.f("ix_missions_status"), "missions", ["status"], unique=False)

    if not table_exists("mission_subtasks"):
        op.create_table(
            "mission_subtasks",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("mission_id", sa.Uuid(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tool_scope", sa.JSON(), nullable=True),
            sa.Column("expected_output", sa.Text(), nullable=True),
            sa.Column("order", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("assigned_subagent_id", sa.String(), nullable=True),
            sa.Column("result_summary", sa.Text(), nullable=True),
            sa.Column("result_evidence", sa.JSON(), nullable=True),
            sa.Column("result_risk", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["mission_id"], ["missions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not index_exists("mission_subtasks", op.f("ix_mission_subtasks_mission_id")):
        op.create_index(
            op.f("ix_mission_subtasks_mission_id"),
            "mission_subtasks",
            ["mission_id"],
            unique=False,
        )
    if not index_exists("mission_subtasks", op.f("ix_mission_subtasks_status")):
        op.create_index(op.f("ix_mission_subtasks_status"), "mission_subtasks", ["status"], unique=False)

    if not table_exists("feishu_sync_configs"):
        op.create_table(
            "feishu_sync_configs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("board_id", sa.Uuid(), nullable=True),
            sa.Column("app_id", sa.String(), nullable=False),
            sa.Column("app_secret_encrypted", sa.Text(), nullable=False),
            sa.Column("bitable_app_token", sa.String(), nullable=False),
            sa.Column("bitable_table_id", sa.String(), nullable=False),
            sa.Column("field_mapping", sa.JSON(), nullable=False),
            sa.Column("sync_direction", sa.String(), nullable=False),
            sa.Column("sync_interval_minutes", sa.Integer(), nullable=False),
            sa.Column("last_sync_at", sa.DateTime(), nullable=True),
            sa.Column("sync_status", sa.String(), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not index_exists("feishu_sync_configs", op.f("ix_feishu_sync_configs_organization_id")):
        op.create_index(
            op.f("ix_feishu_sync_configs_organization_id"),
            "feishu_sync_configs",
            ["organization_id"],
            unique=False,
        )
    if not index_exists("feishu_sync_configs", op.f("ix_feishu_sync_configs_board_id")):
        op.create_index(
            op.f("ix_feishu_sync_configs_board_id"),
            "feishu_sync_configs",
            ["board_id"],
            unique=False,
        )

    if not table_exists("feishu_task_mappings"):
        op.create_table(
            "feishu_task_mappings",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("sync_config_id", sa.Uuid(), nullable=False),
            sa.Column("feishu_record_id", sa.String(), nullable=False),
            sa.Column("task_id", sa.Uuid(), nullable=False),
            sa.Column("last_feishu_update", sa.DateTime(), nullable=True),
            sa.Column("last_mc_update", sa.DateTime(), nullable=True),
            sa.Column("sync_hash", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["sync_config_id"], ["feishu_sync_configs.id"]),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not index_exists("feishu_task_mappings", op.f("ix_feishu_task_mappings_sync_config_id")):
        op.create_index(
            op.f("ix_feishu_task_mappings_sync_config_id"),
            "feishu_task_mappings",
            ["sync_config_id"],
            unique=False,
        )
    if not index_exists("feishu_task_mappings", op.f("ix_feishu_task_mappings_task_id")):
        op.create_index(
            op.f("ix_feishu_task_mappings_task_id"),
            "feishu_task_mappings",
            ["task_id"],
            unique=False,
        )
    if not index_exists("feishu_task_mappings", op.f("ix_feishu_task_mappings_feishu_record_id")):
        op.create_index(
            op.f("ix_feishu_task_mappings_feishu_record_id"),
            "feishu_task_mappings",
            ["feishu_record_id"],
            unique=False,
        )

    if not table_exists("notification_configs"):
        op.create_table(
            "notification_configs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("board_id", sa.Uuid(), nullable=True),
            sa.Column("channel_type", sa.String(), nullable=False),
            sa.Column("channel_config", sa.JSON(), nullable=False),
            sa.Column("notify_on_events", sa.JSON(), nullable=False),
            sa.Column("notify_interval_minutes", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not index_exists("notification_configs", op.f("ix_notification_configs_organization_id")):
        op.create_index(
            op.f("ix_notification_configs_organization_id"),
            "notification_configs",
            ["organization_id"],
            unique=False,
        )
    if not index_exists("notification_configs", op.f("ix_notification_configs_board_id")):
        op.create_index(
            op.f("ix_notification_configs_board_id"),
            "notification_configs",
            ["board_id"],
            unique=False,
        )

    if not table_exists("notification_logs"):
        op.create_table(
            "notification_logs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("notification_config_id", sa.Uuid(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("channel_type", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("response", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["notification_config_id"], ["notification_configs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not index_exists("notification_logs", op.f("ix_notification_logs_notification_config_id")):
        op.create_index(
            op.f("ix_notification_logs_notification_config_id"),
            "notification_logs",
            ["notification_config_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_notification_config_id"), table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index(op.f("ix_notification_configs_board_id"), table_name="notification_configs")
    op.drop_index(op.f("ix_notification_configs_organization_id"), table_name="notification_configs")
    op.drop_table("notification_configs")

    op.drop_index(op.f("ix_feishu_task_mappings_feishu_record_id"), table_name="feishu_task_mappings")
    op.drop_index(op.f("ix_feishu_task_mappings_task_id"), table_name="feishu_task_mappings")
    op.drop_index(op.f("ix_feishu_task_mappings_sync_config_id"), table_name="feishu_task_mappings")
    op.drop_table("feishu_task_mappings")

    op.drop_index(op.f("ix_feishu_sync_configs_board_id"), table_name="feishu_sync_configs")
    op.drop_index(op.f("ix_feishu_sync_configs_organization_id"), table_name="feishu_sync_configs")
    op.drop_table("feishu_sync_configs")

    op.drop_index(op.f("ix_mission_subtasks_status"), table_name="mission_subtasks")
    op.drop_index(op.f("ix_mission_subtasks_mission_id"), table_name="mission_subtasks")
    op.drop_table("mission_subtasks")

    op.drop_index(op.f("ix_missions_status"), table_name="missions")
    op.drop_index(op.f("ix_missions_agent_id"), table_name="missions")
    op.drop_index(op.f("ix_missions_board_id"), table_name="missions")
    op.drop_index(op.f("ix_missions_task_id"), table_name="missions")
    op.drop_table("missions")

    op.drop_index(op.f("ix_tasks_external_id"), table_name="tasks")
    op.drop_column("tasks", "milestone")
    op.drop_column("tasks", "owner_feishu_id")
    op.drop_column("tasks", "owner_name")
    op.drop_column("tasks", "result_next_action")
    op.drop_column("tasks", "result_risk")
    op.drop_column("tasks", "result_evidence_link")
    op.drop_column("tasks", "result_summary")
    op.drop_column("tasks", "external_id")
    op.drop_column("tasks", "external_source")
