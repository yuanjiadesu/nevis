import asyncio
import hashlib
import time
from collections.abc import Callable, Mapping
from typing import Any, cast
from urllib.parse import urlparse

import httpx
import jwt

from nevis.domain.identity import (
    AuthenticatedIdentity,
    IdentityCredentials,
    IdentityMode,
    IdentityProvider,
    IdentityProviderHealth,
    IdentityProviderUnavailable,
    InvalidIdentity,
)
from nevis.settings import Settings


class LocalHeaderIdentityProvider:
    mode = IdentityMode.LOCAL_HEADER

    def __init__(self, *, subject_max_length: int = 200) -> None:
        self._subject_max_length = subject_max_length

    async def authenticate(self, credentials: IdentityCredentials) -> AuthenticatedIdentity:
        external_id = (credentials.local_advisor_external_id or "").strip()
        if not external_id or len(external_id) > self._subject_max_length:
            raise InvalidIdentity
        return AuthenticatedIdentity(external_id, self.mode, "local")

    async def healthcheck(self) -> IdentityProviderHealth:
        return IdentityProviderHealth(True, self.mode)

    async def aclose(self) -> None:
        return None


class DeterministicIdentityProvider:
    mode = IdentityMode.DETERMINISTIC

    def __init__(self, external_id: str = "test-advisor") -> None:
        if not external_id.strip():
            raise ValueError("deterministic external identity must not be empty")
        self._identity = AuthenticatedIdentity(external_id.strip(), self.mode, "test")

    async def authenticate(self, credentials: IdentityCredentials) -> AuthenticatedIdentity:
        del credentials
        return self._identity

    async def healthcheck(self) -> IdentityProviderHealth:
        return IdentityProviderHealth(True, self.mode)

    async def aclose(self) -> None:
        return None


class OIDCIdentityProvider:
    mode = IdentityMode.OIDC

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithms: tuple[str, ...],
        token_max_length: int,
        subject_max_length: int,
        clock_skew_seconds: int,
        fresh_ttl_seconds: int,
        max_stale_seconds: int,
        refresh_min_interval_seconds: int,
        timeout_seconds: float,
        response_max_bytes: int,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._algorithms = algorithms
        self._token_max_length = token_max_length
        self._subject_max_length = subject_max_length
        self._clock_skew_seconds = clock_skew_seconds
        self._fresh_ttl_seconds = fresh_ttl_seconds
        self._max_stale_seconds = max_stale_seconds
        self._refresh_min_interval_seconds = refresh_min_interval_seconds
        self._response_max_bytes = response_max_bytes
        self._clock = clock
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None
        self._issuer_id = hashlib.sha256(self._issuer.encode()).hexdigest()[:16]
        self._jwks_uri: str | None = None
        self._keys: dict[str, jwt.PyJWK] = {}
        self._loaded_at: float | None = None
        self._last_refresh_attempt: float | None = None
        self._refresh_lock = asyncio.Lock()

    async def authenticate(self, credentials: IdentityCredentials) -> AuthenticatedIdentity:
        token = credentials.bearer_token or ""
        if not token or len(token) > self._token_max_length:
            raise InvalidIdentity
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise InvalidIdentity from error
        algorithm = header.get("alg")
        kid = header.get("kid")
        if (
            algorithm not in self._algorithms
            or not isinstance(kid, str)
            or not kid
            or len(kid) > 200
        ):
            raise InvalidIdentity

        refreshed = False
        if not self._cache_fresh():
            try:
                await self._refresh(expected_kid=kid)
                refreshed = True
            except IdentityProviderUnavailable:
                if not self._cache_usable() or kid not in self._keys:
                    raise
        key = self._keys.get(kid)
        if key is None and not refreshed:
            try:
                await self._refresh(force=True, expected_kid=kid)
            except IdentityProviderUnavailable:
                raise
            key = self._keys.get(kid)
        if key is None:
            raise InvalidIdentity

        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._clock_skew_seconds,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            raise InvalidIdentity from error
        subject = claims.get("sub")
        if (
            not isinstance(subject, str)
            or not subject.strip()
            or len(subject) > self._subject_max_length
        ):
            raise InvalidIdentity
        return AuthenticatedIdentity(subject, self.mode, self._issuer_id)

    async def healthcheck(self) -> IdentityProviderHealth:
        if self._cache_usable():
            return IdentityProviderHealth(True, self.mode)
        try:
            await self._refresh()
        except IdentityProviderUnavailable:
            return IdentityProviderHealth(False, self.mode)
        return IdentityProviderHealth(self._cache_usable(), self.mode)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _cache_fresh(self) -> bool:
        return self._cache_age() <= self._fresh_ttl_seconds and bool(self._keys)

    def _cache_usable(self) -> bool:
        return self._cache_age() <= self._max_stale_seconds and bool(self._keys)

    def _cache_age(self) -> float:
        if self._loaded_at is None:
            return float("inf")
        return max(0.0, self._clock() - self._loaded_at)

    async def _refresh(self, *, force: bool = False, expected_kid: str | None = None) -> None:
        async with self._refresh_lock:
            if expected_kid is not None and expected_kid in self._keys and self._cache_usable():
                return
            if not force and self._cache_fresh():
                return
            now = self._clock()
            if (
                force
                and self._last_refresh_attempt is not None
                and now - self._last_refresh_attempt < self._refresh_min_interval_seconds
                and self._keys
            ):
                return
            self._last_refresh_attempt = now
            try:
                jwks_uri = self._jwks_uri or await self._discover_jwks_uri()
                response = await self._client.get(jwks_uri)
                jwks = self._bounded_json(response)
                raw_keys = jwks.get("keys")
                if not isinstance(raw_keys, list):
                    raise ValueError("missing keys")
                keys: dict[str, jwt.PyJWK] = {}
                for raw_key in raw_keys:
                    if not isinstance(raw_key, dict):
                        continue
                    if raw_key.get("use") not in (None, "sig"):
                        continue
                    key_ops = raw_key.get("key_ops")
                    if isinstance(key_ops, list) and "verify" not in key_ops:
                        continue
                    kid = raw_key.get("kid")
                    if not isinstance(kid, str) or not kid or len(kid) > 200:
                        continue
                    parsed = jwt.PyJWK.from_dict(cast(dict[str, Any], raw_key))
                    if parsed.algorithm_name not in self._algorithms:
                        continue
                    keys[kid] = parsed
                if not keys:
                    raise ValueError("no supported signing keys")
            except (httpx.HTTPError, jwt.PyJWTError, ValueError, TypeError) as error:
                raise IdentityProviderUnavailable from error
            self._jwks_uri = jwks_uri
            self._keys = keys
            self._loaded_at = self._clock()

    async def _discover_jwks_uri(self) -> str:
        discovery_url = f"{self._issuer}/.well-known/openid-configuration"
        response = await self._client.get(discovery_url)
        discovery = self._bounded_json(response)
        if discovery.get("issuer") != self._issuer:
            raise ValueError("issuer mismatch")
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str) or urlparse(jwks_uri).scheme != "https":
            raise ValueError("invalid JWKS URL")
        return jwks_uri

    def _bounded_json(self, response: httpx.Response) -> Mapping[str, Any]:
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._response_max_bytes:
                    raise ValueError("response too large")
            except ValueError as error:
                raise ValueError("invalid response size") from error
        if len(response.content) > self._response_max_bytes:
            raise ValueError("response too large")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid response")
        return cast(Mapping[str, Any], payload)


def build_identity_provider(settings: Settings) -> IdentityProvider:
    if settings.identity_provider == "local-header":
        return LocalHeaderIdentityProvider(subject_max_length=settings.oidc_subject_max_length)
    if settings.identity_provider == "deterministic":
        return DeterministicIdentityProvider()
    if settings.identity_provider == "oidc":
        assert settings.oidc_issuer is not None
        assert settings.oidc_audience is not None
        return OIDCIdentityProvider(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            algorithms=settings.oidc_algorithms,
            token_max_length=settings.oidc_token_max_length,
            subject_max_length=settings.oidc_subject_max_length,
            clock_skew_seconds=settings.oidc_clock_skew_seconds,
            fresh_ttl_seconds=settings.oidc_jwks_fresh_ttl_seconds,
            max_stale_seconds=settings.oidc_jwks_max_stale_seconds,
            refresh_min_interval_seconds=settings.oidc_jwks_refresh_min_interval_seconds,
            timeout_seconds=settings.oidc_http_timeout_seconds,
            response_max_bytes=settings.oidc_response_max_bytes,
        )
    raise ValueError("unsupported identity provider")
