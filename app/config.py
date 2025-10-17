from pydantic_settings import BaseSettings
from typing import Optional, Dict
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase projects configuration
supabase_projects = {
    "pulse.pacer.studio": {
        "project_url": "https://roovzqstfwpvvybejjss.supabase.co/",
        "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvb3Z6cXN0ZndwdnZ5YmVqanNzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI1ODAxMjIsImV4cCI6MjA2ODE1NjEyMn0.AbcXk30FDednbYS7z8euxY5tWH4gAqicO03yoNPvBRs"
    },
    "thebodyshop.pacer.studio": {
        "project_url": "https://tfewbenccurmrtahazgr.supabase.co/",
        "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRmZXdiZW5jY3VybXJ0YWhhemdyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDA4NzI2NywiZXhwIjoyMDc1NjYzMjY3fQ.HXXIdPSlTJgJtCraCC8MmGdb0YBir8XVrgtHTcrClZ8"
    }
}

def get_supabase_config(domain: str = None) -> Dict[str, str]:
    """
    Get Supabase configuration based on domain.
    If domain is not provided or not found, returns default configuration.
    """
    try:
        print(f"🔧 Getting Supabase config for domain: {domain}")
        
        if not domain:
            # Return default configuration from environment variables
            config = {
                "project_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
                "api_key": os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
            }
            print(f"📋 Using default config: {config['project_url']}")
            return config
        
        # Extract domain from host header (remove port if present)
        clean_domain = domain.split(':')[0]
        print(f"🧹 Cleaned domain: {clean_domain}")
        
        # Return configuration for the domain or default if not found
        if clean_domain in supabase_projects:
            config = supabase_projects[clean_domain]
            print(f"✅ Found domain-specific config for {clean_domain}: {config['project_url']}")
            return config
        else:
            config = {
                "project_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
                "api_key": os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
            }
            print(f"⚠️  Domain {clean_domain} not found, using default config: {config['project_url']}")
            return config
            
    except Exception as e:
        print(f"💥 Error getting Supabase config: {str(e)}")
        # Fallback to default configuration
        return {
            "project_url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
            "api_key": os.getenv("SUPABASE_ANON_KEY", "your_anon_key")
        }

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
