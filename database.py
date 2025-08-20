from supabase import create_client, Client
from config import settings
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Supabase client
supabase: Client = create_client(settings.supabase_url, settings.supabase_anon_key)

def get_supabase() -> Client:
    return supabase

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
