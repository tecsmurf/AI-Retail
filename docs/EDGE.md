# In-store box (live cameras)

The box is a small program that runs on a PC inside the store. It reads the
store's camera streams over the local network, runs the same people tracking as
the video worker, and sends only anonymous events to the cloud.

Status: **tested on synthetic and looped test streams only.** It has not yet
been run against a real recorder (NVR) or a real IP camera. See
[What was tested](#what-was-tested) before promising anything to a store.

## What leaves the store and what stays

| Stays on the box | Sent to the cloud |
| --- | --- |
| Video frames (analysed in memory, never written to disk) | Events: entry, exit, zone enter/exit, queue enter/exit, with a time and an anonymous track label |
| Camera stream addresses, recorder user names and passwords (`edge.json`) | Queue length samples every 5 seconds |
| The box's token (`state/token`, readable only by its user) | Camera health: live or not, frame rate, picture size, seconds analysed |
| Unsent events while the internet is down (`state/outbox.db`) | One still image of a camera, only when an administrator asks for it |

The still image is the only picture that leaves the store. It is sent only
when an administrator presses "Get still image" for that camera, so zones can
be drawn on a real view. The server refuses a picture nobody asked for. A
still can show people who happened to be in view at that moment, so take it
when the store is quiet; "Remove still image" in the zone editor deletes it.

Track labels look like `CAM1-Lab12cd-T7`. They restart with every connection
to the camera and cannot be linked to a person, a face or a phone.

The box only makes outgoing connections: to the recorder on the local network
and to the API over HTTPS. Nothing has to be opened on the store's router.

## Set up a store

1. In the dashboard open **Cameras & zones**, pick the store and add its
   cameras (code, name, type). The codes are what you use on the box.
2. In the **Live cameras** card press **Add a box** and name it. A pairing
   code appears. It works once and runs out after 30 minutes.
3. On the store PC (Docker installed), get the repository and go to `edge/`:

   ```bash
   cp edge.example.json edge.json
   ```

   Fill in `api_url` (the address of the API) and one stream address per
   camera code:

   ```json
   {
     "api_url": "https://YOUR-API-ADDRESS",
     "state_dir": "./state",
     "cameras": {
       "ENT": "rtsp://USER:PASSWORD@192.168.1.64:554/Streaming/Channels/102",
       "BILL": "rtsp://USER:PASSWORD@192.168.1.64:554/Streaming/Channels/202"
     }
   }
   ```

4. Pair and check each camera, then start:

   ```bash
   docker compose run --rm edge pair ABCDE-FGHJK
   docker compose run --rm edge cameras
   docker compose run --rm edge check-camera ENT
   docker compose up -d
   ```

   `check-camera` opens the stream for a few seconds and prints the picture
   size and frame rate, or a plain reason why it could not connect.
5. Back in the dashboard the box shows **Online** and each camera **Live**
   within about a minute. Press **Get still image** for each camera (it
   arrives within about a minute) and draw the entry line and zones on it. The box picks up zone changes at its next check-in
   (every 30 seconds) without a restart.

Without Docker: Python 3.11, `pip install -r edge/requirements.txt` plus
PyTorch, then from `backend/` run
`PYTHONPATH=.:../edge python -m purplesol_edge --config ../edge/edge.json run`.

### Stream addresses

Use the recorder's **sub-stream** (lower resolution). Analysis runs at 5
frames per second and does not need the full-resolution stream.

These are the patterns the manufacturers document. **None has been tried by
us against real equipment yet**; `check-camera` tells you at once whether an
address works.

| Brand | Usual pattern (channel 1, sub-stream) |
| --- | --- |
| Hikvision | `rtsp://USER:PASS@IP:554/Streaming/Channels/102` (channel 2 is `202`) |
| Dahua, CP Plus | `rtsp://USER:PASS@IP:554/cam/realmonitor?channel=1&subtype=1` |
| Other | Look for "RTSP" in the recorder's network settings or manual |

Special characters in a password must be URL-encoded (`@` becomes `%40`).
RTSP must be enabled on the recorder. Passwords are never printed: logs and
the `cameras` command show `rtsp://USER:***@...`.

## What the dashboard shows

* **Box**: Online when it checked in within the last 90 seconds, with the time
  of the last check-in, the number of events received and how many are still
  waiting on the box.
* **Camera**: Live, Connecting, Offline (with the reason the box gave), or
  "No stream address" when the camera exists in the dashboard but not in
  `edge.json`. A camera is never shown as live when its box is offline.
* **Footage behind these numbers** on the overview adds live time per camera.
  A day with two hours of live time is two hours of observation, not a quiet
  day.

Live events are labelled with their own source (`edge`, shown as "Live
cameras") and count as real data together with processed recordings.

## When things go wrong

| Situation | What happens |
| --- | --- |
| Internet down | Cameras keep being analysed. Events wait in `state/outbox.db` (up to 2 million rows, oldest dropped first and reported) and are sent in order when the connection returns. Events are idempotent, so nothing is counted twice. |
| Camera or recorder down | The camera shows Offline with the reason. The box retries after 2 s, then up to every 60 s. |
| Stream freezes | No new frame for 15 seconds counts as a dead stream and the box reconnects. |
| PC restarts | `docker compose up -d` uses `restart: unless-stopped`, so the box starts with Docker. Unsent events survive the restart. |
| Box replaced or stolen | **Replace box** in the dashboard creates a new code and stops accepting the old box at once. **Remove** stops it for good; data it already sent is kept. A removed box exits with code 3. |

Known limits:

* People who are in view when a connection drops lose their track; they start
  as new tracks after the reconnect. Open zone visits at that moment are not
  completed.
* Live time is booked to the hour in which the box reports it. After a long
  internet outage the hours of the outage are under-reported (at most one
  hour is booked per check-in), although the events themselves arrive.
* Clock: event times come from the box's clock. Keep the PC's time
  synchronised. Events more than 10 minutes in the future are refused.
* One box analyses its cameras on the CPU. On our 4-core 2.1 GHz test machine
  one 1280×720 stream at 5 frames per second used about 60% of one core and
  about 0.9 GB of memory. That is one measurement, not a sizing guarantee;
  measure on the real PC before adding many cameras.
* Entries are counted on the entry line only. Staff are not told apart from
  shoppers.

## What was tested

Automated (run in CI): pairing codes (single use, expiry, rate limit), token
checks, configuration without stream addresses, health and live-time
reporting, idempotent events feeding analytics and journeys, batch limits,
still images, revoke and re-pair, isolation between organisations and roles,
the send queue across restarts, password redaction, and the camera worker on a
synthetic video with a scripted detector.

By hand on 2026-11-11, on one machine: a box was added in the dashboard,
paired with the code, and run with the real detector against a looped test
clip served as a live HTTP stream. The dashboard showed the box online, the
camera live, the still image in the zone editor, and exit and zone events on
the overview. Stopping the stream made the box reconnect; stopping the API
made it queue events and deliver them afterwards. The clip was a still photo
moved across the frame, so the counts say the plumbing works, not how accurate
counting is in a store.

Not tested: RTSP against a real recorder or camera of any brand, the Docker
image on a store PC, more than one camera at a time on real hardware, days of
continuous running, and poor store internet.
