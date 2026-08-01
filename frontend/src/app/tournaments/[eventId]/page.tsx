import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchTournamentDetail } from "@/lib/api";
import { themeStyle, tournamentTitle } from "@/lib/theme";

export const revalidate = 300;

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default async function TournamentDetailPage({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = await params;

  let tournament;
  try {
    tournament = await fetchTournamentDetail(eventId);
  } catch {
    notFound();
  }

  const title = tournamentTitle(tournament.displayData);
  const poster = tournament.displayData.posterFrontImage;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <Link href="/" className="text-sm text-violet-400 hover:text-violet-300">
        ← All tournaments
      </Link>

      <section
        className="mt-6 overflow-hidden rounded-2xl border border-zinc-800"
        style={themeStyle(tournament.displayData)}
      >
        <div className="relative min-h-[220px]">
          {poster ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={poster} alt={title} className="absolute inset-0 h-full w-full object-cover opacity-40" />
          ) : null}
          <div className="relative p-8">
            <div className="flex flex-wrap gap-2">
              {tournament.regions.map((region) => (
                <span key={region} className="rounded-full bg-black/40 px-2 py-0.5 text-xs">
                  {region}
                </span>
              ))}
            </div>
            <h1 className="mt-3 text-3xl font-bold">{title}</h1>
            {tournament.displayData.flavorDescription ? (
              <p className="mt-2 max-w-2xl text-sm opacity-90">
                {tournament.displayData.flavorDescription}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="mb-4 text-xl font-semibold text-white">Event windows</h2>
        <div className="space-y-3">
          {tournament.eventWindows.map((window) => (
            <div
              key={window.eventWindowId}
              className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-white">{window.eventWindowId}</p>
                  <p className="text-sm text-zinc-400">
                    {formatWhen(window.beginTime)} → {formatWhen(window.endTime)}
                  </p>
                </div>
                {window.isLive ? (
                  <span className="rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold uppercase text-white">
                    Live
                  </span>
                ) : (
                  <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-200">
                    {new Date(window.endTime) < new Date() ? "Ended" : "Upcoming"}
                  </span>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {window.scoreLocations
                  .filter((sl) => sl.isMain)
                  .map((sl) => (
                    <Link
                      key={`${sl.leaderboardEventId}-${sl.leaderboardEventWindowId}`}
                      href={`/leaderboard/${encodeURIComponent(sl.leaderboardEventId)}/${encodeURIComponent(sl.leaderboardEventWindowId)}`}
                      className="rounded-md bg-violet-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-600"
                    >
                      View leaderboard
                    </Link>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
