// Loaded only through the dynamic import() in index.ts. Live at runtime,
// but Knip flags it unused because the specifier is not static.
export function register(): void {
  console.log("plugin-a registered");
}
