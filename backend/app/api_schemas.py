from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TournamentListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(serialization_alias="eventId")
    event_group: str | None = Field(serialization_alias="eventGroup")
    regions: list[str]
    platforms: list[str]
    display_data: dict[str, Any] = Field(serialization_alias="displayData")
    is_live: bool = Field(serialization_alias="isLive")
    last_seen: datetime = Field(serialization_alias="lastSeen")


class TournamentListResponse(BaseModel):
    tournaments: list[TournamentListItem]


class ScoreLocationItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    leaderboard_event_id: str = Field(serialization_alias="leaderboardEventId")
    leaderboard_event_window_id: str = Field(serialization_alias="leaderboardEventWindowId")
    is_main: bool = Field(serialization_alias="isMain")


class EventWindowDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_window_id: str = Field(serialization_alias="eventWindowId")
    round: int | None
    begin_time: datetime = Field(serialization_alias="beginTime")
    end_time: datetime = Field(serialization_alias="endTime")
    is_live: bool = Field(serialization_alias="isLive")
    playlist_id: str | None = Field(serialization_alias="playlistId")
    match_cap: int | None = Field(serialization_alias="matchCap")
    score_locations: list[ScoreLocationItem] = Field(serialization_alias="scoreLocations")


class TournamentDetailResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(serialization_alias="eventId")
    event_group: str | None = Field(serialization_alias="eventGroup")
    regions: list[str]
    platforms: list[str]
    display_data: dict[str, Any] = Field(serialization_alias="displayData")
    metadata: dict[str, Any] | None = None
    event_windows: list[EventWindowDetail] = Field(serialization_alias="eventWindows")


class LeaderboardPlayerItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_id: str = Field(serialization_alias="accountId")
    username: str | None = None
    flag_token: str | None = Field(default=None, serialization_alias="flagToken")


class LeaderboardEntryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    team_id: str = Field(serialization_alias="teamId")
    rank: int | None
    score: float | None
    points_earned: float | None = Field(serialization_alias="pointsEarned")
    percentile: float | None
    players: list[Any]
    session_history: list[Any] = Field(serialization_alias="sessionHistory")


class LeaderboardReadyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["ready"] = "ready"
    leaderboard_event_id: str = Field(serialization_alias="leaderboardEventId")
    leaderboard_event_window_id: str = Field(serialization_alias="leaderboardEventWindowId")
    page: int
    source_updated_at: datetime | None = Field(serialization_alias="sourceUpdatedAt")
    entries: list[LeaderboardEntryItem]


class LeaderboardLoadingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["loading"] = "loading"
    leaderboard_event_id: str = Field(serialization_alias="leaderboardEventId")
    leaderboard_event_window_id: str = Field(serialization_alias="leaderboardEventWindowId")
    page: int
    message: str = "Fetch enqueued; retry shortly"


class PlayerSearchItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_id: str = Field(serialization_alias="accountId")
    username: str | None = None
    flag_token: str | None = Field(default=None, serialization_alias="flagToken")


class PlayerSearchResponse(BaseModel):
    source: Literal["database", "lookup"]
    players: list[PlayerSearchItem]


class PlayerPlacementItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    leaderboard_event_id: str = Field(serialization_alias="leaderboardEventId")
    leaderboard_event_window_id: str = Field(serialization_alias="leaderboardEventWindowId")
    team_id: str = Field(serialization_alias="teamId")
    rank: int | None


class PlayerPlacementsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_id: str = Field(serialization_alias="accountId")
    placements: list[PlayerPlacementItem]
