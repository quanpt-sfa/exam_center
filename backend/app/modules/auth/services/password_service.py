"""Password hashing and verification service."""

from __future__ import annotations

from passlib.context import CryptContext


class PasswordService:
    """Encapsulate secure password hashing policy."""

    def __init__(self) -> None:
        self._context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

    def hash_password(self, plain_password: str) -> str:
        return self._context.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self._context.verify(plain_password, hashed_password)
