# Analytics Engine

## Computed Metrics

### Footfall Analytics
- Total visitors (unique ENTRY events)
- Hourly breakdown (24-hour histogram)
- Peak hour identification
- Day-over-day growth rate
- Weekly trends

### Zone Analytics
- Per-zone visit count
- Unique visitor count per zone
- Average dwell time
- Max dwell time
- Zone popularity ranking
- Zone-to-conversion correlation

### Conversion Funnel
```
Total Visitors → Zone Visitors → Product Interactions → Billing → Purchases
    247             198              124                  72        58
   (100%)          (80%)            (63%)               (29%)     (23%)
```

### Queue Analytics
- Average wait time
- Maximum wait time
- Current queue length
- Abandonment rate
- Served vs abandoned counts

### Demographics
- Gender distribution (M/F)
- Age bucket distribution (18-24, 25-34, 35-44, 45-54)

### Revenue Analytics
- Total revenue from POS
- Number of orders
- Average order value
- Top brands by revenue
- Revenue per visitor

## Computation Strategy
- Analytics are computed on-demand from event tables
- Heavy queries use composite indexes for performance
- Frequently accessed metrics cached in Redis (5-minute TTL)
- Historical data supports any time range queries
