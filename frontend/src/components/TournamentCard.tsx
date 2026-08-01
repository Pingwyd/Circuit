import Link from "next/link";

import { themeStyle, tournamentTitle } from "@/lib/theme";
import type { TournamentListItem } from "@/lib/types";

export function TournamentCard({ tournament }: { tournament: TournamentListItem }) {
  const title = tournamentTitle(tournament.displayData);
  const poster = tournament.displayData.posterFrontImage;

  return (
    <Link
      href={`/tournaments/${tournament.eventId}`}
      className="group overflow-hidden rounded-xl border border-zinc-800 shadow-lg transition hover:scale-[1.01] hover:border-zinc-600"
      style={themeStyle(tournament.displayData)}
    >
      <div className="relative aspect-[3/4] w-full overflow-hidden">
        {poster ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={poster}
            alt={title}
            className="h-full w-full object-cover transition group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-end p-4">
            <h2 className="text-xl font-bold">{title}</h2>
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-4">
          <div className="mb-2 flex flex-wrap gap-2">
            {tournament.isLive ? (
              <span className="rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold uppercase text-white">
                Live
              </span>
            ) : null}
            {tournament.regions.slice(0, 3).map((region) => (
              <span
                key={region}
                className="rounded-full bg-black/50 px-2 py-0.5 text-xs text-white/90"
              >
                {region}
              </span>
            ))}
          </div>
          <h2 className="line-clamp-2 text-lg font-bold leading-tight">{title}</h2>
        </div>
      </div>
    </Link>
  );
}
