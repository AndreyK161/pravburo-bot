import socket
import tempfile
from contextlib import asynccontextmanager
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from document_uploader import DocumentMessagesUploader


class DocumentUploadTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def upload_session(self, *, connector, timeout):
        self.assertEqual(connector.family, socket.AF_INET)
        self.assertEqual(timeout.total, 120)

        @asynccontextmanager
        async def post(url, *, data):
            self.assertEqual(url, "https://upload.example.test")
            if hasattr(self, "body"):
                body = self.body

                class Writer:
                    async def write(self, chunk):
                        body.extend(chunk)

                await data().write(Writer())
            yield SimpleNamespace(
                raise_for_status=Mock(),
                text=AsyncMock(return_value=self.upload_response),
            )

        try:
            yield SimpleNamespace(post=post)
        finally:
            await connector.close()

    async def test_upload_uses_ascii_multipart_filename_and_keeps_russian_title(self):
        for extension in (".pdf", ".docx", ".odt", ".jpg"):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / f"Памятка Правбюро{extension}"
                path.write_bytes(b"document contents")
                body = self.body = bytearray()
                self.upload_response = '{"file": "uploaded-file-token"}'

                api = SimpleNamespace(
                    request=AsyncMock(side_effect=[
                        {"response": {"upload_url": "https://upload.example.test"}},
                        {"response": {"type": "doc", "doc": {
                            "owner_id": -123, "id": 456, "access_key": "key",
                        }}},
                    ]),
                )
                with patch("document_uploader.ClientSession", side_effect=self.upload_session):
                    attachment = await DocumentMessagesUploader(api).upload(str(path), peer_id=789)
                self.assertEqual(attachment, "doc-123_456_key")
                self.assertIn(f'filename="document{extension}"'.encode(), body)
                self.assertIn(b'name="file"', body)
                self.assertIn(b"document contents", body)
                method, params = api.request.call_args.args
                self.assertEqual(method, "docs.save")
                self.assertEqual(params["title"], path.name)
                self.assertEqual(params["file"], "uploaded-file-token")

    async def test_rejected_upload_does_not_call_docs_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Памятка.pdf"
            path.write_bytes(b"document contents")
            api = SimpleNamespace(
                request=AsyncMock(return_value={"response": {"upload_url": "https://upload.example.test"}}),
            )
            self.upload_response = "{}"
            with patch("document_uploader.ClientSession", side_effect=self.upload_session), self.assertRaisesRegex(RuntimeError, "ВК не принял документ"):
                await DocumentMessagesUploader(api).upload(str(path), peer_id=789)
            api.request.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
