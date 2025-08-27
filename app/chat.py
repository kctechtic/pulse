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
                f"Remember: 'last two weeks' means the most recent 2 weeks ending on {current_date_str}, not some arbitrary period from {current_year-1}."
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
