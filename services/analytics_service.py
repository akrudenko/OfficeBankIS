from datetime import datetime, timedelta
import pandas as pd
from db import DB
import config

def bookings_df(db: DB, start_at: datetime, end_at: datetime) -> pd.DataFrame:
    rows = db.fetchall("""
        SELECT b.BookingID, r.DisplayName, r.ResourceKind, z.ZoneName,
               b.StartAt, b.EndAt, bs.StatusCode
        FROM dbo.Bookings b
        JOIN dbo.Resources r ON r.ResourceID=b.ResourceID
        JOIN dbo.Zones z ON z.ZoneID=r.ZoneID
        JOIN dbo.BookingStatuses bs ON bs.BookingStatusID=b.BookingStatusID
        WHERE b.StartAt < ? AND b.EndAt > ?
          AND bs.StatusCode IN ('APPROVED','PENDING')
    """, (end_at, start_at))
    data = []
    for x in rows:
        data.append({
            "BookingID": int(x.BookingID),
            "Resource": str(x.DisplayName),
            "Kind": str(x.ResourceKind),
            "Zone": str(x.ZoneName),
            "StartAt": pd.to_datetime(x.StartAt),
            "EndAt": pd.to_datetime(x.EndAt),
            "Status": str(x.StatusCode),
        })
    return pd.DataFrame(data)

def utilization_by_day(df: pd.DataFrame, start_at: datetime, end_at: datetime) -> pd.DataFrame:
    wd_start = config.WORKDAY_START_HOUR
    wd_end = config.WORKDAY_END_HOUR
    work_minutes = (wd_end - wd_start) * 60

    if df.empty:
        return pd.DataFrame(columns=["Date","BookedMinutes","UtilizationPct"])

    records = []
    cur = start_at.date()
    last = end_at.date()
    while cur <= last:
        day_start = datetime(cur.year, cur.month, cur.day, wd_start, 0, 0)
        day_end = datetime(cur.year, cur.month, cur.day, wd_end, 0, 0)
        mask = (df["StartAt"] < day_end) & (df["EndAt"] > day_start)
        day_df = df[mask]
        booked = 0
        for _, r in day_df.iterrows():
            s = max(r["StartAt"].to_pydatetime(), day_start)
            e = min(r["EndAt"].to_pydatetime(), day_end)
            if e > s:
                booked += int((e - s).total_seconds() // 60)
        records.append({
            "Date": cur.isoformat(),
            "BookedMinutes": booked,
            "UtilizationPct": round(100.0 * booked / max(1, work_minutes), 2),
        })
        cur = cur + timedelta(days=1)

    return pd.DataFrame(records)

def top_resources(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Resource","Minutes"])
    mins = (df["EndAt"] - df["StartAt"]).dt.total_seconds() // 60
    tmp = df.copy()
    tmp["Minutes"] = mins.astype(int)
    return tmp.groupby("Resource", as_index=False)["Minutes"].sum().sort_values("Minutes", ascending=False).head(top_n)
