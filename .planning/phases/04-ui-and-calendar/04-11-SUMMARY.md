---
phase: 04-ui-and-calendar
plan: 11
subsystem: infra/google-oauth
tags: [google-calendar, oauth, gap-closure, deferred]
status: deferred
deferred_to: phase-05-or-later
deferred_reason: Google requires app verification for sensitive scopes before publishing; Railway backend not yet deployed
---

# Plan 04-11 Summary: CAL-03 Google OAuth Consent Screen — Deferred

## What Was Intended

Confirm the Google Cloud OAuth consent screen for PacerAI is published as "In production" (not "Testing"), satisfying CAL-03. No code changes were needed — the implementation in calendar.py is complete and correct.

## Blocker

Two external blockers prevent publication:

**1. Google App Verification Required**
`calendar.events` is classified as a sensitive scope. Google requires the app to complete verification (logo, privacy policy, Terms of Service, formal Google review) before it can be published as "In production". The console shows:
> "Your app's data access is not verified. Verification is required because your app requests sensitive or restricted scopes."

The plan incorrectly assumed `calendar.events` could be published without verification. It cannot.

**2. Railway Backend Not Deployed**
The FastAPI backend (calendar.py OAuth callback) has not been deployed to Railway yet. Without a live backend, real users cannot complete the OAuth flow regardless of console publication status.

## What IS Complete

- `api/routes/calendar.py`: Full OAuth2 redirect and callback flow implemented
- `api/calendar_sync.py`: Push/update/delete to Google Calendar
- Fernet-encrypted token storage in DB
- `SettingsScreen.tsx`: Connect/Disconnect Google Calendar UI
- CAL-01, CAL-02, CAL-04: Implemented and E2E tested (mocked)

## What's Deferred to Phase 5+

| Item | Requirement |
|------|-------------|
| Railway deployment (FastAPI + DB) | Live backend for OAuth callback URL |
| App logo (512x512 + displayed) | Required before Google verification |
| Privacy policy URL | Required for verification |
| Terms of Service URL | Required for verification |
| Google verification submission | Up to 4-6 weeks; submit after above |
| Production OAuth flow E2E test | Blocked until Railway is live |

## Self-Check

- [x] Blocker documented and understood
- [x] In-scope implementation (calendar.py, SettingsScreen) is complete
- [x] Out-of-scope items (Railway deploy, app verification) identified for Phase 5
- [ ] CAL-03 DEFERRED — cannot verify production OAuth without deployed backend + Google review

## Decisions

- Treating Phase 4 as functionally complete: all 34 E2E tests pass, UI is built, calendar integration is implemented and tested with mocks
- CAL-03 production verification deferred to Phase 5 (infrastructure/deployment phase)
- Railway setup should be the first task of Phase 5
