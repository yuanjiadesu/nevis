from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.utils import base64url_encode


def _integer_b64(value: int) -> str:
    size = max(1, (value.bit_length() + 7) // 8)
    return base64url_encode(value.to_bytes(size, "big")).decode()


class MutableClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class TestOIDCIssuer:
    __test__ = False

    def __init__(
        self,
        *,
        issuer: str = "https://issuer.example",
        audience: str = "nevis-api",
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.keys: dict[str, rsa.RSAPrivateKey] = {}
        self.published_kids: list[str] = []
        self.fail_requests = False
        self.discovery_issuer = issuer
        self.jwks_uri = "https://issuer.example/keys"
        self.discovery_requests = 0
        self.jwks_requests = 0

    def add_key(self, kid: str, *, publish: bool = True) -> rsa.RSAPrivateKey:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.keys[kid] = key
        if publish:
            self.published_kids.append(kid)
        return key

    def token(
        self,
        kid: str,
        *,
        subject: str = "test-advisor",
        claims: Mapping[str, Any] | None = None,
        remove: tuple[str, ...] = (),
        key: rsa.RSAPrivateKey | str | None = None,
        algorithm: str = "RS256",
        include_kid: bool = True,
    ) -> str:
        now = int(datetime.now(UTC).timestamp())
        payload: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": subject,
            "exp": now + 300,
            "iat": now,
        }
        payload.update(claims or {})
        for name in remove:
            payload.pop(name, None)
        signing_key = key if key is not None else self.keys[kid]
        headers = {"kid": kid} if include_kid else None
        return jwt.encode(payload, signing_key, algorithm=algorithm, headers=headers)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.fail_requests:
            raise httpx.ConnectError("fixture unavailable", request=request)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            self.discovery_requests += 1
            return httpx.Response(
                200,
                json={"issuer": self.discovery_issuer, "jwks_uri": self.jwks_uri},
                request=request,
            )
        if str(request.url) == self.jwks_uri:
            self.jwks_requests += 1
            return httpx.Response(
                200,
                json={"keys": [self.public_jwk(kid) for kid in self.published_kids]},
                request=request,
            )
        return httpx.Response(404, request=request)

    def public_jwk(self, kid: str) -> dict[str, str]:
        numbers = self.keys[kid].public_key().public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": kid,
            "n": _integer_b64(numbers.n),
            "e": _integer_b64(numbers.e),
        }
