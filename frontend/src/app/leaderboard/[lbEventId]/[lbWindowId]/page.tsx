import Link from "next/link";
import { notFound } from "next/navigation";

import { LeaderboardClient } from "@/components/LeaderboardClient";
import { fetchTournamentDetail, fetchTournaments } from "@/lib/api";

async function findWindowLive(lbEventId: string, lbWindowId: string): Promise<boolean> {
  const { tournaments } = await fetchTournaments({ live: true });
  for (const item of tournaments) {
    try {
      const detail = await fetchTournamentDetail(item.eventId);
      for (const window of detail.eventWindows) {
        if (!window.isLive) continue;
        for (const sl of window.scoreLocations) {
          if (
            sl.leaderboardEventId === lbEventId &&
            sl.leaderboardEventWindowId === lbWindowId
          ) {
            return true;
          }
        }
      }
    } catch {
      continue;
    }
  }
  return false;
}

export default async function LeaderboardPage({
  params,
  searchParams,
}: {
  params: Promise<{ lbEventId: string; lbWindowId: string }>;
  searchParams: Promise<{ page?: string }>;
}) {
  const { lbEventId, lbWindowId } = await params;
  const { page: pageParam } = await searchParams;
  const page = pageParam ? Number(pageParam) : 0;
  if (Number.isNaN(page)) notFound();

  const isLive = await findWindowLive(lbEventId, lbWindowId);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <Link href="/" className="text-sm text-violet-400 hover:text-violet-300">
        ← Tournaments
      </Link>
      <div className="mt-6">
        <LeaderboardClient
          lbEventId={lbEventId}
          lbWindowId={lbWindowId}
          initialPage={page}
          isLive={isLive}
        />
      </div>
    </main>
  );
}
