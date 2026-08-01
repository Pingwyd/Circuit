"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { TournamentCard } from "@/components/TournamentCard";
import { filterByTier, TIER_OPTIONS, type TierOption } from "@/lib/tier";
import type { TournamentListItem } from "@/lib/types";

const REGIONS = ["All", "OCE", "ASIA", "ME", "EU", "BR", "NAC", "NAE", "NAW", "ONSITE"] as const;

export function TournamentListClient({
  tournaments,
  initialRegion,
}: {
  tournaments: TournamentListItem[];
  initialRegion?: string;
}) {
  const [tier, setTier] = useState<TierOption>("All");
  const [liveOnly, setLiveOnly] = useState(false);

  const filtered = useMemo(() => {
    let list = filterByTier(tournaments, tier);
    if (liveOnly) list = list.filter((t) => t.isLive);
    return list;
  }, [tournaments, tier, liveOnly]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-2">
          {REGIONS.map((region) => {
            const href =
              region === "All" ? "/" : `/?region=${encodeURIComponent(region)}`;
            const active =
              (region === "All" && !initialRegion) || initialRegion === region;
            return (
              <Link
                key={region}
                href={href}
                className={`rounded-full px-3 py-1 text-sm ${
                  active
                    ? "bg-violet-600 text-white"
                    : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                }`}
              >
                {region}
              </Link>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-2">
          {TIER_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setTier(option)}
              className={`rounded-full px-3 py-1 text-sm ${
                tier === option
                  ? "bg-cyan-600 text-white"
                  : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={liveOnly}
            onChange={(e) => setLiveOnly(e.target.checked)}
          />
          Live only
        </label>
      </div>

      <p className="text-sm text-zinc-400">{filtered.length} tournaments</p>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {filtered.map((tournament) => (
          <TournamentCard key={tournament.eventId} tournament={tournament} />
        ))}
      </div>
    </div>
  );
}
