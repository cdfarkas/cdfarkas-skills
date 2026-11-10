# Sources

Primary sources only. Each was fetched and read on the date shown; the version or edition is
the one the page states. A page that states none says so. Findings cite the success criterion
number and link the Understanding page; nothing here transcribes normative text.

| Source | URL | Version / edition as stated | Checked |
|---|---|---|---|
| WCAG 2.2 | <https://www.w3.org/TR/WCAG22/> | W3C Recommendation 12 December 2024 | 2026-11-10 |
| WCAG 2.2 success criteria data (number, slug, level, the source of `scripts/wcag22.json`) | <https://www.w3.org/WAI/WCAG22/wcag.json> | 86 success criteria with `2.2` in `versions` | 2026-11-10 |
| Understanding 1.4.3 Contrast (Minimum) | <https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html> | Updated 04 October 2026 | 2026-11-10 |
| Understanding 1.4.10 Reflow | <https://www.w3.org/WAI/WCAG22/Understanding/reflow.html> | Updated 04 October 2026 | 2026-11-10 |
| Understanding 1.4.12 Text Spacing | <https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html> | Updated 01 October 2025 | 2026-11-10 |
| Understanding 2.1.1 Keyboard | <https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html> | Updated 04 October 2026 | 2026-11-10 |
| Understanding 2.1.2 No Keyboard Trap | <https://www.w3.org/WAI/WCAG22/Understanding/no-keyboard-trap.html> | Updated 18 May 2026 | 2026-11-10 |
| Understanding 2.3.3 Animation from Interactions (AAA) | <https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html> | Updated 16 September 2025 | 2026-11-10 |
| Understanding 2.4.3 Focus Order | <https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html> | Updated 04 October 2026 | 2026-11-10 |
| Understanding 2.4.7 Focus Visible | <https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html> | Updated 04 October 2026 | 2026-11-10 |
| Understanding 2.4.11 Focus Not Obscured (Minimum) | <https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html> | Updated 15 June 2026 | 2026-11-10 |
| Understanding 2.5.8 Target Size (Minimum) | <https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html> | Updated 02 November 2026 | 2026-11-10 |
| Understanding 4.1.2 Name, Role, Value | <https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html> | Updated 02 November 2026 | 2026-11-10 |
| WAI-ARIA 1.2 | <https://www.w3.org/TR/wai-aria-1.2/> | W3C Recommendation 06 June 2023 | 2026-11-10 |
| ARIA APG, Dialog (Modal) pattern | <https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/> | No version or date stated (living document) | 2026-11-10 |
| ARIA APG, Menu Button pattern | <https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/> | No version or date stated (living document) | 2026-11-10 |
| ARIA APG, Menu and Menubar pattern (Escape behaviour of a menu) | <https://www.w3.org/WAI/ARIA/apg/patterns/menubar/> | No version or date stated (living document) | 2026-11-10 |
| axe-core rule descriptions | <https://github.com/dequelabs/axe-core/blob/v4.14.0/doc/rule-descriptions.md> | axe-core 4.14.0 (git tag `v4.14.0`); `target-size` is listed under "WCAG 2.2 Level A & AA Rules" | 2026-11-10 |
| Playwright, accessibility testing with `@axe-core/playwright` | <https://playwright.dev/docs/accessibility-testing> | No version stated (tracks the latest release) | 2026-11-10 |
| Playwright `Page` API (`emulateMedia` `reducedMotion`, `setViewportSize`, `waitForFunction`, `addStyleTag`) | <https://playwright.dev/docs/api/class-page> | No page version; `reducedMotion` marked "Added in: v1.12" | 2026-11-10 |
| Playwright `Keyboard` API (`press`) | <https://playwright.dev/docs/api/class-keyboard> | No version stated | 2026-11-10 |
| Playwright browsers (`install --only-shell`) | <https://playwright.dev/docs/browsers> | No version stated | 2026-11-10 |
| npm registry: `playwright`, `@axe-core/playwright`, `axe-core` latest | `npm view <pkg> version` | 1.65.0 (published 2026-11-05), 4.14.0 (2026-10-15), 4.14.0 (2026-10-05) | 2026-11-10 |

Nothing is UNVERIFIED: every page above answered and was read. The Playwright pages state no
version, so the APIs were also confirmed by running the script with Playwright 1.65.0.

The APG pages are guidance, not normative WCAG. The `overlay-escape` check cites them because
no success criterion requires Escape to close a click-opened dialog or menu.
