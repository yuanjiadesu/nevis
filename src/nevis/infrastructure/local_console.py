import base64
import hashlib
import hmac


class LocalConsoleCookieCodec:
    _marker = "local-console-v1"

    def __init__(self, key: str) -> None:
        self._key = key.encode()

    def issue(self) -> str:
        signature = hmac.new(self._key, self._marker.encode(), hashlib.sha256).digest()
        encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{self._marker}.{encoded}"

    def accepts(self, value: str | None) -> bool:
        if value is None:
            return False
        return hmac.compare_digest(value, self.issue())
