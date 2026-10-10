# Using and changing PurpleSol from a phone

The goal: run the store analytics, upload footage, and make code changes with
your laptop switched off. Two pieces make that possible.

1. **The hosted app** (Vercel + Railway + Neon + R2, see `DEPLOYMENT.md`) runs
   all the time. Your phone is only a browser.
2. **GitHub Codespaces** gives you the full development environment in the cloud
   when you need to change code.

Status: the hosted app is **not deployed yet** (it needs your cloud accounts).
The Codespaces configuration is in the repo but has not been tested in a real
Codespace yet.

## Day to day, from the phone

Open `https://<your-app>.vercel.app` and sign in. On a phone the dashboard has a
bottom bar (Overview, Analytics, Insights, Videos) and a menu for the rest.

| I want to… | Where |
|---|---|
| See today's footfall, queues, revenue | **Overview**. Pick the store and date range at the top. "Jump to latest data" moves the range to where data exists. |
| Upload CCTV footage | **Videos** > choose camera, recording start time, file. The upload goes straight to storage, so you can lock the phone once the progress bar finishes. Processing happens on the worker. |
| Check a processing job | **Videos**: status, progress, the realtime factor, snapshots. Cancel, retry or reprocess from there. |
| See whether the worker is alive | **System** (in the menu): worker online, model loaded, queue length, last heartbeat. |
| Draw zones for a camera | **Cameras & zones** > camera > zone editor. Works with touch; a tablet is easier than a phone. |
| Import POS sales | **Cameras & zones** > store > Import POS CSV. |
| Add a team member | Ask Claude, or use `python -m app.cli create-user` from a Codespace pointed at the production database. |

Tip: on iOS Safari or Android Chrome use "Add to Home Screen" to open it like an
app.

## Changing code without the laptop

### Option A: ask Claude in this project

Describe the change in the project chat. Claude works on a branch, opens a pull
request, and CI checks it. You review and merge from the GitHub mobile app.
Vercel and Railway redeploy from `main` automatically once connected.

### Option B: GitHub Codespaces in the phone browser

1. On github.com (desktop site) open the repo, **Code > Codespaces > Create
   codespace on your branch**. A 4-core machine is enough.
2. The first start runs `.devcontainer/setup.sh` (10 to 15 minutes): Python 3.11,
   Node 22, ffmpeg, CPU PyTorch, a local Postgres with migrations and the default
   stores.
3. In the terminal: `make dev`. This starts the API on 8000, the worker, and the
   dashboard on 3000. Codespaces forwards port 3000; open it and sign in as
   `admin@purplesol.local` / `change-this-password` (development only).
4. `make test` runs the backend tests and frontend checks; `make lint` runs the
   linters.
5. Commit and push from the Source Control panel, then open a pull request.

Codespaces stop after 30 idle minutes and keep your files. Stop them yourself when
done to save free hours.

A phone screen is cramped for coding. It is fine for small fixes and for running
commands; for anything larger, Option A is easier.

## Keeping it safe

* Never put production secrets in the Codespace or the repo. Use Railway and
  Vercel variables. The Codespace uses its own local database.
* Use a strong admin password and remove `ADMIN_PASSWORD` from Railway after the
  first login.
* "Sign out on all devices" (bottom of the menu) ends all sessions if a phone is lost.
* CCTV footage must never be committed to Git. Upload it through the app; it is
  stored in your private bucket and deleted after `VIDEO_RETENTION_DAYS`.
