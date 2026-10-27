"""Offline checks for own name/phone collection and CRM field mapping."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import handlers
import bitrix
import state
from validators import parse_contact, parse_referral_contact, validate_name


class ContactParsingTests(unittest.TestCase):
    def test_both_separators_and_phone_first(self):
        for raw in ["Сергей +7 900 123-45-67", "Сергей, +7 900 123-45-67",
                    "Сергей 8 (900) 123-45-67", "Сергей, 79001234567",
                    "89001234567, Сергей", "Сергей\n+7 900 123-45-67"]:
            self.assertEqual(parse_contact(raw), ("Сергей", "89001234567"), raw)
            self.assertEqual(parse_referral_contact(raw), ("Сергей", "89001234567"), raw)

    def test_phone_only_allowed_only_for_own_contact(self):
        self.assertEqual(parse_contact("+7 900 123-45-67"), (None, "89001234567"))
        self.assertIsNone(parse_referral_contact("+7 900 123-45-67"))

    def test_invalid_or_multiple_numbers(self):
        for raw in [None, "", "Сергей", "Сергей 890012345678", "Сергей 9001234567",
                    "Сергей +7 900 123-45-67 8 901 123-45-67", "Сергей 123 +7 900 123-45-67"]:
            self.assertIsNone(parse_contact(raw), raw)

    def test_names(self):
        self.assertEqual(validate_name("  Анна-Мария   Петрова "), "Анна-Мария Петрова")
        self.assertEqual(validate_name("John O'Connor"), "John O'Connor")
        for raw in [None, "", "123", "<script>", "Иван 123", "https://example.com"]:
            self.assertIsNone(validate_name(raw), raw)

    def test_bitrix_uses_entered_name_not_username(self):
        with patch("lead_format.load_scenario", return_value={"blocks": {}}):
            lead = {"name": "Сергей", "username": "sergey_user", "phone": "89001234567"}
            fields = bitrix._build_lead_fields("Telegram", 7, lead)
        self.assertEqual(fields["NAME"], "Сергей")
        self.assertEqual(fields["PHONE"][0]["VALUE"], "89001234567")
        self.assertIn("@sergey_user", fields["COMMENTS"])
        self.assertNotIn("STATUS_ID", fields)

    def test_old_records_still_have_fallback(self):
        with patch("lead_format.load_scenario", return_value={"blocks": {}}):
            fields = bitrix._build_lead_fields("Telegram", 7, {"username": "old_user"})
        self.assertEqual(fields["NAME"], "@old_user")


class OwnContactFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        state.AWAITING_INPUT.clear()
        state.USER_DATA.clear()
        state.AWAITING_INPUT[7] = dict(
            collect_name=True, save_as="phone", validate="phone", next="consultation_contact",
        )
        self.bot = AsyncMock()
        self.message = SimpleNamespace(
            from_user=SimpleNamespace(id=7, username="user"), chat=SimpleNamespace(id=7), text=None,
        )
        self.patches = [
            patch.object(handlers, "mark_active", AsyncMock()),
            patch.object(handlers, "save_user_contact", AsyncMock()),
            patch.object(handlers, "save_user_field", AsyncMock()),
            patch.object(handlers, "save_referral_contact", AsyncMock()),
            patch.object(handlers, "render_block", AsyncMock()),
            patch.object(handlers, "gate_next_block", AsyncMock(side_effect=lambda bot, uid, target: target)),
        ]
        for p in self.patches:
            p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches):
            p.stop()
        state.AWAITING_INPUT.clear()
        state.USER_DATA.clear()

    async def submit(self, text):
        self.message.text = text
        await handlers.fallback_text_handler(self.message, self.bot)

    async def test_combined_message_saves_both_before_success(self):
        await self.submit("Сергей, +7 900 123-45-67")
        handlers.save_user_contact.assert_awaited_once_with(7, "Сергей", "89001234567")
        handlers.render_block.assert_awaited_once_with(
            self.bot, 7, 7, "consultation_contact", replace=False)
        handlers.save_referral_contact.assert_not_awaited()
        self.assertNotIn(7, state.AWAITING_INPUT)

    async def test_phone_then_name(self):
        await self.submit("89001234567")
        handlers.save_user_contact.assert_not_awaited()
        handlers.render_block.assert_not_awaited()
        await self.submit("Сергей")
        handlers.save_user_contact.assert_awaited_once_with(7, "Сергей", "89001234567")

    async def test_name_then_phone(self):
        await self.submit("Анна-Мария")
        handlers.render_block.assert_not_awaited()
        await self.submit("+7 (900) 123-45-67")
        handlers.save_user_contact.assert_awaited_once_with(7, "Анна-Мария", "89001234567")

    async def test_invalid_input_preserves_waiting_state(self):
        for text in [None, "123", "Сергей 890012345678"]:
            await self.submit(text)
        handlers.save_user_contact.assert_not_awaited()
        handlers.render_block.assert_not_awaited()
        self.assertIn(7, state.AWAITING_INPUT)

    async def test_complete_contact_can_correct_phone_while_waiting_name(self):
        await self.submit("89001234567")
        await self.submit("Иван 89015555555")
        handlers.save_user_contact.assert_awaited_once_with(7, "Иван", "89015555555")

    async def test_duplicate_phone_does_not_become_name(self):
        await self.submit("89001234567")
        await self.submit("89001234567")
        handlers.save_user_contact.assert_not_awaited()
        handlers.render_block.assert_not_awaited()

    async def test_mfc_service_marker_is_not_changed_by_name_collection(self):
        state.AWAITING_INPUT[7]["next"] = "consultation_contact"
        await self.submit("Иван, 89001234567")
        # Service is set when entering the input block, not inferred from typed text.
        handlers.save_user_field.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
