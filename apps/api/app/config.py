from os import getenv

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_env: str = Field(default="development", min_length=1)
    log_level: str = Field(default="info", min_length=1)
    service_version: str = Field(default="0.1.0", min_length=1)
    supabase_jwt_secret: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_jwks_url: str | None = None
    supabase_jwt_audience: str = Field(default="authenticated", min_length=1)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    @classmethod
    def from_environment(cls) -> "Settings":
        issuer = (getenv("SUPABASE_JWT_ISSUER") or "").rstrip("/") or None
        return cls(
            app_env=getenv("APP_ENV", "development"),
            log_level=getenv("LOG_LEVEL", "info"),
            service_version=getenv("SERVICE_VERSION", "0.1.0"),
            supabase_jwt_secret=getenv("SUPABASE_JWT_SECRET"),
            supabase_jwt_issuer=issuer,
            supabase_jwt_jwks_url=getenv("SUPABASE_JWT_JWKS_URL")
            or (f"{issuer}/.well-known/jwks.json" if issuer else None),
            supabase_jwt_audience=getenv("SUPABASE_JWT_AUDIENCE", "authenticated"),
            cors_origins=[
                origin.strip()
                for origin in getenv(
                    "CORS_ORIGINS",
                    "http://localhost:3000,http://127.0.0.1:3000",
                ).split(",")
                if origin.strip()
            ],
        )

    def validate_for_production(self) -> None:
        if self.app_env != "production":
            return
        missing = []
        if not self.supabase_jwt_secret and not self.supabase_jwt_jwks_url:
            missing.append("SUPABASE_JWT_SECRET or SUPABASE_JWT_JWKS_URL")
        if not self.supabase_jwt_issuer:
            missing.append("SUPABASE_JWT_ISSUER")
        if missing:
            raise ValueError(f"Missing production configuration: {', '.join(missing)}")
