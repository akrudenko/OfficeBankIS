import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from security import hash_password, verify_password
from services.booking_service import has_conflict, create_booking

class TestSecurity(unittest.TestCase):
    def test_password_hash(self):
        pwd = "Test123!"
        h = hash_password(pwd)
        self.assertTrue(verify_password(pwd, h))
        self.assertFalse(verify_password("Wrong!", h))

class TestBookingLogic(unittest.TestCase):
    def test_conflict_detection(self):
        db = MagicMock()

        db.fetchall.return_value = [MagicMock(BookingID=123)]
        self.assertTrue(
            has_conflict(
                db,
                resource_id=1,
                start_at=datetime(2025, 1, 1, 10, 0),
                end_at=datetime(2025, 1, 1, 11, 0),
            )
        )

        db.fetchall.return_value = []
        self.assertFalse(
            has_conflict(
                db,
                resource_id=1,
                start_at=datetime(2025, 1, 1, 10, 0),
                end_at=datetime(2025, 1, 1, 11, 0),
            )
        )

        db.fetchall.assert_called()

    def test_conflict_none_rows(self):
        db = MagicMock()
        db.fetchall.return_value = None
        self.assertFalse(
            has_conflict(
                db,
                resource_id=1,
                start_at=datetime(2025, 1, 1, 10, 0),
                end_at=datetime(2025, 1, 1, 11, 0),
            )
        )


    def test_create_booking_invalid_interval(self):
        db = MagicMock()
        t0 = datetime.now()
        t1 = t0 - timedelta(minutes=1)
        res = create_booking(db, resource_id=1, requested_by_user_id=1,
                             start_at=t0, end_at=t1,
                             title="t", notes="", participants=2)
        self.assertFalse(res.ok)

if __name__ == "__main__":
    unittest.main()
