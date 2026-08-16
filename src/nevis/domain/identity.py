from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class IdentityMode(StrEnum):
    LOCAL_HEADER = "local-header"
    DETERMINISTIC = "deterministic"
    OIDC = "oidc"


@dataclass(frozen=True, slots=True)
class IdentityCredentials:
    bearer_token: str | None = None
    local_advisor_external_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    external_id: str
    mode: IdentityMode
    issuer_id: str


@dataclass(frozen=True, slots=True)
class IdentityProviderHealth:
    available: bool
    mode: IdentityMode


class InvalidIdentity(Exception):
    """Credentials are absent or cannot be authenticated."""


class IdentityProviderUnavailable(Exception):
    """Identity cannot be verified because a required dependency is unavailable."""


class IdentityProvider(Protocol):
    mode: IdentityMode

    async def authenticate(self, credentials: IdentityCredentials) -> AuthenticatedIdentity: ...

    async def healthcheck(self) -> IdentityProviderHealth: ...

    async def aclose(self) -> None: ...
