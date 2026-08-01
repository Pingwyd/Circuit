from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tournament(Base):
    __tablename__ = "tournaments"
    __table_args__ = (Index("idx_tournaments_regions", "regions", postgresql_using="gin"),)

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_group: Mapped[str | None] = mapped_column(Text)
    regions: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    platforms: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    display_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    event_windows: Mapped[list["EventWindow"]] = relationship(back_populates="tournament")


class EventWindow(Base):
    __tablename__ = "event_windows"
    __table_args__ = (Index("idx_windows_live", "begin_time", "end_time"),)

    event_window_id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tournaments.event_id", ondelete="CASCADE"), nullable=False
    )
    round: Mapped[int | None] = mapped_column(Integer)
    begin_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    playlist_id: Mapped[str | None] = mapped_column(Text)
    match_cap: Mapped[int | None] = mapped_column(Integer)
    require_all_tokens: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    require_any_tokens: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tournament: Mapped["Tournament"] = relationship(back_populates="event_windows")
    score_locations: Mapped[list["ScoreLocation"]] = relationship(back_populates="event_window")


class ScoreLocation(Base):
    __tablename__ = "score_locations"
    __table_args__ = (
        UniqueConstraint(
            "leaderboard_event_id",
            "leaderboard_event_window_id",
            name="uq_score_locations_lb_ids",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_window_id: Mapped[str] = mapped_column(
        Text, ForeignKey("event_windows.event_window_id", ondelete="CASCADE"), nullable=False
    )
    leaderboard_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    leaderboard_event_window_id: Mapped[str] = mapped_column(Text, nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    payout_tables: Mapped[dict | list | None] = mapped_column(JSONB)
    scoring_rules: Mapped[dict | list | None] = mapped_column(JSONB)

    event_window: Mapped["EventWindow"] = relationship(back_populates="score_locations")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (Index("idx_players_username", text("lower(username)")),)

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text)
    flag_token: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "leaderboard_event_id",
            "leaderboard_event_window_id",
            "page",
            "source_updated_at",
            name="uq_leaderboard_snapshots_dedupe",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    leaderboard_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    leaderboard_event_window_id: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    total_pages: Mapped[int | None] = mapped_column(Integer)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    entries: Mapped[dict | list] = mapped_column(JSONB, nullable=False)


class LeaderboardCurrent(Base):
    __tablename__ = "leaderboard_current"
    __table_args__ = (
        Index(
            "idx_current_rank",
            "leaderboard_event_id",
            "leaderboard_event_window_id",
            "rank",
        ),
    )

    leaderboard_event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    leaderboard_event_window_id: Mapped[str] = mapped_column(Text, primary_key=True)
    team_id: Mapped[str] = mapped_column(Text, primary_key=True)
    rank: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[Decimal | None] = mapped_column(Numeric)
    points_earned: Mapped[Decimal | None] = mapped_column(Numeric)
    percentile: Mapped[Decimal | None] = mapped_column(Numeric)
    players: Mapped[dict | list | None] = mapped_column(JSONB)
    session_history: Mapped[dict | list | None] = mapped_column(JSONB)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeaderboardEntryPlayer(Base):
    __tablename__ = "leaderboard_entry_players"
    __table_args__ = (Index("idx_entry_players_account", "account_id"),)

    leaderboard_event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    leaderboard_event_window_id: Mapped[str] = mapped_column(Text, primary_key=True)
    team_id: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    rank: Mapped[int | None] = mapped_column(Integer)
