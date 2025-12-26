from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from db import DB
from services.common import get_id_by_code, get_user_roles

@dataclass
class BookingResult:
    ok: bool
    message: str
    booking_id: int | None = None
    requires_approval: bool = False

def has_conflict(db: DB, resource_id: int, start_at: datetime, end_at: datetime) -> bool:
    rows = db.fetchall("""
        SELECT b.BookingID
        FROM dbo.Bookings b
        JOIN dbo.BookingStatuses bs ON bs.BookingStatusID = b.BookingStatusID
        WHERE b.ResourceID = ?
          AND bs.StatusCode NOT IN ('CANCELLED','REJECTED')
          AND b.StartAt < ?
          AND b.EndAt   > ?
    """, (resource_id, end_at, start_at))

    rows = rows or []   # защита на случай некорректного ответа драйвера/обёртки
    return len(rows) > 0

def _zone_is_restricted(db: DB, resource_id: int) -> bool:
    row = db.fetchone("""
        SELECT z.IsRestricted
        FROM dbo.Resources r
        JOIN dbo.Zones z ON z.ZoneID = r.ZoneID
        WHERE r.ResourceID = ?
    """, (resource_id,))
    return bool(row.IsRestricted) if row else False

def _pick_approver_user(db: DB) -> Optional[int]:
    row = db.fetchone("""
        SELECT TOP 1 ur.UserID
        FROM dbo.UserRoles ur
        JOIN dbo.Roles r ON r.RoleID = ur.RoleID
        WHERE r.RoleCode = 'FAC'
        ORDER BY ur.UserID
    """)
    return int(row.UserID) if row else None

def create_booking(
    db: DB,
    resource_id: int,
    requested_by_user_id: int,
    start_at: datetime,
    end_at: datetime,
    title: str,
    notes: str,
    participants: Optional[int],
) -> BookingResult:
    # 1) Проверки
    if end_at <= start_at:
        return BookingResult(False, "End должен быть позже Start.")

    if has_conflict(db, resource_id, start_at, end_at):
        return BookingResult(False, "Конфликт: ресурс занят в выбранный период.")

    # 2) Нужны ли согласования
    roles = get_user_roles(db, requested_by_user_id)
    restricted = _zone_is_restricted(db, resource_id)
    requires_approval = restricted and ("FAC" not in roles) and ("ADM" not in roles)

    # 3) Статус брони
    bs_code = "PENDING" if requires_approval else "APPROVED"
    booking_status_id = get_id_by_code(db, "BookingStatuses", "StatusCode", "BookingStatusID", bs_code)

    # 4) Вставка с OUTPUT (надёжно получаем BookingID)
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO dbo.Bookings(
            ResourceID, RequestedByUserID, StartAt, EndAt,
            Title, Notes, ParticipantsCount, BookingStatusID
        )
        OUTPUT INSERTED.BookingID
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        resource_id, requested_by_user_id, start_at, end_at,
        title or None, notes or None, participants, booking_status_id
    ))

    row = cur.fetchone()
    if not row or row[0] is None:
        db.rollback()
        return BookingResult(False, "Не удалось получить BookingID после вставки (проверь IDENTITY у BookingID).", None)

    booking_id = int(row[0])

    # 5) Если нужно согласование — создаём запись согласования
    if requires_approval:
        approver_id = _pick_approver_user(db)
        if not approver_id:
            db.rollback()
            return BookingResult(False, "Нет согласующего с ролью FAC.", None)

        approval_status_id = get_id_by_code(db, "ApprovalStatuses", "StatusCode", "ApprovalStatusID", "PENDING")
        db.execute("""
            INSERT INTO dbo.BookingApprovals(BookingID, ApproverUserID, ApprovalStatusID)
            VALUES (?, ?, ?)
        """, (booking_id, approver_id, approval_status_id))

    db.commit()
    msg = "Бронь подтверждена." if not requires_approval else "Заявка отправлена на согласование."
    return BookingResult(True, msg, booking_id, requires_approval)


def list_bookings_for_period(db: DB, start_at: datetime, end_at: datetime) -> list:
    return db.fetchall("""
    SELECT b.BookingID, r.DisplayName, r.ResourceKind, b.StartAt, b.EndAt,
           bs.StatusCode, u.Login AS RequestedBy
    FROM dbo.Bookings b
    JOIN dbo.Resources r ON r.ResourceID = b.ResourceID
    JOIN dbo.BookingStatuses bs ON bs.BookingStatusID = b.BookingStatusID
    JOIN dbo.UserAccounts u ON u.UserID = b.RequestedByUserID
    WHERE b.StartAt < ? AND b.EndAt > ?
    ORDER BY b.StartAt
    """, (end_at, start_at))

def cancel_booking(db: DB, booking_id: int) -> None:
    cancelled = get_id_by_code(db, "BookingStatuses", "StatusCode", "BookingStatusID", "CANCELLED")
    db.execute(
        "UPDATE dbo.Bookings SET BookingStatusID=?, UpdatedAt=SYSUTCDATETIME() WHERE BookingID=?",
        (cancelled, booking_id)
    )
    db.commit()

def list_pending_approvals(db: DB, approver_user_id: int) -> list:
    return db.fetchall("""
    SELECT a.ApprovalID, a.BookingID, r.DisplayName, b.StartAt, b.EndAt,
           u.Login AS RequestedBy, aps.StatusCode AS ApprovalStatus
    FROM dbo.BookingApprovals a
    JOIN dbo.Bookings b ON b.BookingID = a.BookingID
    JOIN dbo.Resources r ON r.ResourceID = b.ResourceID
    JOIN dbo.UserAccounts u ON u.UserID = b.RequestedByUserID
    JOIN dbo.ApprovalStatuses aps ON aps.ApprovalStatusID = a.ApprovalStatusID
    WHERE a.ApproverUserID=? AND aps.StatusCode='PENDING'
    ORDER BY b.StartAt
    """, (approver_user_id,))

def decide_approval(db: DB, approval_id: int, approve: bool) -> None:
    new_appr = "APPROVED" if approve else "REJECTED"
    aps_id = get_id_by_code(db, "ApprovalStatuses", "StatusCode", "ApprovalStatusID", new_appr)
    db.execute(
        "UPDATE dbo.BookingApprovals SET ApprovalStatusID=?, DecidedAt=SYSUTCDATETIME() WHERE ApprovalID=?",
        (aps_id, approval_id)
    )
    row = db.fetchone("SELECT BookingID FROM dbo.BookingApprovals WHERE ApprovalID=?", (approval_id,))
    booking_id = int(row.BookingID)

    bs_code = "APPROVED" if approve else "REJECTED"
    bs_id = get_id_by_code(db, "BookingStatuses", "StatusCode", "BookingStatusID", bs_code)
    db.execute(
        "UPDATE dbo.Bookings SET BookingStatusID=?, UpdatedAt=SYSUTCDATETIME() WHERE BookingID=?",
        (bs_id, booking_id)
    )
    db.commit()
