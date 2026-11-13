# OpenProxyAI website

The marketing site (home, product, security, providers, pricing). React, TypeScript, Vite and Tailwind, deployed on Vercel. It is separate from the admin console in `../admin-console`.

```bash
npm ci
npm run dev      # local dev server
npm run lint
npm run build    # type-check and production build
```

Pages are in `src/pages`, composed from `src/sections`.
