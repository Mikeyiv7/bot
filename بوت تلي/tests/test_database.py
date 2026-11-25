import tempfile
import unittest
from pathlib import Path

from database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp_dir.name) / "test.sqlite3"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_user_profile_does_not_store_unverified_phone(self):
        self.db.upsert_user(1001, "mikey")
        user = self.db.get_user(1001)
        self.assertEqual(user["user_id"], 1001)
        self.assertEqual(user["username"], "mikey")
        self.assertIsNone(user["phone"])

    def test_orders_are_idempotent_and_counted(self):
        self.db.upsert_user(1001, "mikey")
        first = self.db.create_order(1001, "Plus", 20, "1 GB", "30 يوم", "once")
        duplicate = self.db.create_order(1001, "Plus", 20, "1 GB", "30 يوم", "once")
        self.assertEqual(first, duplicate)
        self.assertEqual(self.db.get_stats()["orders"], 1)

    def test_pause_state_persists(self):
        self.assertFalse(self.db.orders_paused())
        self.db.set_orders_paused(True)
        self.assertTrue(self.db.orders_paused())
        self.db.set_orders_paused(False)
        self.assertFalse(self.db.orders_paused())


if __name__ == "__main__":
    unittest.main()
