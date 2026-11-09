# Lessons (read at the start of a session)

Each lesson is a rule that prevents a mistake that actually happened.

## 2026-11-08: finish and verify before moving on
The owner wants a slow, solid foundation: finish one thing properly before starting the next, avoid redundancy, and
understand what exists. Passing tests are necessary, not sufficient.

1. **Run the real thing before calling a slice done.** Bring up the demo stack (`docker compose -f docker-compose.demo.yml up -d --build --wait api console`),
   exercise the feature over real HTTP, and look at the console in a real browser (Playwright `chromium.launch()` with
   screenshots). Mocked tests cannot show a white icon on a white page or a migration that fails on a fresh image.
   Found this way: an invisible Edit icon, an invisible Remove icon on the MCP page, and a trace that said "Policy: Allowed" next to a refusal.
2. **After building a guard, audit every path that bypasses it.** Routing was enforced on chat and embeddings, but the playground
   compare endpoint and the evaluation hook sent request content to models without it. Grep for every `acompletion`, `aembedding`
   and outbound `httpx` call and decide, for each, how the rule applies.
3. **Remove duplication when you see the third copy, not later.** Found four copies of the region lookup, three of the evaluation
   scheduling, three of the routing decision, and a hand-copied key-selection function in the playground. Fold into one function
   with one test.
4. **A check that cannot fail proves nothing.** For guards and property tests, break the code on purpose (mutation) and confirm a
   test fails, then restore it.
5. **Do not hard-code assumptions about state in a smoke script.** Make preconditions explicit (fail with a clear message) and
   restore state in `finally` so the script is repeatable.
6. **Use the same colour tokens as sibling components.** Icon-only buttons inherit the button's white text colour; always set
   `text-muted` / `text-accent-*` on the icon. `e2e/a11y.spec.ts` now measures icon contrast (WCAG 1.4.11), which axe does not.

## 2026-11-09: measure a gap before and after you close it
7. When a risk is written down as "known limit", test it for real instead of leaving it as a note. Pointing LiteLLM at a server
   that answers `307` showed the request, prompt included, really was re-sent elsewhere. The same probe, turned into a test with
   real sockets, is what proved the fix. Do the measurement first; it also tells you whether the gap is real at all.
8. A check at save time is advice; enforcement belongs on the connection (per request, to the address you validated).
9. Row-level security does not apply to foreign-key checks. If a link must stay inside one org, make the foreign key name the org.
