import type { TournamentListItem } from "./types";

export const TIER_OPTIONS = ["All", "Ranked", "Cash Cup", "FNCS", "Victory", "Other"] as const;

export type TierOption = (typeof TIER_OPTIONS)[number];

export function inferTier(tournament: TournamentListItem): TierOption {
  const haystack = [
    tournament.eventId,
    tournament.eventGroup ?? "",
    tournament.displayData.longFormatTitle ?? "",
    tournament.displayData.titleLine1 ?? "",
  ]
    .join(" ")
    .toLowerCase();

  if (haystack.includes("fncs")) return "FNCS";
  if (haystack.includes("ranked")) return "Ranked";
  if (haystack.includes("cashcup") || haystack.includes("cash cup")) return "Cash Cup";
  if (haystack.includes("victory")) return "Victory";
  if (haystack.includes("cup") || haystack.includes("series")) return "Other";
  return "Other";
}

export function filterByTier(
  tournaments: TournamentListItem[],
  tier: TierOption,
): TournamentListItem[] {
  if (tier === "All") return tournaments;
  return tournaments.filter((t) => inferTier(t) === tier);
}
