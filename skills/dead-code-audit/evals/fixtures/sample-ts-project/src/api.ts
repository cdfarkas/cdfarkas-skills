import type { ActivePayload } from "./types.js";

export async function fetchData(): Promise<ActivePayload> {
  return { id: "1", active: true };
}

// Exported but never imported anywhere: a planted unused export.
export function buildLegacyUrl(path: string): string {
  return `https://legacy.example.com/${path}`;
}
