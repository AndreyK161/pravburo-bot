"""Offline referral checks: no DB, Telegram or Bitrix calls."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import handlers
import bitrix
import scenario_engine
from state import AWAITING_INPUT
from validators import parse_referral_contact


class ReferralParserTests(unittest.TestCase):
    def test_common_formats(self):
        for raw in [
            "Сергей, +7 900 123-45-67", "Сергей 89001234567",
            "Сергей Петров, 8 (900) 123-45-67", "+7 900 123-45-67, Сергей",
        ]:
            contact = parse_referral_contact(raw)
            self.assertIsNotNone(contact, raw)
            self.assertEqual(contact[1], "89001234567")

    def test_invalid_and_ambiguous(self):
        for raw in [None, "", "Сергей", "89001234567", "Сергей 890012345678",
                    "Сергей 12345678901", "Сергей +7 900 123-45-67, +7 901 123-45-67"]:
            self.assertIsNone(parse_referral_contact(raw), raw)

    def test_bitrix_fields_do_not_use_partners_phone(self):
        referral = dict(id=1, contact_name="Сергей", contact_phone="89001234567",
                        partner_telegram_id=7, partner_name="Иван", partner_username="ivan",
                        marker="partner_first_contact", created_at=datetime.now(timezone.utc))
        fields = bitrix._build_referral_fields(referral)
        self.assertEqual(fields["NAME"], "Сергей")
        self.assertEqual(fields["PHONE"][0]["VALUE"], "89001234567")
        self.assertIn("Telegram ID партнёра: 7", fields["COMMENTS"])
        self.assertIn("partner_first_contact", fields["COMMENTS"])
        self.assertNotIn("STATUS_ID", fields)


class ReferralFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        AWAITING_INPUT.clear()
        AWAITING_INPUT[7] = dict(kind="referral", next="referral_contact_done",
                                failure="referral_contact_failure", attempts=0)
        self.bot = AsyncMock()
        self.message = SimpleNamespace(
            from_user=SimpleNamespace(id=7, username="ivan", full_name="Иван"),
            chat=SimpleNamespace(id=7), message_id=101, text="Сергей, +7 900 123-45-67",
        )
        self.patches = [
            patch.object(handlers, "mark_active", AsyncMock()),
            patch.object(handlers, "save_referral_contact", AsyncMock(return_value={"id": 1})),
            patch.object(handlers, "render_block", AsyncMock()),
            patch.object(handlers, "save_user_field", AsyncMock()),
            patch.object(handlers, "send_referral_to_bitrix", AsyncMock()),
            # Close mocked coroutine without launching a background task.
            patch.object(handlers, "run_in_background", side_effect=lambda coro: coro.close()),
        ]
        for p in self.patches:
            p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches):
            p.stop()
        AWAITING_INPUT.clear()

    async def test_valid_contact_separate_from_profile(self):
        await handlers.fallback_text_handler(self.message, self.bot)
        handlers.save_referral_contact.assert_awaited_once_with(
            7, "Иван", "ivan", "Сергей", "89001234567", 7, 101)
        handlers.save_user_field.assert_not_awaited()
        handlers.render_block.assert_awaited_once_with(
            self.bot, 7, 7, "referral_contact_done", replace=False)
        self.assertNotIn(7, AWAITING_INPUT)

    async def test_two_failures_then_specialist(self):
        self.message.text = "Нет номера"
        await handlers.fallback_text_handler(self.message, self.bot)
        self.assertEqual(AWAITING_INPUT[7]["attempts"], 1)
        self.bot.send_message.assert_awaited_once()
        await handlers.fallback_text_handler(self.message, self.bot)
        self.assertNotIn(7, AWAITING_INPUT)
        handlers.render_block.assert_awaited_once_with(
            self.bot, 7, 7, "referral_contact_failure", replace=False)
        handlers.save_referral_contact.assert_not_awaited()

    async def test_valid_second_attempt(self):
        self.message.text = None
        await handlers.fallback_text_handler(self.message, self.bot)
        self.message.text = "Сергей 89001234567"
        await handlers.fallback_text_handler(self.message, self.bot)
        handlers.save_referral_contact.assert_awaited_once()

    async def test_input_reentry_resets_attempts(self):
        with patch.object(scenario_engine, "update_current_stage", AsyncMock()), \
             patch.object(scenario_engine, "set_blocked", AsyncMock()), \
             patch.object(scenario_engine, "show_text", AsyncMock()):
            AWAITING_INPUT[7]["attempts"] = 1
            await scenario_engine._render_block(
                self.bot, 7, 7, "referral_contact_input", False, None)
        self.assertEqual(AWAITING_INPUT[7]["attempts"], 0)

    async def test_empty_webhook_prevents_external_calls(self):
        with patch.object(bitrix, "BITRIX_WEBHOOK_URL", ""), \
             patch.object(bitrix, "claim_referral_for_bitrix", AsyncMock()) as claim, \
             patch.object(bitrix.aiohttp, "ClientSession") as session:
            await bitrix.send_referral_to_bitrix({"id": 1})
            claim.assert_not_awaited()
            session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
