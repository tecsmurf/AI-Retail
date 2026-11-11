# Security questionnaire answers (DRAFT)

> Answers for a retail chain's IT or procurement team, based on the code in
> this repository as of the date of the last change to this file. Where
> something is not done yet, it says so; do not soften these answers when
> sending them to a customer.

## Product

**Does the system use face recognition or identify people?**
No. It detects people as boxes (YOLO11n person class) and tracks them within
one camera view using anonymous numbers. There is no face detection,
face template, re-identification across cameras, or age/gender estimation.

**Does video leave the store?**
With the in-store box: no. Video is read from the NVR/cameras on the store's
network and analysed in memory. Only events and, when an admin asks, a single
still image are sent. With uploaded recordings: yes, the uploaded files are
stored in the cloud until `VIDEO_RETENTION_DAYS` (default 30) and then deleted.

**What does the in-store box need from our network?**
Read access to the camera streams (RTSP) on the local network, and outbound
HTTPS to the Footrail API. No inbound ports. See docs/EDGE.md.

**Where are camera passwords kept?**
Only on the box, in its settings file. They are removed from the box's logs
and never sent to the server.

**What happens if the internet drops?**
The box keeps analysing and queues events on its disk, then sends them with
their original times when the connection returns (tested by stopping the
API for under a minute, see docs/EDGE.md; longer outages are not tested yet).
The queue holds up to 2 million events; after that the oldest are dropped and
the dashboard says how many.

## Access control

**How do users sign in?** Email and password. Passwords are stored as salted
scrypt hashes. Sessions are signed tokens in httpOnly cookies, with a CSRF
header check on changes.

**Is there single sign-on (SAML/OIDC) or two-factor authentication?**
Not yet.

**Can we restrict a store manager to their own store?** Yes. Roles are HQ
admin, HQ viewer, regional manager (their regions) and store manager (their
stores). Requests for other stores are refused as if the store did not exist.

**Is there an audit trail?** Yes, for sign-ins, user and role changes, setup
changes, uploads, report downloads and in-store box pairing, viewable by HQ
admins on the System page.

**Can access be revoked quickly?** Deactivating a user ends all of their
sessions immediately. Removing an in-store box revokes its token; the box stops
sending at its next contact.

## Data protection

**Is data encrypted?** In transit, yes (HTTPS). At rest, by the hosting
providers' storage encryption; Footrail does not add its own encryption layer.

**Where is data hosted?** Not decided yet. No production environment exists.
Planned providers are in DPA_TEMPLATE.md Annex C, with regions to be agreed.

**How long is data kept?** See DATA_MAP.md. Recordings 30 days by default,
audit-log IP addresses 90 days, anonymous counts for the contract.

**Can you delete our data at the end of the contract?** Yes, by a manual,
documented deletion. A tested one-step organisation deletion is not built yet.

**Backups?** Not set up yet. They will come from the database provider's
point-in-time recovery once hosting is chosen; restore testing is still to do.

## Assurance

**Certifications (ISO 27001, SOC 2)?** None.

**Penetration test?** None yet. Automated tests cover access control between
organisations, roles and stores (`backend/tests/test_org_access.py`), and the
in-store box authentication (`backend/tests/test_edge.py`).

**Vulnerability management?** Dependencies are pinned; there is no automated
dependency scanning yet.

**Incident response?** The draft DPA commits to telling the customer within
[24] hours of becoming aware of a breach. A written incident runbook is still
to do.

**How accurate are the counts?** Measured so far only on public test clips
and a simulated live stream, not on a customer's cameras; see
docs/CV_VALIDATION.md and docs/BUILD_LOG.md. Accuracy must be checked on each
store's cameras during setup (the setup checklist ends with this step).
