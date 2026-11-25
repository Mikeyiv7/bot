import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from database import Database
from mikey_bot import handle_callback, main_keyboard
from services.vodafone import VodafonePlusService


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp_dir.name) / "test.sqlite3"))
        self.user = SimpleNamespace(id=1001, username="user")
        self.query = SimpleNamespace(
            data="",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        self.update = SimpleNamespace(callback_query=self.query, effective_user=self.user)
        self.context = SimpleNamespace(
            application=SimpleNamespace(
                bot_data={
                    "db": self.db,
                    "admin_id": 9000,
                    "vodafone": VodafonePlusService(),
                }
            ),
            user_data={},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_main_menu_has_all_eight_independent_actions(self):
        actions = {
            button.callback_data
            for row in main_keyboard().inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertEqual(
            actions,
            {
                "menu:subscribe",
                "menu:etisalat_gift",
                "menu:vf_1gb_soon",
                "menu:account",
                "menu:orders",
                "menu:packages",
                "menu:support",
                "menu:about",
            },
        )

    def test_home_back_navigation(self):
        self.query.data = "menu:home"
        asyncio.run(handle_callback(self.update, self.context))
        self.query.edit_message_text.assert_awaited_once()
        markup = self.query.edit_message_text.await_args.kwargs["reply_markup"]
        self.assertEqual(len(markup.inline_keyboard), 7)

    def test_each_main_menu_action_has_a_response(self):
        actions = [
            "menu:subscribe",
            "menu:etisalat_gift",
            "menu:vf_1gb_soon",
            "menu:account",
            "menu:orders",
            "menu:packages",
            "menu:support",
            "menu:about",
        ]
        for action in actions:
            with self.subTest(action=action):
                self.query.answer.reset_mock()
                self.query.edit_message_text.reset_mock()
                self.query.data = action
                asyncio.run(handle_callback(self.update, self.context))
                self.query.answer.assert_awaited_once()
                self.query.edit_message_text.assert_awaited_once()

    def test_etisalat_gift_selection_sets_awaiting_phone(self):
        self.query.data = "etisalat_gift:all"
        asyncio.run(handle_callback(self.update, self.context))
        self.assertEqual(self.context.user_data.get("action"), "awaiting_etisalat_phone")
        self.assertEqual(self.context.user_data.get("etisalat_gift_type"), "all")

    def test_support_back_cancels_pending_message(self):
        self.query.data = "menu:support"
        asyncio.run(handle_callback(self.update, self.context))
        self.assertTrue(self.context.user_data["support_waiting"])
        self.query.data = "menu:home"
        asyncio.run(handle_callback(self.update, self.context))
        self.assertNotIn("support_waiting", self.context.user_data)

    def test_admin_can_toggle_a_user_block(self):
        self.db.upsert_user(1002, "other")
        self.context.application.bot_data["admin_id"] = self.user.id
        self.query.data = "admin:user:1002"
        asyncio.run(handle_callback(self.update, self.context))
        self.assertEqual(self.db.get_user(1002)["is_blocked"], 1)


if __name__ == "__main__":
    unittest.main()
