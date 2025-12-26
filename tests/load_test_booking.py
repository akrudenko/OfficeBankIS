import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from db import DB
from services.booking_service import create_booking

LOAD_PREFIX = "[LOADTEST]"

def _pick_room_ids(db, limit=5):
    rows = db.fetchall("""
        SELECT TOP (?) ResourceID
        FROM dbo.Resources r
        WHERE r.ResourceKind='R'
        ORDER BY r.ResourceID
    """, (limit,))
    return [r.ResourceID for r in rows]

def _worker(resource_id: int, user_id: int, start_at, end_at):
    db = DB.connect()
    try:
        res = create_booking(db, resource_id, user_id, start_at, end_at,
                             title=f"{LOAD_PREFIX} booking", notes="", participants=2)
        return res.ok, res.message
    finally:
        db.close()

def cleanup_loadtest_rows():
    db = DB.connect()
    try:
        db.execute("""
          DELETE a
          FROM dbo.BookingApprovals a
          JOIN dbo.Bookings b ON b.BookingID=a.BookingID
          WHERE b.Title LIKE ?
        """, (f"{LOAD_PREFIX}%",))
        db.execute("DELETE FROM dbo.Bookings WHERE Title LIKE ?", (f"{LOAD_PREFIX}%",))
        db.commit()
    finally:
        db.close()

def run_load(n=200, threads=10, user_id=1):
    cleanup_loadtest_rows()

    db = DB.connect()
    room_ids = _pick_room_ids(db, limit=threads)
    db.close()

    t0 = time.perf_counter()
    ok = 0
    fail = 0

    base = datetime.now() + timedelta(minutes=30)

    futures = []
    with ThreadPoolExecutor(max_workers=threads) as ex:
        for i in range(n):
            rid = room_ids[i % len(room_ids)]
            s = base + timedelta(minutes=2*i)
            e = s + timedelta(minutes=30)
            futures.append(ex.submit(_worker, rid, user_id, s, e))

        for f in as_completed(futures):
            success, _ = f.result()
            if success:
                ok += 1
            else:
                fail += 1

    t1 = time.perf_counter()
    total = t1 - t0
    rps = n / total if total > 0 else 0

    print(f"Requests: {n}, Threads: {threads}")
    print(f"OK: {ok}, FAIL: {fail}")
    print(f"Total time: {total:.2f}s, Throughput: {rps:.2f} req/s")

    cleanup_loadtest_rows()

if __name__ == "__main__":
    run_load(n=200, threads=10, user_id=1)
