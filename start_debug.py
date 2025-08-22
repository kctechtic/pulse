#!/usr/bin/env python3
"""
Debug startup script to identify import issues
"""

import sys
import traceback

def main():
    """Main function to test imports step by step"""
    print("🔍 Debugging Pulse imports...")
    print("=" * 50)
    
    try:
        print("1. Testing basic Python imports...")
        import fastapi
        import uvicorn
        print("   ✅ FastAPI and Uvicorn imported")
        
        print("2. Testing config import...")
        from app.config import settings
        print(f"   ✅ Config imported: {settings.supabase_url}")
        
        print("3. Testing database import...")
        from app.database import get_supabase_client
        print("   ✅ Database imported")
        
        print("4. Testing models import...")
        from app.models import ChatMessage, MessageRole, ChatSession
        print("   ✅ Models imported")
        
        print("5. Testing auth import...")
        from app.auth import get_current_user
        print("   ✅ Auth imported")
        
        print("6. Testing chat service import...")
        from app.chat_service import chat_service
        print("   ✅ Chat service imported")
        
        print("7. Testing chat routes import...")
        from app.routes.chat import router
        print("   ✅ Chat routes imported")
        
        print("8. Testing main app import...")
        from main import app
        print("   ✅ Main app imported")
        
        print("\n🎉 All imports successful! Server should start normally.")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed at step: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
