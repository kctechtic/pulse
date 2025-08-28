import json
import requests
from openai import OpenAI
from datetime import datetime
from .database import get_supabase
from .config import settings

# Initialize OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Supabase configuration from environment
SUPABASE_BASE_URL = settings.supabase_edge_function_url
SUPABASE_API_KEY = settings.supabase_anon_key

# Mapping of tool names to Supabase Edge function endpoints
SUPABASE_FUNCTIONS = {
    "getOrdersOverTime": "get-orders-over-time",
}

def create_session(user_id: str, title: str = None):
    """Create a new chat session"""
    try:
        if not user_id:
            raise ValueError("user_id is required")
        
        supabase = get_supabase()
        resp = supabase.table("chat_sessions").insert({
            "user_id": user_id,
            "title": title or "New Chat"
        }).execute()
        
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        else:
            raise Exception("Failed to create session - no data returned")
    except Exception as e:
        print(f"Failed to create session: {str(e)}")
        raise

def call_openai(user_message: str, tools, session_id: str, user_id: str):
    """Main function to handle OpenAI API calls with tool support"""
    try:
        # Get chat history
        history = get_history(session_id)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]

        # Get current date for context
        current_date = datetime.now()
        current_date_str = current_date.strftime("%Y-%m-%d")
        current_year = current_date.year

        # Add system message with current date context
        system_message = {
            "role": "system",
            "content": (
                f"You are a business data analyst assistant. TODAY'S DATE IS {current_date_str} (Year: {current_year}). "
                f"You are helping user {user_id} with business analytics queries. "
                "When users ask about revenue trends, order patterns, or time-based analytics, you MUST use the getOrdersOverTime tool. "
                "You are responsible for analyzing the user's request and determining ALL required parameters: "
                "- interval: Choose 'day', 'week', or 'month' based on the user's request "
                "- start_date: Extract or infer the start date in YYYY-MM-DD format "
                "- end_date: Extract or infer the end date in YYYY-MM-DD format "
                "- currency: Include if the user specifies a currency "
                f"CRITICAL DATE RULE: You are working in {current_year}. When dealing with relative time references "
                f"(like 'last week', 'past 2 weeks', 'this month'), you MUST calculate dates relative to TODAY ({current_date_str}). "
                f"NEVER use dates from {current_year-1} or earlier unless explicitly requested. "
                f"For example: 'last two weeks' should be from 2 weeks ago to {current_date_str}, using {current_year}. "
                f"Current date context: The user wants recent, current data from {current_year}. "
                f"If you see 'last week', 'past week', 'recent', etc., always use dates from {current_year} and recent past. "
                f"Remember: 'last two weeks' means the most recent 2 weeks ending on {current_date_str}, not some arbitrary period from {current_year-1}. "
                f"RESPONSE FORMATTING: Format your responses naturally and clearly, just like ChatGPT does. "
                f"Use **bold** for important numbers and key findings when it makes sense. "
                f"Present data in a readable way that's easy to understand. "
                f"Structure your response logically with clear sections and proper spacing."
            )
        }

        # Prepare messages for OpenAI
        openai_messages = [system_message] + messages + [
            {
                "role": "user", 
                "content": f"Current date context: Today is {current_date_str} (Year {current_year}). Please use this as your reference for all relative time calculations."
            },
            {"role": "user", "content": user_message}
        ]
        
        # Save user message
        save_message(session_id, "user", user_message)

        # Call OpenAI with tools
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=openai_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=4000
        )

        return handle_openai_response(response, session_id, openai_messages)

    except Exception as e:
        error_msg = f"Error in call_openai: {str(e)}"
        print(error_msg)
        save_message(session_id, "assistant", error_msg)
        return error_msg

def handle_openai_response(response, session_id, messages):
    """Handle OpenAI response and tool calls"""
    try:
        message = response.choices[0].message

        # Handle tool calls
        if getattr(message, "tool_calls", None) and message.tool_calls:
            return handle_tool_calls(message.tool_calls, session_id, messages)
        else:
            # No tool call, just return the assistant's response
            reply = message.content or "I apologize, but I couldn't generate a response. Please try rephrasing your question."
            save_message(session_id, "assistant", reply)
            return reply

    except Exception as e:
        error_msg = f"Error handling OpenAI response: {str(e)}"
        print(error_msg)
        save_message(session_id, "assistant", error_msg)
        return error_msg

def handle_tool_calls(tool_calls, session_id, messages):
    """Handle multiple tool calls and return final response"""
    try:
        # Add assistant's tool call request to messages
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls
        })

        # Execute each tool call
        for tool_call in tool_calls:
            try:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments or "{}")
                
                # Call Supabase Edge Function directly with GPT's parameters
                result = call_supabase_edge(fn_name, fn_args)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)
                })

            except Exception as tool_error:
                print(f"Error executing tool {fn_name}: {tool_error}")
                error_result = {"error": f"Tool execution failed: {str(tool_error)}"}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(error_result)
                })

        # Get final response from OpenAI with tool results
        final_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            max_tokens=4000
        )

        final_answer = final_response.choices[0].message.content
        if not final_answer:
            final_answer = "I've processed your request using the available tools. Is there anything specific you'd like to know about the results?"
        
        # Ensure the response is well-formatted for UI display
        final_answer = enhance_response_formatting(final_answer)

        save_message(session_id, "assistant", final_answer)
        return final_answer

    except Exception as e:
        error_msg = f"Error handling tool calls: {str(e)}"
        print(error_msg)
        save_message(session_id, "assistant", error_msg)
        return error_msg

def call_supabase_edge(fn_name: str, args: dict) -> dict:
    """Call Supabase Edge Function with GPT's parameters directly"""
    try:
        mapped_name = SUPABASE_FUNCTIONS.get(fn_name, fn_name)
        url = f"{SUPABASE_BASE_URL}/{mapped_name}"
        
        headers = {
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "apikey": SUPABASE_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Pacer-CIL-Chat/1.0"
        }
        
        response = requests.post(url, headers=headers, json=args, timeout=30)
        
        if response.status_code == 200:
            try:
                result = response.json()
                return result
            except json.JSONDecodeError as e:
                return {"data": response.text, "warning": "Response was not valid JSON"}
        else:
            error_msg = f"Supabase function returned status {response.status_code}: {response.text}"
            print(error_msg)
            return {"error": error_msg, "status_code": response.status_code}
            
    except requests.exceptions.Timeout:
        error_msg = "Request to Supabase function timed out"
        print(error_msg)
        return {"error": error_msg}
    except requests.exceptions.RequestException as req_err:
        error_msg = f"Request to Supabase function failed: {str(req_err)}"
        print(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error calling Supabase function: {str(e)}"
        print(error_msg)
        return {"error": error_msg}

def save_message(session_id: str, role: str, content: str):
    """Save message to database"""
    try:
        if not content or content.strip() == "":
            content = "Empty message"
        
        supabase = get_supabase()
        supabase.table("chat_messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        print(f"Error saving message: {e}")

def get_history(session_id: str) -> list:
    """Get chat history for a session"""
    try:
        supabase = get_supabase()
        history = (
            supabase.table("chat_messages")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
            .data
        )
        return history or []
    except Exception as e:
        print(f"Error getting history: {e}")
        return []

def get_user_chat_sessions(user_id: str, page: int = 1, pagination: int = 10) -> dict:
    """Get paginated chat sessions for a user with basic info"""
    try:
        supabase = get_supabase()
        
        # Calculate offset for pagination
        offset = (page - 1) * pagination
        
        # Get total count of sessions for this user
        total_count_response = (
            supabase.table("chat_sessions")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        total_sessions = total_count_response.count or 0
        
        # Get paginated chat sessions
        sessions = (
            supabase.table("chat_sessions")
            .select("id, title, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + pagination - 1)
            .execute()
            .data
        )
        
        # Get message count for each session
        for session in sessions:
            message_count = (
                supabase.table("chat_messages")
                .select("id", count="exact")
                .eq("session_id", session["id"])
                .execute()
                .count
            )
            session["message_count"] = message_count or 0
            
            # Get last message preview
            last_message = (
                supabase.table("chat_messages")
                .select("content, created_at")
                .eq("session_id", session["id"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            
            if last_message:
                session["last_message"] = last_message[0]["content"][:100] + "..." if len(last_message[0]["content"]) > 100 else last_message[0]["content"]
                session["last_message_time"] = last_message[0]["created_at"]
            else:
                session["last_message"] = "No messages yet"
                session["last_message_time"] = None
        
        # Calculate pagination metadata
        total_pages = (total_sessions + pagination - 1) // pagination if total_sessions > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1
        
        return {
            "sessions": sessions or [],
            "total_sessions": total_sessions,
            "page": page,
            "pagination": pagination,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev
        }
        
    except Exception as e:
        print(f"Error getting user chat sessions: {e}")
        return {
            "sessions": [],
            "total_sessions": 0,
            "page": page,
            "pagination": pagination,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False
        }

def get_chat_detail(session_id: str, user_id: str) -> dict:
    """Get detailed chat information including all messages for a specific session"""
    try:
        supabase = get_supabase()
        
        # First verify the session belongs to the user
        session_check = (
            supabase.table("chat_sessions")
            .select("id, title, created_at, user_id")
            .eq("id", session_id)
            .execute()
            .data
        )
        
        if not session_check:
            raise ValueError("Chat session not found")
        
        if session_check[0]["user_id"] != user_id:
            raise ValueError("You can only view your own chat sessions")
        
        session_info = session_check[0]
        
        # Get all messages for this session
        messages = (
            supabase.table("chat_messages")
            .select("id, role, content, created_at, session_id")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
            .data
        )
        
        return {
            "session_id": session_id,
            "title": session_info["title"],
            "created_at": session_info["created_at"],
            "user_id": user_id,
            "messages": messages or [],
            "total_messages": len(messages) if messages else 0
        }
        
    except Exception as e:
        print(f"Error getting chat detail: {e}")
        raise

def delete_chat_session(session_id: str, user_id: str) -> bool:
    """Delete a chat session and all its messages - requires user ownership verification"""
    try:
        supabase = get_supabase()
        
        # First verify the session belongs to the user
        session_check = (
            supabase.table("chat_sessions")
            .select("id, user_id")
            .eq("id", session_id)
            .execute()
            .data
        )
        
        if not session_check:
            raise ValueError("Chat session not found")
        
        if session_check[0]["user_id"] != user_id:
            raise ValueError("You can only delete your own chat sessions")
        
        # Delete all messages in the session first (due to foreign key constraints)
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        
        # Delete the session
        supabase.table("chat_sessions").delete().eq("id", session_id).execute()
        
        return True
        
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        raise

def enhance_response_formatting(response: str) -> str:
    """Clean up response by removing debug messages while preserving GPT's natural formatting"""
    if not response:
        return response
    
    # Clean up debug messages and unnecessary text
    lines = response.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove debug messages and connection info
        if line.strip().startswith('> [debug]') or line.strip().startswith('[debug]'):
            continue
        if 'Talked to' in line and 'supabase.co' in line:
            continue
        if line.strip() == '':
            cleaned_lines.append(line)
            continue
        
        cleaned_lines.append(line)
    
    # Rejoin and clean up extra whitespace
    cleaned_response = '\n'.join(cleaned_lines).strip()
    
    # Ensure proper spacing around sections
    cleaned_response = cleaned_response.replace('\n\n\n', '\n\n')
    
    return cleaned_response
