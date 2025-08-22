#!/usr/bin/env python3
"""
Test script for Pulse Chatbot functionality
Run this after setting up your environment and database

Note: This system uses your custom public.users table, not Supabase's auth.users
"""

import asyncio
import httpx
import json
from datetime import datetime

# Configuration - Update these values
BASE_URL = "http://localhost:8000"
JWT_TOKEN = "your_jwt_token_here"  # Get this from login endpoint

async def test_chatbot():
    """Test the chatbot functionality"""
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("🧪 Testing Pulse Chatbot...")
    print("=" * 50)
    
    # Test 1: Create a new chat session
    print("\n1. Creating new chat session...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/chat/sessions",
                json={
                    "title": "Test Chat Session",
                    "system_prompt": "You are a helpful test assistant."
                },
                headers=headers
            )
            
            if response.status_code == 200:
                session_data = response.json()
                session_id = session_data["id"]
                print(f"✅ Session created: {session_data['title']} (ID: {session_id})")
            else:
                print(f"❌ Failed to create session: {response.status_code}")
                print(f"Response: {response.text}")
                return
                
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return
    
    # Test 2: Send a message
    print("\n2. Sending chat message...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/chat/send",
                json={
                    "message": "Hello! This is a test message. Can you respond?",
                    "session_id": session_id,
                    "temperature": 0.7
                },
                headers=headers
            )
            
            if response.status_code == 200:
                chat_response = response.json()
                print(f"✅ Message sent successfully!")
                print(f"Response: {chat_response['response']}")
                print(f"Session ID: {chat_response['session_id']}")
            else:
                print(f"❌ Failed to send message: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error sending message: {e}")
    
    # Test 3: Get session with messages
    print("\n3. Retrieving session with messages...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/chat/sessions/{session_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                session_data = response.json()
                print(f"✅ Session retrieved successfully!")
                print(f"Title: {session_data['title']}")
                print(f"Messages: {len(session_data['messages'])}")
                for i, msg in enumerate(session_data['messages']):
                    print(f"  {i+1}. [{msg['role']}]: {msg['content'][:100]}...")
            else:
                print(f"❌ Failed to retrieve session: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error retrieving session: {e}")
    
    # Test 4: Get all sessions
    print("\n4. Retrieving all sessions...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/chat/sessions?limit=10",
                headers=headers
            )
            
            if response.status_code == 200:
                sessions = response.json()
                print(f"✅ Retrieved {len(sessions)} sessions")
                for i, session in enumerate(sessions):
                    print(f"  {i+1}. {session['title']} (ID: {session['id']})")
            else:
                print(f"❌ Failed to retrieve sessions: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error retrieving sessions: {e}")
    
    # Test 5: Send another message to continue conversation
    print("\n5. Sending follow-up message...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/chat/send",
                json={
                    "message": "Thank you! Can you remember what I said earlier?",
                    "session_id": session_id,
                    "temperature": 0.7
                },
                headers=headers
            )
            
            if response.status_code == 200:
                chat_response = response.json()
                print(f"✅ Follow-up message sent successfully!")
                print(f"Response: {chat_response['response']}")
            else:
                print(f"❌ Failed to send follow-up message: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error sending follow-up message: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Chatbot testing completed!")
    print(f"📝 Test session ID: {session_id}")
    print("💡 You can continue testing with this session ID")

def print_setup_instructions():
    """Print setup instructions"""
    print("🚀 Pulse Chatbot Test Setup")
    print("=" * 50)
    print("\nBefore running this test, ensure you have:")
    print("1. ✅ Started your Pulse FastAPI server")
    print("2. ✅ Set up your .env file with proper credentials")
    print("3. ✅ Run the database migration in Supabase")
    print("4. ✅ Deployed your edge function")
    print("5. ✅ Obtained a valid JWT token")
    print("\n📋 Important Notes:")
    print("• This system uses your custom public.users table (not auth.users)")
    print("• Ensure your users table has 'id' and 'email' columns")
    print("• JWT tokens should contain the user's email in the 'sub' field")
    print("\n🔑 To get a JWT token:")
    print("1. Register/login at POST /api/auth/register or POST /api/auth/login")
    print("2. Copy the access_token from the response")
    print("3. Update JWT_TOKEN in this script")
    print("\n🗄️ Database Requirements:")
    print("• public.users table must exist with proper structure")
    print("• chat_sessions and chat_messages tables (created by migration)")
    print("• Proper RLS policies for security")
    print("\n▶️ To run the test:")
    print("python test_chatbot.py")

if __name__ == "__main__":
    if JWT_TOKEN == "your_jwt_token_here":
        print_setup_instructions()
    else:
        asyncio.run(test_chatbot())
