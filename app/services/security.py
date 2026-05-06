import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status


@dataclass(slots=True)
class TokenClaims:
    user_id: int
    email: str
    expires_at: int


class PasswordHasher:
    iterations = 100_000

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.iterations)
        return f"{self.iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        iterations_str, salt_b64, digest_b64 = stored_hash.split("$", maxsplit=2)
        salt = base64.b64decode(salt_b64.encode())
        expected_digest = base64.b64decode(digest_b64.encode())
        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations_str),
        )
        return secrets.compare_digest(candidate_digest, expected_digest)


class TokenService:
    def __init__(self, secret_key: str, expire_minutes: int) -> None:
        self.secret_key = secret_key.encode("utf-8")
        self.expire_minutes = expire_minutes

    def issue_access_token(self, user_id: int, email: str) -> str:
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": int((datetime.now(UTC) + timedelta(minutes=self.expire_minutes)).timestamp()),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).digest()
        return (
            f"{base64.urlsafe_b64encode(payload_bytes).decode().rstrip('=')}."
            f"{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"
        )

    def verify_access_token(self, token: str) -> TokenClaims:
        try:
            encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        except ValueError as exc:
            raise self._unauthorized() from exc

        payload_bytes = self._decode_segment(encoded_payload)
        provided_signature = self._decode_segment(encoded_signature)
        expected_signature = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise self._unauthorized()

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
            user_id = int(payload["sub"])
            email = str(payload["email"])
            expires_at = int(payload["exp"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise self._unauthorized() from exc

        if expires_at < int(datetime.now(UTC).timestamp()):
            raise self._unauthorized()

        return TokenClaims(user_id=user_id, email=email, expires_at=expires_at)

    def _decode_segment(self, value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        try:
            return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise self._unauthorized() from exc

    def _unauthorized(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
