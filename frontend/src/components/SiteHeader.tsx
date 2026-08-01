"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { searchPlayers } from "@/lib/api";

export function SiteHeader() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await searchPlayers(query.trim());
      if (result.players.length === 0) {
        setError("No players found");
        return;
      }
      router.push(`/players/${result.players[0].accountId}`);
    } catch {
      setError("Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <header className="border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-white">
          Circuit
        </Link>
        <form onSubmit={onSearch} className="flex items-center gap-2">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search player..."
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder:text-zinc-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {loading ? "..." : "Search"}
          </button>
        </form>
      </div>
      {error ? <p className="px-4 pb-3 text-sm text-red-400">{error}</p> : null}
    </header>
  );
}
