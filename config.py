from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Supabase Configuration
    supabase_url: str = "https://roovzqstfwpvvybejjss.supabase.co"
    supabase_anon_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvb3Z6cXN0ZndwdnZ5YmVqanNzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI1ODAxMjIsImV4cCI6MjA2ODE1NjEyMn0.AbcXk30FDednbYS7z8euxY5tWH4gAqicO03yoNPvBRs"
    
    # JWT Configuration
    jwt_secret_key: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    
    # Database Configuration
    database_url: Optional[str] = "Test"
    
    class Config:
        env_file = ".env"

settings = Settings()
