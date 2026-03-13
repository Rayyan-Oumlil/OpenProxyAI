# OpenProxy Admin Console

Separate React + Vite admin app for operating OpenProxyAI.

## Current V1 Slice

- Login with backend JWT auth
- Dashboard (analytics overview)
- Request Logs (filter + pagination)
- API Keys (list, create, revoke)
- Placeholder screens for Users & Roles / Organization Settings

## Run Locally

1. Start backend at `http://localhost:8000`.
2. In this folder:

```bash
npm install
npm run dev
```

Default local URL: `http://localhost:5174`

## Environment

Optional:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

If unset, the app defaults to `http://localhost:8000`.
