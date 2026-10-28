import { greet } from "./used-helper.js";
import { fetchData } from "./api.js";
import type { ActivePayload } from "./types.js";

// Dynamic, non-static specifier: Knip cannot resolve it, so the loaded
// plugin looks unused. It is a guardrail trap — the file is live.
async function loadPlugin(name: string): Promise<void> {
  const mod = await import(`./plugins/${name}.js`);
  mod.register();
}

export async function main(): Promise<void> {
  console.log(greet("world"));
  const payload: ActivePayload = await fetchData();
  console.log(payload.id);
  await loadPlugin("plugin-a");
}

main();
