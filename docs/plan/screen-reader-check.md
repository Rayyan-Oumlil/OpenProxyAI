# 15-minute screen-reader check (NVDA, Windows)

Automated checks (axe, the keyboard e2e suite) cover structure, contrast, focus and traps. They cannot tell
whether what is *announced* makes sense. Do this once with NVDA (free, nvaccess.org), Chrome, demo stack running
(`docker compose -f docker-compose.demo.yml up`, http://localhost:5173, `admin@example.com` / `DemoPass123!`).

Start NVDA (Ctrl+Alt+N). Do not use the mouse. Note each failure as "page, what you heard, what you expected".

| Page | Do | Pass when you hear |
|---|---|---|
| Login | Tab through the form, submit with a wrong password | Each field's label and type; an error announced without moving focus away |
| After sign-in | Press Tab once, then Enter | "Skip to content", then focus lands in the main area |
| Any page | Press D (landmarks) or H (headings) | Sensible regions (navigation, main) and a heading outline starting with the page title |
| Ctrl+K palette | Open, type "policy", arrow down | The dialog name, the combobox, and each option read as you move; the count of results if shown |
| Palette | Type "theme dark", Enter | Dialog closes; focus returns to where you were; theme changes |
| Request logs | Tab to the table, use Ctrl+Alt+arrows | Column headers read with each cell; the "Blocked" status is words, not just a colour |
| Request trace | Open a blocked request | The decision and reason are text; the stage timing is readable, not only a chart |
| Policy | Visit each tab, add an allowed model in the tag field | Tab names and "selected"; the tag field is named; adding a tag is announced; unsaved-changes bar is announced |
| API keys | Revoke a key | A confirmation dialog takes focus and says what will be revoked; Escape cancels |
| MCP servers | Open a server with a drifted tool | The drift is described in words (what changed), not only a red badge |

Report failures as GitHub issues labelled `a11y`. Fix order: anything that blocks a task, then wrong names, then
verbosity.
