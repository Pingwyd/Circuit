"""initial schema

Revision ID: bef4e0d65eaf
Revises:
Create Date: 2026-08-01 19:22:26.115554

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bef4e0d65eaf"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tournaments",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("event_group", sa.Text(), nullable=True),
        sa.Column(
            "regions",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "platforms",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("display_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "idx_tournaments_regions",
        "tournaments",
        ["regions"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "event_windows",
        sa.Column("event_window_id", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.Column("begin_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("playlist_id", sa.Text(), nullable=True),
        sa.Column("match_cap", sa.Integer(), nullable=True),
        sa.Column(
            "require_all_tokens",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=True,
        ),
        sa.Column(
            "require_any_tokens",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=True,
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["tournaments.event_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_window_id"),
    )
    op.create_index(
        "idx_windows_live",
        "event_windows",
        ["begin_time", "end_time"],
        unique=False,
    )

    op.create_table(
        "score_locations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_window_id", sa.Text(), nullable=False),
        sa.Column("leaderboard_event_id", sa.Text(), nullable=False),
        sa.Column("leaderboard_event_window_id", sa.Text(), nullable=False),
        sa.Column("is_main", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("payout_tables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scoring_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_window_id"],
            ["event_windows.event_window_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "leaderboard_event_id",
            "leaderboard_event_window_id",
            name="uq_score_locations_lb_ids",
        ),
    )

    op.create_table(
        "players",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("flag_token", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_index(
        "idx_players_username",
        "players",
        [sa.text("lower(username)")],
        unique=False,
    )

    op.create_table(
        "leaderboard_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("leaderboard_event_id", sa.Text(), nullable=False),
        sa.Column("leaderboard_event_window_id", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("entries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "leaderboard_event_id",
            "leaderboard_event_window_id",
            "page",
            "source_updated_at",
            name="uq_leaderboard_snapshots_dedupe",
        ),
    )

    op.create_table(
        "leaderboard_current",
        sa.Column("leaderboard_event_id", sa.Text(), nullable=False),
        sa.Column("leaderboard_event_window_id", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("points_earned", sa.Numeric(), nullable=True),
        sa.Column("percentile", sa.Numeric(), nullable=True),
        sa.Column("players", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("session_history", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "leaderboard_event_id",
            "leaderboard_event_window_id",
            "team_id",
        ),
    )
    op.create_index(
        "idx_current_rank",
        "leaderboard_current",
        ["leaderboard_event_id", "leaderboard_event_window_id", "rank"],
        unique=False,
    )

    op.create_table(
        "leaderboard_entry_players",
        sa.Column("leaderboard_event_id", sa.Text(), nullable=False),
        sa.Column("leaderboard_event_window_id", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint(
            "leaderboard_event_id",
            "leaderboard_event_window_id",
            "account_id",
        ),
    )
    op.create_index(
        "idx_entry_players_account",
        "leaderboard_entry_players",
        ["account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_entry_players_account", table_name="leaderboard_entry_players")
    op.drop_table("leaderboard_entry_players")
    op.drop_index("idx_current_rank", table_name="leaderboard_current")
    op.drop_table("leaderboard_current")
    op.drop_table("leaderboard_snapshots")
    op.drop_index("idx_players_username", table_name="players")
    op.drop_table("players")
    op.drop_table("score_locations")
    op.drop_index("idx_windows_live", table_name="event_windows")
    op.drop_table("event_windows")
    op.drop_index("idx_tournaments_regions", table_name="tournaments", postgresql_using="gin")
    op.drop_table("tournaments")
