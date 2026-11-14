# OpenProxyAI website

The marketing site (home, product, security, providers, pricing). React, TypeScript, Vite and Tailwind, deployed on Vercel. It is separate from the admin console in `../admin-console`.

```bash
npm ci
npm run dev      # local dev server
npm run lint
npm run build    # type-check and production build
```

Pages are in `src/pages`, composed from `src/sections`.

## Search and sharing requirements (keep these through any redesign)

Each page is pre-rendered to static HTML at build time (`scripts/prerender.mjs`), then hydrated in the browser. The build writes `sitemap.xml` and per-page tags. When you change the UI:

- **No browser APIs while rendering.** `window`, `document`, `matchMedia`, `Date.now()` and `Math.random()` may only be used inside `useEffect` or event handlers. Otherwise the server render fails or hydration warns. Render a stable first state, then update after mount.
- **One `<h1>` per page**, with real text (not an image). Keep headings in order.
- **Add every new route in two places:** the `Routes` in `src/App.tsx` and the `pages` list in `scripts/prerender.mjs` (title, description). The list also feeds the sitemap.
- **Titles and descriptions** are set per page in `scripts/prerender.mjs`. Keep titles under about 60 characters and descriptions under about 160. If you change the `document.title` calls in the page components, keep them equal to the prerender titles.
- **Do not hide copy behind tabs or click-to-load.** Content that exists only after a click is not indexed.
- **Keep `public/robots.txt`, `public/llms.txt` and `public/og-image.png`.** Keep the 1200x630 share image up to date with the brand.
- **Links between pages must be real anchors** (`<Link>` or `<a href>`), not click handlers.
- After a redesign, run `npm run build`, open `dist/index.html` and confirm the page text is in the file, then check the site with a rich-results test and a share-preview check.
