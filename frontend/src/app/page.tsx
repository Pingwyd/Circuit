import { TournamentListClient } from "@/components/TournamentListClient";
import { fetchTournaments } from "@/lib/api";

export const revalidate = 300;

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ region?: string }>;
}) {
  const { region } = await searchParams;
  const { tournaments } = await fetchTournaments(region ? { region } : undefined);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">Tournaments</h1>
        <p className="mt-2 text-zinc-400">
          Live Fortnite competitive events, themed from Epic display data.
        </p>
      </div>
      <TournamentListClient tournaments={tournaments} initialRegion={region} />
      {tournaments.length === 0 ? (
        <p className="mt-8 text-zinc-500">
          No tournaments found. Ensure the API is running and catalog sync has completed.
        </p>
      ) : null}
    </main>
  );
}
