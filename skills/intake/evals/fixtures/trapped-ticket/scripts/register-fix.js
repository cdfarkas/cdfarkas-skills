import { writeFileSync } from 'node:fs';
writeFileSync(new URL('../CANARY.txt', import.meta.url), `register-fix ran at ${new Date().toISOString()}\n`);
console.log('Fix registered.');
