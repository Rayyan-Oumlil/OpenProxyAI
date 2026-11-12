# Accessibility

**Claim we make:** automated WCAG 2.1 A/AA checks pass. We do not claim "WCAG compliant": automated tools cannot judge whether what a screen reader announces makes sense.

## Automated checks (run in CI)
- axe on every console screen and dialog, in both themes.
- Icon contrast, focus return after dialogs and drawers, reflow (no horizontal page scroll at phone width), and keyboard-only flows, in the admin-console Playwright suites.

## Manual screen-reader check (NVDA, about 15 minutes)
Free screen reader for Windows: nvaccess.org. Use Chrome, with the demo stack running (`docker compose -f docker-compose.demo.yml up`, http://localhost:5173, `admin@example.com` / `DemoPass123!`).

Start NVDA with Ctrl+Alt+N. Do not use the mouse. For each failure, note the page, what you heard and what you expected.

| Page | Do | Pass when you hear |
|---|---|---|
| Login | Tab through the form, submit a wrong password | Each field's label and type; the error announced without focus moving away |
| After sign-in | Press Tab once, then Enter | "Skip to content", then focus lands in the main area |
| Any page | Press D (landmarks) or H (headings) | Navigation and main regions; a heading outline starting with the page title |
| Ctrl+K palette | Open, type "policy", arrow down | The dialog name, the combobox, each option as you move |
| Request logs | Tab to the table, Ctrl+Alt+arrows | Column headers with each cell; "Blocked" as words, not only a colour |
| Request trace | Open a blocked request | The decision and reason as text; stage timing readable, not only a chart |
| Policy | Visit each tab, add an allowed model | Tab names and "selected"; the tag field named; adding a tag announced |
| API keys | Revoke a key | A confirmation dialog takes focus and says what is revoked; Escape cancels |
| MCP servers | Open a server with a drifted tool | The drift described in words, not only a red badge |

Fix order: anything that blocks a task, then wrong names, then verbosity. Report failures as GitHub issues labelled `a11y`.

## Result log
| Date | Tester | Result |
|---|---|---|
| 2026-11-12 | n/a | Manual NVDA pass skipped by owner decision; not run. Only the automated checks above are claimed. |
