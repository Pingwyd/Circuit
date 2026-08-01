from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_OsirionConfig = ConfigDict(populate_by_name=True, extra="ignore")

TournamentRegion = Literal[
    "OCE", "ASIA", "ME", "EU", "BR", "NAC", "NAE", "NAW", "ONSITE"
]

ALL_TOURNAMENT_REGIONS: tuple[TournamentRegion, ...] = (
    "OCE",
    "ASIA",
    "ME",
    "EU",
    "BR",
    "NAC",
    "NAE",
    "NAW",
    "ONSITE",
)


class TournamentsDataDisplayData(BaseModel):
    model_config = _OsirionConfig

    tournament_display_id: str = Field(alias="tournamentDisplayId")
    background_left_color: str | None = Field(default=None, alias="backgroundLeftColor")
    background_right_color: str | None = Field(default=None, alias="backgroundRightColor")
    background_text_color: str | None = Field(default=None, alias="backgroundTextColor")
    base_color: str | None = Field(default=None, alias="baseColor")
    details_description: str | None = Field(default=None, alias="detailsDescription")
    flavor_description: str | None = Field(default=None, alias="flavorDescription")
    highlight_color: str | None = Field(default=None, alias="highlightColor")
    loading_screen_image: str | None = Field(default=None, alias="loadingScreenImage")
    long_format_title: str | None = Field(default=None, alias="longFormatTitle")
    playlist_tile_image: str | None = Field(default=None, alias="playlistTileImage")
    poster_back_image: str | None = Field(default=None, alias="posterBackImage")
    poster_fade_color: str | None = Field(default=None, alias="posterFadeColor")
    poster_front_image: str | None = Field(default=None, alias="posterFrontImage")
    primary_color: str | None = Field(default=None, alias="primaryColor")
    secondary_color: str | None = Field(default=None, alias="secondaryColor")
    shadow_color: str | None = Field(default=None, alias="shadowColor")
    title_color: str | None = Field(default=None, alias="titleColor")
    title_line1: str | None = Field(default=None, alias="titleLine1")
    title_line2: str | None = Field(default=None, alias="titleLine2")
    square_poster_image: str | None = Field(default=None, alias="squarePosterImage")
    tournament_view_background_image: str | None = Field(
        default=None, alias="tournamentViewBackgroundImage"
    )
    background_title: str | None = Field(default=None, alias="backgroundTitle")
    round_names: list[str] | None = Field(default=None, alias="roundNames")
    series_point_leaderboard_name: str | None = Field(
        default=None, alias="seriesPointLeaderboardName"
    )
    playlist_description: str | None = Field(default=None, alias="playlistDescription")


class TournamentsDataPayoutTablePayout(BaseModel):
    model_config = _OsirionConfig

    reward_type: str = Field(alias="rewardType")
    reward_mode: str = Field(alias="rewardMode")
    value: str
    quantity: int


class TournamentsDataPayoutTableRank(BaseModel):
    model_config = _OsirionConfig

    threshold: float
    payouts: list[TournamentsDataPayoutTablePayout]


class TournamentsDataPayoutTable(BaseModel):
    model_config = _OsirionConfig

    scoring_type: str = Field(alias="scoringType")
    ranks: list[TournamentsDataPayoutTableRank]
    score_id: str | None = Field(default=None, alias="scoreId")


class TournamentsDataScoringRewardTier(BaseModel):
    model_config = _OsirionConfig

    key_value: int = Field(alias="keyValue")
    points_earned: int = Field(alias="pointsEarned")
    multiplicative: bool


class TournamentsDataScoringRule(BaseModel):
    model_config = _OsirionConfig

    tracked_stat: str = Field(alias="trackedStat")
    match_rule: str = Field(alias="matchRule")
    reward_tiers: list[TournamentsDataScoringRewardTier] = Field(alias="rewardTiers")


class TournamentsDataScoreLocation(BaseModel):
    model_config = _OsirionConfig

    leaderboard_event_id: str = Field(alias="leaderboardEventId")
    leaderboard_event_window_id: str = Field(alias="leaderboardEventWindowId")
    is_main: bool = Field(alias="isMain")
    payout_tables: list[TournamentsDataPayoutTable] = Field(alias="payoutTables")
    scoring_rules: list[TournamentsDataScoringRule] = Field(alias="scoringRules")


class TournamentsDataEventWindow(BaseModel):
    model_config = _OsirionConfig

    event_window_id: str = Field(alias="eventWindowId")
    begin_time: datetime = Field(alias="beginTime")
    end_time: datetime = Field(alias="endTime")
    round: int
    score_locations: list[TournamentsDataScoreLocation] = Field(alias="scoreLocations")
    additional_requirements: list[str | list[str]] = Field(alias="additionalRequirements")
    require_all_tokens: list[str] = Field(alias="requireAllTokens")
    require_any_tokens: list[str] = Field(alias="requireAnyTokens")
    require_none_tokens_caller: list[str] = Field(alias="requireNoneTokensCaller")
    require_all_tokens_caller: list[str] = Field(alias="requireAllTokensCaller")
    require_any_tokens_caller: list[str] = Field(alias="requireAnyTokensCaller")
    playlist_id: str | None = Field(alias="playlistId")
    match_cap: int | None = Field(alias="matchCap")
    metadata: dict[str, Any] | None = None


class TournamentsDataTournament(BaseModel):
    model_config = _OsirionConfig

    event_id: str = Field(alias="eventId")
    event_group: str = Field(alias="eventGroup")
    regions: list[str]
    platforms: list[str]
    display_data: TournamentsDataDisplayData = Field(alias="displayData")
    event_windows: list[TournamentsDataEventWindow] = Field(alias="eventWindows")
    metadata: dict[str, Any] | None = None


class TournamentsDataResponse(BaseModel):
    model_config = _OsirionConfig

    success: bool
    region: TournamentRegion
    tournaments: list[TournamentsDataTournament]


class TournamentLeaderboardPlayer(BaseModel):
    model_config = _OsirionConfig

    account_id: str = Field(alias="accountId")
    username: str | None = None
    flag_token: str | None = Field(default=None, alias="flagToken")


class TournamentLeaderboardSessionHistoryEntry(BaseModel):
    model_config = _OsirionConfig

    session_id: str = Field(alias="sessionId")
    end_time: datetime = Field(alias="endTime")
    # TODO: inspect live payload
    tracked_stats: dict[str, Any] = Field(alias="trackedStats")


class TournamentLeaderboardEntry(BaseModel):
    model_config = _OsirionConfig

    team_id: str = Field(alias="teamId")
    players: list[TournamentLeaderboardPlayer]
    points_earned: float = Field(alias="pointsEarned")
    score: float
    rank: int
    percentile: float
    session_history: list[TournamentLeaderboardSessionHistoryEntry] = Field(alias="sessionHistory")
    unscored_sessions: list[str] = Field(alias="unscoredSessions")


class TournamentLeaderboard(BaseModel):
    model_config = _OsirionConfig

    leaderboard_event_id: str = Field(alias="leaderboardEventId")
    leaderboard_event_window_id: str = Field(alias="leaderboardEventWindowId")
    page: int
    total_pages: int = Field(alias="totalPages")
    updated_at: datetime = Field(alias="updatedAt")
    entries: list[TournamentLeaderboardEntry]


class TournamentLeaderboardDataResponse(BaseModel):
    model_config = _OsirionConfig

    success: bool
    leaderboard: TournamentLeaderboard
