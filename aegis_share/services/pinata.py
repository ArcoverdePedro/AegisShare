import logging
from io import BytesIO

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class PinataError(RuntimeError):
    pass


class PinataClient:
    upload_url = "https://uploads.pinata.cloud/v3/files"
    api_base = "https://api.pinata.cloud/v3/files"

    def __init__(self):
        self.token = settings.PINATA_JWT_TOKEN
        self.timeout = settings.PINATA_TIMEOUT_SECONDS
        self.network = getattr(settings, "PINATA_NETWORK", "public")

    @property
    def headers(self):
        if not self.token:
            raise PinataError("PINATA_JWT_TOKEN nao configurado.")
        return {"Authorization": f"Bearer {self.token}"}

    def upload_bytes(self, content: bytes, *, filename: str) -> dict:
        try:
            response = requests.post(
                self.upload_url,
                headers=self.headers,
                data={"network": self.network, "name": filename},
                files={"file": (filename, BytesIO(content), "application/octet-stream")},
                timeout=(10, self.timeout),
            )
            response.raise_for_status()
            payload = response.json().get("data") or {}
        except (requests.RequestException, ValueError) as exc:
            logger.exception("pinata_upload_failed", extra={"filename": filename})
            raise PinataError("Falha ao enviar arquivo para a Pinata.") from exc

        if not payload.get("id") or not payload.get("cid"):
            raise PinataError("Resposta da Pinata sem id/cid.")
        return payload

    def download_bytes(self, cid: str) -> bytes:
        gateway = settings.PINATA_GATEWAY_URL.format(cid=cid)
        try:
            response = requests.get(gateway, timeout=(10, self.timeout))
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            logger.exception("pinata_download_failed", extra={"cid": cid})
            raise PinataError("Falha ao recuperar arquivo da Pinata.") from exc

    def delete_file(self, file_id: str) -> bool:
        if not file_id:
            return True
        try:
            response = requests.delete(
                f"{self.api_base}/{self.network}/{file_id}",
                headers=self.headers,
                timeout=(5, 30),
            )
            if response.status_code in {200, 202, 204, 404}:
                return True
            response.raise_for_status()
            return True
        except requests.RequestException:
            logger.exception("pinata_delete_failed", extra={"pinata_id": file_id})
            return False

    def ping(self) -> bool:
        if not self.token:
            return False
        try:
            response = requests.get(
                f"{self.api_base}/{self.network}",
                headers=self.headers,
                params={"limit": 1},
                timeout=(3, 5),
            )
            return response.ok
        except requests.RequestException:
            return False
