from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "http://localhost:54321")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
    
    # JWT Configuration
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "your_secret_key")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = os.getenv("JWT_EXPIRE_MINUTES", 30)
    
    # Database Configuration
    database_url: Optional[str] = os.getenv("DATABASE_URL", "http://localhost:54321")
    
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "your_openai_api_key")
    
    # Supabase Edge Function Configuration
    supabase_edge_function_url: str = os.getenv("SUPABASE_EDGE_FUNCTION_URL", "https://your-project.supabase.co/functions/v1")
    supabase_edge_function_key: str = os.getenv("SUPABASE_EDGE_FUNCTION_KEY", "your_supabase_edge_function_key")
    
    class Config:
        env_file = ".env"

settings = Settings()
