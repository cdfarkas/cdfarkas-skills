# Review rules for @sample/ui

## Floor
- WCAG 2.1 AA: a failure is Blocking. WCAG 2.2 additions are at most Should fix.
- Target size: 24x24 CSS px (SC 2.5.8), or its spacing exception.
- Browsers: the last two versions of Chrome, Edge, Firefox and Safari.

## Always check
- UI-1: every component is exported from `src/index.ts` (source: the `exports` map in package.json).

## What Blocking means here
- A state the user cannot perceive in a supported mode, forced colors included.

## Do not report
- U4: the library ships a single theme.
- CSS formatting: stylelint-config-standard covers it.

## Gates
- `npm run lint`, `npm run typecheck`, `npm test`
