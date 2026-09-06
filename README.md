# Twitch Breakout Categories

**PM portfolio project.** Which game categories will see above-median viewer growth next week — and what should Twitch's content/discovery team do about it?

The deliverable is not the pipeline; it's a 1-page memo with one defensible insight. The pipeline exists to make that memo credible.

## Setup (30 min)

1. Register an app at https://dev.twitch.tv/console → copy **Client ID** and **Client Secret**
2. `cp .env.example .env` and fill in the credentials
3. `pip install -r requirements.txt`
4. Test locally: `python collector.py --games 5`

## Data collection (Week 1)

- Polls `Get Top Games` + `Get Streams` every 10 min, appends to `data/twitch.db`
- GitHub Actions: add repo secrets `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET`, then push. The workflow runs every 10 min and commits the DB back to `main` with `[skip ci]`.
- Health check target: ≥98% of polls landed (see notebook §1)

## Analysis (Weeks 2–4)

`notebooks/01_explore.ipynb` — health check → baseline → four metrics (growth slope, streamer-to-viewer ratio, new-streamer inflow, language mix) → one insight, pressure-tested against rival explanations (season, events, one-big-streamer skew).

## Memo (Week 5)

One page, PRD style: context → insight (+1 chart) → recommendation → how to measure → risks. That artifact is the portfolio piece.

## Notes / caveats baked into the design

- Streamer counts are "live at poll time," an undercount of daily unique creators — documented in the notebook, not hidden.
- All data is public Helix endpoints; no user OAuth, no chat scraping, ToS-clean.
- Top-30 games × ~300 streams each per poll ≈ well under Helix rate limits.
