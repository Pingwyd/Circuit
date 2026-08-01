import type {
  LeaderboardResponse,
  PlayerPlacementsResponse,
  PlayerSearchResponse,
  TournamentDetail,
  TournamentListResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchTournaments(params?: {
  region?: string;
  live?: boolean;
}): Promise<TournamentListResponse> {
  const search = new URLSearchParams();
  if (params?.region) search.set("region", params.region);
  if (params?.live !== undefined) search.set("live", String(params.live));
  const query = search.toString();
  return apiFetch(`/tournaments${query ? `?${query}` : ""}`, {
    next: { revalidate: 300 },
  });
}

export async function fetchTournamentDetail(eventId: string): Promise<TournamentDetail> {
  return apiFetch(`/tournaments/${encodeURIComponent(eventId)}`, {
    next: { revalidate: 300 },
  });
}

export async function fetchLeaderboard(
  lbEventId: string,
  lbWindowId: string,
  page: number,
): Promise<{ data: LeaderboardResponse; status: number }> {
  const response = await fetch(
    `${API_BASE}/leaderboard/${encodeURIComponent(lbEventId)}/${encodeURIComponent(lbWindowId)}?page=${page}`,
    { headers: { Accept: "application/json" }, cache: "no-store" },
  );
  const data = (await response.json()) as LeaderboardResponse;
  return { data, status: response.status };
}

export async function searchPlayers(name: string): Promise<PlayerSearchResponse> {
  return apiFetch(`/players/search?name=${encodeURIComponent(name)}`, {
    cache: "no-store",
  });
}

export async function fetchPlayerPlacements(
  accountId: string,
): Promise<PlayerPlacementsResponse> {
  return apiFetch(`/players/${encodeURIComponent(accountId)}/placements`, {
    next: { revalidate: 300 },
  });
}
