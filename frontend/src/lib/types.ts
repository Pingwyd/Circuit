export type DisplayData = {
  tournamentDisplayId?: string;
  posterFrontImage?: string;
  posterBackImage?: string;
  primaryColor?: string;
  secondaryColor?: string;
  backgroundLeftColor?: string;
  backgroundRightColor?: string;
  backgroundTextColor?: string;
  titleColor?: string;
  titleLine1?: string;
  titleLine2?: string;
  longFormatTitle?: string;
  flavorDescription?: string;
};

export type TournamentListItem = {
  eventId: string;
  eventGroup: string | null;
  regions: string[];
  platforms: string[];
  displayData: DisplayData;
  isLive: boolean;
  lastSeen: string;
};

export type TournamentListResponse = {
  tournaments: TournamentListItem[];
};

export type ScoreLocation = {
  leaderboardEventId: string;
  leaderboardEventWindowId: string;
  isMain: boolean;
};

export type EventWindow = {
  eventWindowId: string;
  round: number | null;
  beginTime: string;
  endTime: string;
  isLive: boolean;
  playlistId: string | null;
  matchCap: number | null;
  scoreLocations: ScoreLocation[];
};

export type TournamentDetail = {
  eventId: string;
  eventGroup: string | null;
  regions: string[];
  platforms: string[];
  displayData: DisplayData;
  metadata: Record<string, unknown> | null;
  eventWindows: EventWindow[];
};

export type LeaderboardPlayer = {
  accountId: string;
  username: string | null;
  flagToken: string | null;
};

export type LeaderboardEntry = {
  teamId: string;
  rank: number | null;
  score: number | null;
  pointsEarned: number | null;
  percentile: number | null;
  players: LeaderboardPlayer[];
  sessionHistory: unknown[];
};

export type LeaderboardReadyResponse = {
  status: "ready";
  leaderboardEventId: string;
  leaderboardEventWindowId: string;
  page: number;
  sourceUpdatedAt: string | null;
  entries: LeaderboardEntry[];
};

export type LeaderboardLoadingResponse = {
  status: "loading";
  leaderboardEventId: string;
  leaderboardEventWindowId: string;
  page: number;
  message: string;
};

export type LeaderboardResponse = LeaderboardReadyResponse | LeaderboardLoadingResponse;

export type PlayerSearchResponse = {
  source: "database" | "lookup";
  players: LeaderboardPlayer[];
};

export type PlayerPlacement = {
  leaderboardEventId: string;
  leaderboardEventWindowId: string;
  teamId: string;
  rank: number | null;
};

export type PlayerPlacementsResponse = {
  accountId: string;
  placements: PlayerPlacement[];
};
