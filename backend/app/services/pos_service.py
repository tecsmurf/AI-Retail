"""POS CSV import (idempotent).

Expected columns: order_id, order_date (DD-MM-YYYY or YYYY-MM-DD), order_time
(HH:MM:SS), store_id (POS store code), product_id, brand_name, total_amount.
Dates/times are local to the store; ``ordered_at_utc`` is computed with the
time zone of the store whose ``pos_store_code`` matches (default
Asia/Kolkata when the code is not mapped yet).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import POSTransaction
from app.models.store import Store
from app.services.timerange import store_tz, to_utc_naive

REQUIRED = ("order_id", "order_date", "order_time", "store_id", "product_id", "brand_name", "total_amount")
DEFAULT_TZ = "Asia/Kolkata"


def _parse_date(value: str):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date '{value}'")


async def import_csv(db: AsyncSession, text: str, source: str = "api") -> Dict:
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"CSV is missing columns: {', '.join(missing)}")
    tz_by_code = {
        code: tz for code, tz in (await db.execute(select(Store.pos_store_code, Store.timezone))).all() if code
    }
    existing = {
        (s, o, p)
        for s, o, p in (
            await db.execute(select(POSTransaction.store_id, POSTransaction.order_id, POSTransaction.product_id))
        ).all()
    }
    inserted = 0
    duplicates = 0
    errors: List[str] = []
    for line_no, row in enumerate(reader, start=2):
        try:
            order_id = int(row["order_id"])
            code = row["store_id"].strip()
            product = row["product_id"].strip()
            d = _parse_date(row["order_date"])
            t = datetime.strptime(row["order_time"].strip(), "%H:%M:%S").time()
            amount = float(row["total_amount"])
            if amount < 0:
                raise ValueError("negative amount")
        except (ValueError, KeyError, AttributeError) as exc:
            errors.append(f"line {line_no}: {exc}")
            continue
        key = (code, order_id, product)
        if key in existing:
            duplicates += 1
            continue
        existing.add(key)
        tz = store_tz(tz_by_code.get(code, DEFAULT_TZ))
        db.add(
            POSTransaction(
                order_id=order_id, store_id=code, order_date=d, order_time=t,
                ordered_at_utc=to_utc_naive(datetime.combine(d, t), tz), product_id=product,
                brand_name=row["brand_name"].strip(), total_amount=amount, source=source,
            )
        )
        inserted += 1
    await db.flush()
    return {"inserted": inserted, "duplicates_skipped": duplicates, "errors": errors[:50], "error_count": len(errors)}
