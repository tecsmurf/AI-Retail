# Assumptions

## Technical
1. CCTV cameras provide at least 15 FPS at 720p resolution
2. Camera positions are fixed (no PTZ during operation)
3. Zone polygons are manually defined per camera view
4. One person = one customer (no multi-person merging)
5. PostgreSQL can handle up to 10M events per store/month
6. Redis TTL of 5 minutes is acceptable for cached analytics

## Business
1. Store operates 9 AM to 10 PM
2. Staff wear identifiable clothing (future feature)
3. Groups entering together can be detected by proximity
4. Queue area is defined and fixed
5. POS data is available in CSV/API format
6. Customer consent is obtained via in-store signage

## Privacy
1. No facial recognition is performed
2. No biometric data is stored
3. Track IDs are ephemeral (reset per visit)
4. No customer re-identification across visits
5. Gender/age predictions are statistical, not identity-linked
