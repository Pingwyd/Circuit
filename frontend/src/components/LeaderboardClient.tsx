"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { fetchLeaderboard } from "@/lib/api";
import type { LeaderboardReadyResponse } from "@/lib/types";

const POLL_MS = 75_000;

function formatRelative(iso: string | null): string {
  if (!iso) return "unknown";
  const delta = Date.now() - new Date(iso).getTime();
  const seconds = Math.max(0, Math.floor(delta / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function flagEmoji(token: string | null | undefined): string {
  if (!token || token.length !== 2) return "";
  const code = token.toUpperCase();
  return String.fromCodePoint(...[...code].map((c) => 127397 + c.charCodeAt(0)));
}

export function LeaderboardClient({
  lbEventId,
  lbWindowId,
  initialPage = 0,
  isLive,
}: {
  lbEventId: string;
  lbWindowId: string;
  initialPage?: number;
  isLive: boolean;
}) {
  const [page, setPage] = useState(initialPage);

  const query = useQuery({
    queryKey: ["leaderboard", lbEventId, lbWindowId, page],
    queryFn: () => fetchLeaderboard(lbEventId, lbWindowId, page),
    refetchInterval: isLive ? POLL_MS : false,
  });

  const ready = useMemo(() => {
    if (!query.data) return null;
    if (query.data.status === 200 && query.data.data.status === "ready") {
      return query.data.data as LeaderboardReadyResponse;
    }
    return null;
  }, [query.data]);

  const loading = query.data?.status === 202 || query.data?.data.status === "loading";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Leaderboard</h1>
          <p className="text-sm text-zinc-400 break-all">
            {lbEventId} / {lbWindowId}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="rounded bg-zinc-800 px-3 py-1 text-sm text-white disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-sm text-zinc-300">Page {page}</span>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
            className="rounded bg-zinc-800 px-3 py-1 text-sm text-white"
          >
            Next
          </button>
        </div>
      </div>

      {query.isLoading ? (
        <p className="text-zinc-400">Loading standings...</p>
      ) : null}

      {loading ? (
        <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 p-4 text-amber-100">
          Fetch enqueued. Polling until this page is cached...
        </div>
      ) : null}

      {ready ? (
        <>
          <p className="text-sm text-zinc-400">
            Updated {formatRelative(ready.sourceUpdatedAt)}
            {isLive ? ` · auto-refresh every ${POLL_MS / 1000}s` : ""}
          </p>
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-zinc-900 text-zinc-300">
                <tr>
                  <th className="px-4 py-3">Rank</th>
                  <th className="px-4 py-3">Team</th>
                  <th className="px-4 py-3">Score</th>
                  <th className="px-4 py-3">Points</th>
                  <th className="px-4 py-3">Pct</th>
                </tr>
              </thead>
              <tbody>
                {ready.entries.map((entry) => (
                  <tr key={entry.teamId} className="border-t border-zinc-800">
                    <td className="px-4 py-3 font-semibold text-white">{entry.rank}</td>
                    <td className="px-4 py-3 text-zinc-200">
                      {entry.players.map((player) => (
                        <div key={player.accountId}>
                          <Link
                            href={`/players/${player.accountId}`}
                            className="hover:text-violet-300"
                          >
                            {flagEmoji(player.flagToken)} {player.username ?? player.accountId}
                          </Link>
                        </div>
                      ))}
                    </td>
                    <td className="px-4 py-3">{entry.score ?? "-"}</td>
                    <td className="px-4 py-3">{entry.pointsEarned ?? "-"}</td>
                    <td className="px-4 py-3">
                      {entry.percentile != null ? `${entry.percentile.toFixed(1)}%` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {query.isError ? (
        <p className="text-red-400">Failed to load leaderboard.</p>
      ) : null}
    </div>
  );
}
