# Frontend / UI

## Look at (Phase 1)

- The component and design-system inventory first: what you need may already exist (the components folder, the design-system package, its stories).
- The stories of the components involved, the design tokens, and the linked design frame when a design-tool MCP is authorized.
- The existing tests (unit, interaction, visual) and the project's lint and type rules for UI code.

## Claims to verify

- "Component X does not exist", "nothing similar exists".
- "It matches the design system" or "the design".
- "It works on mobile", "it is responsive".
- "It is accessible".
- "The change is purely visual" (no behaviour or API change).

## Checks

- When a browser or preview tool exists, render it (Storybook or a browser preview) and screenshot each named state (default, hover and focus, disabled, error, empty, loading) in each theme the project ships. Otherwise, list the named states for the user to check in the browser.
- An axe or equivalent a11y scan when available; walk the keyboard path and check the visible focus.
- The narrowest supported width and each breakpoint the project uses.
- The project's lint and typecheck, and the tests around the component.

## Done when

The named states and themes are checked (screenshots in the transcript when a browser or preview tool exists, else by the user in the browser) and lint, typecheck and tests are green.

## Pitfalls

- Rebuilding a component that already exists, or adding a near-duplicate variant.
- Raw values (hex colours, pixel sizes) instead of the design tokens.
- Shipping a pixel change without a human looking at it: the agent's screenshot review does not replace the user's eye.
- Checking one theme or one width and generalising.
