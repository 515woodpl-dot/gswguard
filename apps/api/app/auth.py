from __future__ import annotations

import logging
from enum import StrEnum
from typing import Annotated, Callable
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AppRole(StrEnum):
    owner = "owner"
    administrator = "administrator"
    viewer = "viewer"


class AuthenticatedUser(BaseModel):
    user_id: UUID
    email: str | None = None
    role: AppRole | None = None
    organization_id: UUID | None = None


class JwtVerifier:
    def __init__(
        self,
        secret: str | None,
        issuer: str | None,
        audience: str = "authenticated",
        jwks_url: str | None = None,
    ):
        self.secret = secret
        self.issuer = issuer
        self.audience = audience
        self.jwks_client = jwt.PyJWKClient(jwks_url) if jwks_url else None

    def verify(self, token: str) -> AuthenticatedUser:
        if not self.secret and self.jwks_client is None:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        options = {"require": ["exp", "sub"]}
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
            if algorithm == "ES256":
                if self.jwks_client is None:
                    raise jwt.InvalidTokenError("JWKS verification is not configured")
                key = self.jwks_client.get_signing_key_from_jwt(token).key
                algorithms = ["ES256"]
            elif algorithm == "HS256":
                key = self.secret
                algorithms = ["HS256"]
            else:
                raise jwt.InvalidAlgorithmError("Unsupported JWT algorithm")
        except jwt.PyJWTError as exc:
            logger.warning("JWT key selection failed: %s", type(exc).__name__)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        kwargs: dict[str, object] = {"algorithms": algorithms, "audience": self.audience, "options": options}
        if self.issuer:
            kwargs["issuer"] = self.issuer
        try:
            claims = jwt.decode(token, key, **kwargs)
            user_id = UUID(str(claims["sub"]))
        except (KeyError, ValueError, jwt.PyJWTError) as exc:
            logger.warning("JWT verification failed: %s", type(exc).__name__)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        role = claims.get("role")
        return AuthenticatedUser(
            user_id=user_id,
            email=claims.get("email"),
            role=AppRole(role) if role in {r.value for r in AppRole} else None,
            organization_id=UUID(claims["organization_id"]) if claims.get("organization_id") else None,
        )


def bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return token


def current_user(request: Request, token: Annotated[str, Depends(bearer_token)]) -> AuthenticatedUser:
    verifier: JwtVerifier = request.app.state.jwt_verifier
    user = verifier.verify(token)
    repository = getattr(request.app.state, "membership_repository", None)
    if repository is not None:
        membership = repository.resolve(user.user_id)
        if membership is None:
            # Once the database-backed membership boundary is configured, JWT
            # role and organization claims are not sufficient authorization.
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization membership required")
        role, organization_id = membership
        user = user.model_copy(update={"role": role, "organization_id": organization_id})
    return user


def require_roles(*allowed: AppRole) -> Callable[..., AuthenticatedUser]:
    def dependency(user: Annotated[AuthenticatedUser, Depends(current_user)]) -> AuthenticatedUser:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency
