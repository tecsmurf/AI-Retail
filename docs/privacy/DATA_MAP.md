# Data map (DRAFT)

> Draft for review by a lawyer and the customer's privacy team. It describes
> what the code in this repository does; check it again whenever the code
> changes.

Every kind of data Footrail handles, where it lives, who can see it and when
it is deleted. "Org" means one retail chain; no user can see another org's
data (`backend/app/access.py`, tested in `backend/tests/test_org_access.py`).

Who can see what inside an org:

| Role | Stores | Can change setup |
|---|---|---|
| HQ admin | All | Yes |
| HQ viewer | All | No |
| Regional manager | Stores in their regions | Uploads only |
| Store manager | Their stores | Uploads only |

## 1. Video and images (can show identifiable people)

| Data | Where | Who can see it | Deleted when |
|---|---|---|---|
| Live camera video, in-store box | Read from the NVR/camera into the box's memory, analysed frame by frame. | Nobody through Footrail. Never written to disk or uploaded. | Immediately (never stored). |
| Uploaded recordings | Object storage (`videos/...`). | Users who can see the store (download is not offered in the app). | `VIDEO_RETENTION_DAYS` after upload (default 30), by the worker's hourly clean-up. |
| Worker scratch copy of a recording | Worker's temp folder while a job runs. | Nobody. | When the job finishes or fails. |
| Annotated frames (a few per processed video, with boxes drawn on people) | Object storage (`artifacts/<job>/snapshot_*.jpg`). | Users who can see the store, on the Videos page. | With the recording, after `VIDEO_RETENTION_DAYS`. |
| Still image per camera (backdrop for drawing zones) | Object storage (`frames/<camera>/...`). Comes from a processed video, an admin upload, or "Get still image" on the box. | Users who can see the store. | When replaced by a newer still, or when an admin presses "Remove still image". Otherwise kept while the camera exists. **Tip:** take the still when the store is empty. |

## 2. Anonymous movement data

None of this contains images, faces, names, or anything linked to a person
outside the store.

| Data | Contents | Where | Deleted when |
|---|---|---|---|
| Events | Time, camera, event type (entry, exit, zone enter/exit, queue), zone, anonymous track number, dwell/wait seconds, detector confidence, person-box coordinates as fractions of the frame. | Database (`events`). On the box, a local queue holds unsent events. | Database: kept for the contract (see "End of contract"). Box queue: as soon as the server confirms receipt. |
| Journeys | Ordered list of zones one anonymous track visited on one camera. | Database. | As events. |
| Queue length samples | Number of people in a queue zone every few seconds. | Database. | As events. |
| Tracks file per processed video | Per frame: anonymous track number, box coordinates, confidence. Used to check detection quality. | Object storage (`artifacts/<job>/tracks.jsonl.gz`). | Kept for the contract (it holds no images). |
| Coverage | Seconds of live video analysed per camera per hour. | Database. | Kept for the contract. |

## 3. Business data from the customer

| Data | Contents | Where | Deleted when |
|---|---|---|---|
| POS transactions | Order id, store code, date and time, product id, brand, amount. **No customer name, phone or card.** | Database. | Kept for the contract. The customer can ask for deletion of any import. |
| Stores, cameras, zones, regions | Names, codes, city, time zone, drawn zone shapes. Camera stream addresses are **not** stored on the server; they stay in the box's own settings file. | Database; box settings file. | When deleted by an admin / at end of contract. |

## 4. People who use the app

| Data | Contents | Where | Deleted when |
|---|---|---|---|
| User accounts | Email, full name (optional), role, store/region access, password hash (scrypt). | Database. | Deactivated by an admin; deleted at end of contract. |
| Sign-in session | Signed token in an httpOnly cookie, valid for `SESSION_TTL_HOURS` (default 7 days). | User's browser. | Sign-out removes it from that browser. "Sign out everywhere", a password change or deactivation makes every copy invalid. Otherwise it expires. |
| Audit log | Who did what (email, action, target, time) and the IP address of the request. Covers sign-in, user and role changes, setup changes, uploads, report downloads, box pairing. | Database. | IP addresses are blanked after `AUDIT_IP_RETENTION_DAYS` (default 90). Entries are kept for the contract. |
| Request logs | Route, status, timing, user id. No IP address, no request bodies. | Hosting provider's log store. | Per the hosting provider's log retention. |
| Dashboard filters | Selected store and dates. | The user's browser (localStorage). | When the user clears site data. |

## 5. The in-store box

| Data | Contents | Where | Deleted when |
|---|---|---|---|
| Box record | Name, store, hostname, software version, last seen time, last IP address, per-camera health. | Database. | When the box is removed and the store is deleted. |
| Box access token | Random token; only its SHA-256 hash is on the server. | Box (file readable only by its user); hash in the database. | Revoked when an admin presses "Remove". |
| Camera stream addresses (with camera passwords) | `rtsp://user:pass@...` | Only on the box, in its settings file. Passwords are removed from the box's logs. | When the box is wiped. |

## Settings that control retention

| Setting | Default | Effect |
|---|---|---|
| `VIDEO_RETENTION_DAYS` | 30 | Uploaded recordings and their annotated frames are deleted after this many days. 0 keeps them. |
| `AUDIT_IP_RETENTION_DAYS` | 90 | IP addresses in the audit log are blanked after this many days. 0 keeps them. |
| `SESSION_TTL_HOURS` | 168 | How long a sign-in lasts. |

Current values are shown to admins on the System page.

## End of contract

There is no one-click "delete this org" yet. At the end of a contract the
operator exports what the customer wants (CSV reports) and deletes the org's
data from the database and object storage by hand, and confirms in writing.
Building a tested org-deletion command is on the roadmap.

## Where it is hosted

Not decided yet: no production environment exists. The planned providers are
listed in DPA_TEMPLATE.md Annex C. Their regions must be chosen with the first
customer (see the open question on hosting location in README.md).
