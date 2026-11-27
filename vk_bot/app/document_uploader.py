import json
import socket
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout, FormData, TCPConnector
from vkbottle.tools import DocMessagesUploader


class DocumentMessagesUploader(DocMessagesUploader):
    async def get_server(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("type", "doc")
        return await super().get_server(**kwargs)

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
        # Uploading over IPv6 returns a gateway error from VK on our server.
        async with ClientSession(
            connector=TCPConnector(family=socket.AF_INET),
            timeout=ClientTimeout(total=120),
        ) as session:
            async with session.post(upload_url, data=form) as response:
                response.raise_for_status()
                uploaded = json.loads(await response.text())
        if not uploaded.get("file"):
            raise RuntimeError("ВК не принял документ на сервер загрузки")
        return uploaded
