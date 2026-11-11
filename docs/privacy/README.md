# Privacy pack (DRAFT, for review by a lawyer)

> **These are drafts written by the engineering team, not legal advice.**
> Have a lawyer who practises Indian data protection law review and adapt
> every document before it is shown to a customer, printed on a sign, or
> signed. Section references are to the Digital Personal Data Protection Act,
> 2023 ("DPDP Act") and should be checked against the current text of the Act
> and the DPDP Rules, 2025.

A retail chain will ask three things before putting Footrail on its cameras:
what data does it collect, where does it go, and who is responsible. This
folder answers those questions from what the code actually does today.

| File | For | What it is |
|---|---|---|
| [DATA_MAP.md](DATA_MAP.md) | Customer's privacy / IT team | Every kind of data Footrail handles, where it is stored, who can see it, and when it is deleted. |
| [SIGNAGE.md](SIGNAGE.md) | Store operations | Text for the notice at the store entrance (English and Hindi), in two versions depending on how the store is connected. |
| [PRIVACY_NOTICE.md](PRIVACY_NOTICE.md) | Customer's website / notice board | The longer notice the sign points to. |
| [DPA_TEMPLATE.md](DPA_TEMPLATE.md) | Legal, both sides | A data processing agreement between the retail chain and Footrail. |
| [SECURITY_FAQ.md](SECURITY_FAQ.md) | Customer's IT / procurement | Answers to the usual security questionnaire, including what is not done yet. |

## Who is who

* **The retail chain is the Data Fiduciary.** It decides to put analytics on
  its cameras and why.
* **Footrail is a Data Processor** acting on the chain's instructions under a
  contract (DPDP Act s. 8(2)). The draft contract is DPA_TEMPLATE.md.
* **Shoppers and store staff are Data Principals** whenever they can be
  identified from what is processed (for example in a video frame).

## How the product keeps personal data small

These are design facts, each backed by code and tests in this repository:

* No facial recognition, no face images stored, no age or gender estimates.
  The event schema still has legacy `gender`/`age` columns; nothing writes to
  them (`backend/app/services/ingest.py` drops those fields from the old
  sample file).
* People are tracked as anonymous numbers within one camera's view. Tracks are
  not linked across cameras or across days, and nothing links a track to a
  name, phone number, loyalty card or payment.
* POS data is imported as order id, time, product, brand and amount. There is
  no customer field in the POS table, so a customer's identity cannot be
  joined to a track.
* With the in-store box (docs/EDGE.md), video is analysed inside the store and
  never uploaded. Only events (times, zone names, anonymous track numbers,
  person-box coordinates) leave the store, plus a still image when an admin
  presses "Get still image" to draw zones.
* With uploaded recordings, the video is stored in the cloud and deleted after
  `VIDEO_RETENTION_DAYS` (default 30). Annotated frames made while processing
  are deleted with it.

## Open legal questions for the lawyer

These need an answer before the first paid deployment. Engineering cannot
answer them.

1. **Lawful basis for shoppers.** The DPDP Act allows processing with consent
   (s. 6) or for a listed "legitimate use" (s. 7). Store analytics is not
   obviously one of the listed uses, and a sign at the door may not meet the
   Act's standard for consent (a clear affirmative action). What basis does
   the chain rely on, and does the answer change because the video is
   processed in memory and only anonymous counts are kept?
2. **Children.** Section 9 restricts tracking and behavioural monitoring of
   children. Cameras see children in a store, and the system cannot tell
   adults from children (and should not try). Does counting and dwell timing
   of anonymous tracks fall under s. 9(3)?
3. **Staff.** Store staff appear on the same cameras. Section 7(i) covers some
   employment purposes. Does it cover footfall analytics, and should staff
   be told separately (for example in the employee handbook)?
4. **Are anonymous tracks personal data?** If the events table is not
   personal data, rights requests (access, erasure) only apply to video and
   stills. If it is, how does the chain answer a request when a track cannot
   be tied to a person?
5. **Retention.** Are the defaults in DATA_MAP.md (30 days for uploaded video,
   90 days for audit-log IP addresses, counts kept for the life of the
   contract) acceptable, and does the chain need shorter ones?
6. **Hosting location.** No cloud region has been chosen yet. Does the chain
   require data to stay in India?
7. **Breach notice.** Section 8(6) and the Rules require the fiduciary to tell
   the Data Protection Board and affected people. What notice period should
   the contract give Footrail to tell the chain (the template says
   24 hours)?
