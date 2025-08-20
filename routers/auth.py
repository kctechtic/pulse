from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from models import UserCreate, UserLogin, UserResponse, Token
from database import get_supabase, get_password_hash
from auth import create_access_token, authenticate_user, get_current_user
from datetime import timedelta
from config import settings
from supabase import create_client

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    supabase = get_supabase()
    
    # Check if user already exists
    try:
        existing_user = supabase.table("users").select("*").eq("email", user.email).execute()
        if existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
        )
    
    # Hash password and create user
    hashed_password = get_password_hash(user.password)
    
    try:
        new_user = {
            "email": user.email,
            "password": hashed_password,
            "full_name": user.full_name
        }
        
        response = supabase.table("users").insert(new_user).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        created_user = response.data[0]
        return UserResponse(
            id=created_user["id"],
            email=created_user["email"],
            full_name=created_user["full_name"],
            created_at=created_user["created_at"],
            updated_at=created_user["updated_at"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    user = authenticate_user(user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        created_at=current_user["created_at"],
        updated_at=current_user["updated_at"]
    )

@router.get("/verify")
async def verify_token_validity(current_user: dict = Depends(get_current_user)):
    return {"valid": True, "user_id": current_user["id"]}

@router.get("/supabase-connection")
async def supabase_connection():
    try:
        # Test the connection with a simple query
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        
        # Try to get the current user (this will test the connection)
        response = supabase.auth.get_user()
        
        print(f"Supabase client created successfully")
        print(f"URL: {settings.supabase_url}")
        print(f"Response: {response}")
        
        return {
            "message": "Supabase connection successful",
            "url": settings.supabase_url,
            "status": "connected"
        }
    except Exception as e:
        print(f"Supabase connection error: {str(e)}")
        return {
            "message": f"Supabase connection failed: {str(e)}",
            "url": settings.supabase_url,
            "status": "failed",
            "error": str(e)
        }

@router.get("/test-table")
async def test_table():
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        
        # Test if we can access the database
        response = supabase.table("customers").select("count").execute()
        
        return {
            "message": "Table access successful",
            "table": "customer",
            "response": response.data
        }
    except Exception as e:
        print(f"Table test error: {str(e)}")
        return {
            "message": f"Table access failed: {str(e)}",
            "error": str(e)
        }

@router.get("/customers")
def get_customers():  # user must be logged in
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        
        # First, let's check if the table exists by trying to get its schema
        try:
            # Try to get a single row to test table access
            response = supabase.table("customers").select("*").limit(1).execute()
            
            if hasattr(response, 'error') and response.error:
                raise HTTPException(status_code=400, detail=f"Supabase error: {response.error.message}")
            
            print(f"Response data: {response.data}")
            print(f"Response count: {len(response.data) if response.data else 0}")
            
            return {"customers": response.data or [], "count": len(response.data) if response.data else 0}
            
        except Exception as table_error:
            print(f"Table access error: {str(table_error)}")
            # Try to get all customers if the limit approach fails
            response = supabase.table("customers").select("*").execute()
            
            if hasattr(response, 'error') and response.error:
                raise HTTPException(status_code=400, detail=f"Supabase error: {response.error.message}")
            
            return {"customers": response.data or [], "count": len(response.data) if response.data else 0}
            
    except Exception as e:
        print(f"General error in get_customers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")