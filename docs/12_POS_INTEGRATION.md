# POS Integration

## Data Source
CSV file with columns: order_id, order_date, order_time, store_id, product_id, brand_name, total_amount

## Sample Data
- Store: ST1008
- Date: 10-04-2026
- 101 line items across ~30 orders
- Brands: Faces Canada, Good Vibes, NY Bae, DERMDOC, Juicy Chemistry, COSRX, Lakme, etc.
- Revenue range: ₹0 (loyalty rewards) to ₹1,448.18

## Correlation Metrics

### Zone-to-Revenue Mapping
Link zone visits to brand purchases:
- Faces Canada zone → Faces Canada brand sales
- L'Oreal zone → L'Oreal brand sales

### Conversion Rate
`Purchases / Total Visitors × 100`

### Revenue per Visitor
`Total Revenue / Total Visitors`

### Average Basket Value
`Total Revenue / Number of Orders`

## Top Brands by Revenue (Sample Data)
1. Faces Canada — ₹14,520
2. L'Oreal — ₹8,340
3. COSRX — ₹2,070
4. Beauty of Joseon — ₹1,278
5. Round Lab — ₹1,448
