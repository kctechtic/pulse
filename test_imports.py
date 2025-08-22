#!/usr/bin/env python3
"""
Test script to check if all imports work correctly
"""

def test_imports():
    """Test all the imports"""
    try:
        print("Testing imports...")
        
        # Test config
        print("1. Testing config import...")
        from app.config import settings
        print(f"   ✅ Config imported: {settings.supabase_url}")
        
        # Test database
        print("2. Testing database import...")
        from app.database import get_supabase_client
        print("   ✅ Database imported")
        
        # Test models
        print("3. Testing models import...")
        from app.models import ChatMessage, MessageRole, ChatSession
        print("   ✅ Models imported")
        
        # Test auth
        print("4. Testing auth import...")
        from app.auth import get_current_user
        print("   ✅ Auth imported")
        
        # Test chat service
        print("5. Testing chat service import...")
        from app.chat_service import chat_service
        print("   ✅ Chat service imported")
        
        # Test chat routes
        print("6. Testing chat routes import...")
        from app.routes.chat import router
        print("   ✅ Chat routes imported")
        
        print("\n🎉 All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()
