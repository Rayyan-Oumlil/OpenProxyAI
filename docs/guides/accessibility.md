# Accessibility

**Claim we make:** automated WCAG 2.1 A/AA checks pass. We do not claim "WCAG compliant".

## Automated checks (run in CI)
- axe on every console screen and dialog, in both themes.
- Icon contrast, focus return after dialogs and drawers, reflow (no horizontal page scroll at phone width), and keyboard-only flows, in the admin-console Playwright suites (`admin-console/e2e/`).
