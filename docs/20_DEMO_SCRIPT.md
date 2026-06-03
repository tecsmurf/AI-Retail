# Demo Script

## Pre-Demo Checklist
- [ ] Dashboard running at localhost:3000 or Vercel URL
- [ ] Backend API running (verify /docs endpoint)
- [ ] Demo data loaded (247 visitors, 58 purchases)

---

## Demo Flow (5 minutes)

### Opening (30s)
> "PurpleSol is Google Analytics for physical retail. We turn your existing CCTV cameras into a business intelligence platform."

### Screen 1: Executive Dashboard (60s)
**Show**: Full dashboard view

**Talk through**:
- "247 visitors today with a 23.4% conversion rate"
- "₹48,750 in revenue, up 8.1% from yesterday"
- "12 customers currently in the store"
- "3 active alerts — the system is monitoring in real time"

### Screen 2: Hourly Footfall (30s)
**Point to**: Area chart

> "We can see the traffic pattern — peak at 6 PM with 35 visitors. This helps with staff scheduling."

### Screen 3: Conversion Funnel (30s)
**Point to**: Funnel bars

> "Of 247 visitors, 198 visited product zones, 72 reached billing, and 58 purchased. We lose 51% between zone visits and billing — that's our optimization opportunity."

### Screen 4: Zone Performance (45s)
**Point to**: Zone ranking table

> "Faces Canada is the most popular zone with 89 visits and 67 unique visitors. But notice Makeup Unit — fewer visits but highest average dwell time at 2m 26s. This suggests high engagement."

### Screen 5: Customer Journeys (45s)
**Point to**: Journey paths

> "Our top conversion journey is Entry → Faces Canada → L'Oreal → Billing → Exit. 18 customers took this path, all converted. We also see browse-only paths like Entry → Minimalist → Foxtale → Exit."

### Screen 6: Anomaly Center (30s)
**Point to**: Alerts

> "The system automatically detects anomalies. Right now we have a long queue alert — average wait exceeded 45 seconds. This triggers an instant notification to the store manager."

### Screen 7: Multi-Store (30s)
**Point to**: Store comparison

> "We support multiple stores. Store 1 has higher traffic (247 vs 189) and better conversion (23.4% vs 19.8%). Store 2 could learn from Store 1's layout."

### Closing (30s)
> "No new hardware. No customer opt-in. Just AI on your existing cameras. Ready to deploy across all Purplle stores."

---

## Q&A Preparation

**Q: How do you handle privacy?**
A: No facial recognition, no PII storage. We track anonymous person IDs that reset each visit.

**Q: What about accuracy?**
A: YOLO11 achieves >95% person detection accuracy. ByteTrack maintains consistent tracking through occlusion.

**Q: Can it scale?**
A: Each component is independently deployable. Backend on Railway auto-scales. PostgreSQL on Neon handles millions of events.

**Q: What's the deployment cost?**
A: Under $50/month on Vercel + Railway + Neon free tiers. Enterprise: $200-500/month per store.
