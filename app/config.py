import os
from pydantic import BaseModel


class Settings(BaseModel):
    UPSTREAM_URL: str = os.getenv("UPSTREAM_URL", "https://test.ooobs.ru/api/orders")
    UPSTREAM_TIMEOUT_SECONDS: float = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "10.0"))
    HTTP_TRUST_ENV: bool = os.getenv("HTTP_TRUST_ENV", "false").lower() in ("1", "true", "yes")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
