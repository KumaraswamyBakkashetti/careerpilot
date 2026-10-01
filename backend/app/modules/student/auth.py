from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.modules.student.models import StudentIdentity, TokenResponse
from app.modules.student.repository import StudentRepository

ALGORITHM = "HS256"
ISSUER = "careerpilot"
AUDIENCE = "careerpilot-api"


class AuthService:
    def __init__(self, settings: Settings, repository: StudentRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.passwords = PasswordHash.recommended()

    def available_secret(self) -> str:
        secret = self.settings.jwt_secret.get_secret_value()
        if len(secret) < 32:
            raise ApplicationError("AUTH_NOT_CONFIGURED")
        return secret

    def hash_password(self, password: str) -> str:
        return self.passwords.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return self.passwords.verify(password, password_hash)

    def token(self, student_id: str) -> TokenResponse:
        now = datetime.now(UTC)
        ttl = timedelta(minutes=self.settings.jwt_ttl_minutes)
        encoded = jwt.encode(
            {
                "sub": student_id,
                "iss": ISSUER,
                "aud": AUDIENCE,
                "iat": now,
                "exp": now + ttl,
                "jti": uuid4().hex,
            },
            self.available_secret(),
            algorithm=ALGORITHM,
        )
        return TokenResponse(access_token=encoded, expires_in=int(ttl.total_seconds()))

    def identity(self, token: str) -> StudentIdentity:
        try:
            payload = jwt.decode(
                token,
                self.available_secret(),
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": ["sub", "exp", "iat", "jti"]},
            )
            return StudentIdentity(student_id=payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise ApplicationError("AUTHENTICATION_REQUIRED") from exc
