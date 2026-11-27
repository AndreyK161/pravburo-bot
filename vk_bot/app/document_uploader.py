import json
from pathlib import Path
from typing import Any

from aiohttp import FormData
from vkbottle.tools import DocMessagesUploader


class DocumentMessagesUploader(DocMessagesUploader):
    async def upload_files(self, upload_url: str, files: dict[str, Any]) -> dict[str, Any]:
        document = files["file"]
        extension = Path(document.name).suffix
        # VK's upload server needs a plain multipart filename. docs.save
        # separately receives the original title from DocMessagesUploader.
        form = FormData(quote_fields=False)
        form.add_field(
            "file",
            document,
            filename=f"document{extension}",
            content_type="application/octet-stream",
        )
        response = await self.api.http_client.request_text(
            upload_url, method="POST", data=form
        )
        uploaded = json.loads(response)
        if not uploaded.get("file"):
            raise RuntimeError("ВК не принял документ на сервер загрузки")
        return uploaded
