"""Offline upload checks: no Telegram requests."""
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendDocument
import scenario_engine as engine


class MediaUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_pdf_gets_long_timeout_and_russian_name(self):
        bot = AsyncMock()
        await engine.send_file(bot, 1, Path("memo.pdf"), "Памятка.pdf")
        args = bot.send_document.call_args
        self.assertEqual(args.kwargs["request_timeout"], 300)
        self.assertEqual(args.args[1].filename, "Памятка.pdf")

    async def test_timeout_shows_retry_and_does_not_continue_chain(self):
        bot = AsyncMock()
        bot.send_document.side_effect = TelegramNetworkError(
            method=SendDocument(chat_id=1, document="fake"),
            message="Request timeout error",
        )
        scenario = {"blocks": {
            "memo": {"type": "document", "file": "memo.pdf", "text": "Ваша памятка",
                     "auto_next": "next"},
            "next": {"type": "message", "text": "Нельзя отправлять после ошибки"},
        }}
        with patch.object(engine, "SCENARIO", scenario), \
             patch.object(engine, "update_current_stage", AsyncMock()), \
             patch.object(engine, "set_blocked", AsyncMock()), \
             patch.object(Path, "exists", return_value=True):
            await engine._render_block(bot, 1, 7, "memo", False, None)
        messages = [call.args[1] for call in bot.send_message.call_args_list]
        self.assertEqual(len(messages), 2)
        self.assertIn("сбоя связи", messages[-1])
        markup = bot.send_message.call_args.kwargs["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "block:memo")
        self.assertNotIn("Нельзя отправлять после ошибки", messages)
        bot.send_document.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
