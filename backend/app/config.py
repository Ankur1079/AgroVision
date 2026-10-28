from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "AgroVision API"
    database_url: str = "postgresql+psycopg://agrovision:change-this-password@localhost:5434/agrovision"
    jwt_secret: str = "replace-with-a-long-random-secret-before-use"
    jwt_exp_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
