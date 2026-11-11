# Data Processing Agreement (DRAFT TEMPLATE)

> Template drafted by the engineering team as a starting point. **It is not
> legal advice and must be reviewed and completed by a lawyer before use.**
> Clause choices in [brackets] are placeholders. It is meant to sit alongside
> the commercial agreement (the "Main Agreement").

This Data Processing Agreement ("DPA") is made on [date] between:

1. **[Retail chain legal name]**, [registered office] (the "**Customer**",
   the Data Fiduciary); and
2. **[Footrail operator legal name]**, [registered office] ("**Footrail**",
   the Data Processor).

## 1. Definitions

Terms such as "personal data", "processing", "Data Fiduciary", "Data
Processor", "Data Principal", "personal data breach" and "Board" have the
meanings given in the Digital Personal Data Protection Act, 2023 (the
"**Act**") and the rules made under it (the "**Rules**").

"**Service**" means the Footrail store analytics service described in the
Main Agreement, including the in-store box software and the hosted dashboard.

"**Customer Data**" means the personal data described in Annex A that
Footrail processes for the Customer.

## 2. Roles and instructions

2.1 The Customer is the Data Fiduciary and decides the purpose and means of
processing. Footrail processes Customer Data only as a Data Processor on the
Customer's behalf, as required by section 8(2) of the Act.

2.2 Footrail will process Customer Data only to provide the Service and on
the Customer's documented instructions. The Main Agreement, this DPA and the
Customer's use of the Service's settings (for example retention settings)
are the Customer's instructions.

2.3 Footrail will tell the Customer if it believes an instruction breaks the
Act, and may suspend the affected processing until the Customer confirms or
changes it.

2.4 Footrail will not:
(a) use Customer Data for its own purposes, including training or improving
detection models, unless the Customer agrees in writing [for each dataset];
(b) attempt to identify any individual, use face recognition, or estimate
age, gender or other personal characteristics;
(c) sell or share Customer Data with anyone except as allowed in clause 5.

## 3. Customer responsibilities

3.1 The Customer is responsible for having a lawful basis under the Act for
the processing, for notices and signage to shoppers and staff, and for
handling requests from Data Principals.

3.2 The Customer will not send Footrail POS data that identifies shoppers
(names, phone numbers, loyalty ids, card details).

## 4. Confidentiality and security

4.1 Footrail will ensure that everyone it authorises to process Customer Data
is bound by confidentiality.

4.2 Footrail will maintain reasonable security safeguards appropriate to the
risk, at least those in Annex B, and will not materially reduce them during
the term.

## 5. Sub-processors

5.1 The Customer authorises the sub-processors listed in Annex C.

5.2 Footrail will give the Customer at least [30] days' written notice
before adding or replacing a sub-processor. The Customer may object on
reasonable data protection grounds within that period; the parties will
discuss in good faith, and if they cannot agree the Customer may terminate
the affected part of the Service [without penalty].

5.3 Footrail will impose data protection terms on each sub-processor that are
no less protective than this DPA, and remains responsible for their
performance.

## 6. Location and transfers

6.1 Customer Data will be stored and processed in [India / the locations in
Annex C].

6.2 Footrail will not transfer Customer Data to any country or territory
restricted by the Central Government under section 16 of the Act.

## 7. Assistance

7.1 Footrail will, taking into account the nature of the processing, help the
Customer respond to requests from Data Principals (for example by deleting a
still image or recording on request) and to inquiries from the Board.

7.2 Footrail will forward to the Customer, without undue delay, any request
it receives directly from a Data Principal about Customer Data, and will not
answer it except on the Customer's instructions.

## 8. Personal data breach

8.1 Footrail will notify the Customer without undue delay, and in any event
within [24] hours, after becoming aware of a personal data breach affecting
Customer Data.

8.2 The notice will describe, as far as then known: what happened and when;
the categories and approximate volume of data and stores affected; the likely
consequences; and the steps taken or proposed. Footrail will update it as
more becomes known.

8.3 Footrail will co-operate with the Customer so that the Customer can meet
its own duty to notify the Board and affected Data Principals under section
8(6) of the Act and the Rules.

## 9. Retention, return and deletion

9.1 During the term, Customer Data is retained as described in Annex A, which
the Customer can shorten using the Service's settings or by written
instruction.

9.2 Within [30] days after the end of the Main Agreement, Footrail will, at
the Customer's choice, provide an export of the Customer's analytics in CSV
form and then delete all Customer Data from its systems and its
sub-processors' systems, and confirm the deletion in writing. Backups held by
sub-processors will be deleted on their normal backup cycle, no later than
[60] days after the end of the Main Agreement, and will not be restored in
the meantime.

## 10. Records and audits

10.1 Footrail will make available to the Customer the information reasonably
needed to show compliance with this DPA, including the Service's audit log of
user actions.

10.2 The Customer may, at most [once a year] and on [30] days' notice, audit
Footrail's compliance with this DPA itself or through an independent auditor
bound by confidentiality, at the Customer's cost.

## 11. Liability

[Liability under this DPA is subject to / excluded from the limits in the Main
Agreement. To be agreed by counsel.]

## 12. Term, law and disputes

12.1 This DPA lasts as long as Footrail processes Customer Data.

12.2 This DPA is governed by the laws of India. The courts at [city] have
exclusive jurisdiction [or: disputes go to arbitration under ...].

12.3 If this DPA conflicts with the Main Agreement on data protection, this
DPA prevails.

---

## Annex A: Processing details

| Item | Details |
|---|---|
| Purpose | Counting visitors, measuring use of store areas, queue lengths and waits, and comparing them with sales totals, to help the Customer run its stores. |
| Data Principals | Shoppers and store staff who appear on the cameras covered by the Service; Customer staff who use the dashboard. |
| Categories of data | (1) CCTV video and still images, which may show identifiable people. (2) Anonymous movement events: times, zones, temporary track numbers, positions in the frame. (3) POS transaction totals with no shopper identity. (4) Dashboard users' email, name, role and audit log including IP address. |
| Sensitive data | None intended. No biometric identification or face templates are created. Children may appear on cameras (see the open question on children in the privacy pack). |
| Nature of processing | Automated person detection and tracking within each camera view; aggregation into counts and durations; storage; display in the dashboard; CSV/PDF export. |
| Retention | Live video via the in-store box: not stored. Uploaded recordings and annotated frames: [30] days. Still images of camera views: until replaced or removed. Anonymous events and POS totals: for the term. Audit-log IP addresses: [90] days. |
| Location | [To be agreed.] |

## Annex B: Security measures (as built today)

* Each Customer's data is separated in the database by organisation; every
  request is checked against the user's organisation and store access.
* Role-based access: HQ admin, HQ viewer, regional manager, store manager.
* Passwords stored as salted scrypt hashes. Sessions are signed tokens in
  httpOnly cookies with CSRF protection; signing out everywhere, changing a
  password or deactivating a user ends all sessions.
* Rate limits on sign-in, uploads and box pairing.
* In-store boxes use a one-time pairing code (30-minute expiry) and then a
  long random token stored only as a hash on the server; an admin can revoke
  a box at any time. Camera passwords stay on the box.
* Audit log of sign-ins, user and role changes, setup changes, uploads,
  report downloads and box pairing.
* Automatic deletion of uploaded recordings and annotated frames, and blanking
  of audit-log IP addresses, after the configured periods.
* Data in transit protected by TLS (HTTPS) between browsers, boxes and the
  service. Encryption at rest is provided by the hosting providers in
  Annex C.
* No face recognition or demographic estimation code in the product.

[To be completed before signing: backup schedule and restore testing,
vulnerability management, staff access controls at Footrail, incident
response contacts. See SECURITY_FAQ.md for the current state.]

## Annex C: Sub-processors

None of these accounts exists yet. The list must be confirmed, with regions,
before signing.

| Provider | Used for | Data | Region |
|---|---|---|---|
| [Railway] | Running the API and the video worker | All categories while processing | [to be chosen] |
| [Neon] | PostgreSQL database | Events, POS totals, users, audit log | [to be chosen] |
| [Cloudflare R2] | Object storage | Uploaded recordings, still images, annotated frames, tracks files | [to be chosen] |
| [Vercel] | Hosting the dashboard web pages | Passes requests through to the API; stores no Customer Data | [to be chosen] |
