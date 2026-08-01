import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchPlayerPlacements } from "@/lib/api";

export const revalidate = 300;

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;

  let data;
  try {
    data = await fetchPlayerPlacements(accountId);
  } catch {
    notFound();
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-violet-400 hover:text-violet-300">
        ← Tournaments
      </Link>

      <h1 className="mt-6 text-2xl font-bold text-white">Player history</h1>
      <p className="mt-1 break-all text-sm text-zinc-400">{accountId}</p>

      <div className="mt-8 overflow-x-auto rounded-lg border border-zinc-800">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-zinc-900 text-zinc-300">
            <tr>
              <th className="px-4 py-3">Rank</th>
              <th className="px-4 py-3">Leaderboard</th>
              <th className="px-4 py-3">Window</th>
              <th className="px-4 py-3">Team</th>
            </tr>
          </thead>
          <tbody>
            {data.placements.map((placement) => (
              <tr key={`${placement.leaderboardEventWindowId}-${placement.teamId}`} className="border-t border-zinc-800">
                <td className="px-4 py-3 font-semibold text-white">{placement.rank ?? "-"}</td>
                <td className="px-4 py-3">
                  <Link
                    href={`/leaderboard/${encodeURIComponent(placement.leaderboardEventId)}/${encodeURIComponent(placement.leaderboardEventWindowId)}`}
                    className="text-violet-400 hover:text-violet-300 break-all"
                  >
                    {placement.leaderboardEventId}
                  </Link>
                </td>
                <td className="px-4 py-3 text-zinc-300 break-all">{placement.leaderboardEventWindowId}</td>
                <td className="px-4 py-3 text-zinc-300 break-all">{placement.teamId}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
