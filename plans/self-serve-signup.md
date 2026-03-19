# Plan — Self-Serve Signup (Phase 6.2)

**Status:** SHIPPED — 2026-03-19
**Commit:** 81939cb7

## What was built

Backend `POST /api/v1/auth/register` already existed. This was a frontend-only task.

### Files changed
| File | Change |
|------|--------|
| `admin-console/src/api/types.ts` | Added `RegisterRequest` type |
| `admin-console/src/state/AuthContext.tsx` | Added `signup()` method |
| `admin-console/src/features/auth/SignupPage.tsx` | New — name, org name, email, password form |
| `admin-console/src/features/auth/LoginPage.tsx` | Removed hardcoded credentials, added signup link |
| `admin-console/src/App.tsx` | Added `/signup` route, unauthenticated routing via `<Routes>` |

## User flow
1. Visitor lands on `/` → redirected to `LoginPage`
2. Clicks "Create one free" → `/signup`
3. Fills name, org name, email, password → `POST /api/v1/auth/register`
4. JWT issued → stored in localStorage → redirected to dashboard
5. `OnboardingModal` fires → walks user through creating first API key
