# Pulse Chatbot Implementation

This document explains how to set up and use the ChatGPT-like chatbot functionality in your Pulse project.

## Features

- **User Session Management**: Each user has their own chat sessions
- **Memory Management**: Chat history is maintained per session
- **Supabase Integration**: Uses Supabase for data storage and edge functions
- **Custom GPT Support**: Integrates with your custom GPT edge functions
- **Real-time Chat**: FastAPI-based API for real-time chat interactions
- **Custom User System**: Works with your existing `public.users` table

## Architecture

```
User Request → FastAPI → Chat Service → Supabase Edge Function → AI Response
                ↓
            Supabase Database (public.users, chat_sessions, chat_messages)
```

## Setup Instructions

### 1. Environment Configuration

Copy `env.example` to `.env` and configure:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# JWT Configuration
JWT_SECRET_KEY=your_jwt_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# Chat Configuration
EDGE_FUNCTION_URL=https://your-project.supabase.co/functions/v1/chat
CHAT_TIMEOUT=30
MAX_CONTEXT_MESSAGES=10
DEFAULT_TEMPERATURE=0.7
DEFAULT_MAX_TOKENS=1000
```

### 2. Database Setup

Run the SQL migration in your Supabase SQL editor:

```sql
-- Copy and paste the contents of database_migration.sql
```

This creates:
- `chat_sessions` table for managing chat sessions (references `public.users.id`)
- `chat_messages` table for storing conversation history
- Proper indexes and RLS policies for security
- **Note**: Uses your existing `public.users` table, not Supabase's `auth.users`

### 3. Edge Function Setup

Create a Supabase Edge Function for your custom GPT:

```typescript
// supabase/functions/chat/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

serve(async (req) => {
  try {
    const { messages, system_prompt, temperature, max_tokens } = await req.json()
    
    // Your custom GPT logic here
    // This should follow OpenAI 3.1.0 schema
    
    const response = await yourCustomGPTFunction({
      messages,
      system_prompt,
      temperature,
      max_tokens
    })
    
    return new Response(
      JSON.stringify({ response: response.content }),
      { headers: { "Content-Type": "application/json" } }
    )
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    )
  }
})
```

## API Endpoints

### Chat Operations

#### Send Message
```http
POST /api/chat/send
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "message": "Hello, how are you?",
  "session_id": "optional-existing-session-id",
  "system_prompt": "You are a helpful assistant",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

#### Create Session
```http
POST /api/chat/sessions
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "title": "My Chat Session",
  "system_prompt": "You are a helpful assistant"
}
```

#### Get Sessions
```http
GET /api/chat/sessions?limit=20
Authorization: Bearer <jwt_token>
```

#### Get Session with Messages
```http
GET /api/chat/sessions/{session_id}
Authorization: Bearer <jwt_token>
```

#### Update Session
```http
PUT /api/chat/sessions/{session_id}
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "title": "Updated Title",
  "is_active": true
}
```

#### Delete Session
```http
DELETE /api/chat/sessions/{session_id}
Authorization: Bearer <jwt_token>
```

#### Clear Session Messages
```http
POST /api/chat/sessions/{session_id}/clear
Authorization: Bearer <jwt_token>
```

## Usage Examples

### Python Client Example

```python
import httpx

async def chat_with_bot(message: str, session_id: str = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/chat/send",
            json={
                "message": message,
                "session_id": session_id,
                "temperature": 0.7
            },
            headers={
                "Authorization": "Bearer your_jwt_token"
            }
        )
        return response.json()

# Usage
response = await chat_with_bot("Hello, how are you?")
print(response["response"])
```

### JavaScript/TypeScript Client Example

```typescript
async function chatWithBot(message: string, sessionId?: string) {
  const response = await fetch('http://localhost:8000/api/chat/send', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      temperature: 0.7
    })
  });
  
  return response.json();
}

// Usage
const response = await chatWithBot('Hello, how are you?');
console.log(response.response);
```

## Session Management

### Creating New Sessions
- Sessions are automatically created when sending the first message
- Each session has a unique ID and title
- Sessions can have custom system prompts
- **User association**: Sessions are linked to users via `public.users.id`

### Memory Management
- Chat history is maintained per session
- Configurable context window (default: 10 messages)
- Messages are stored with timestamps and metadata

### Session Lifecycle
1. **Create**: When user sends first message
2. **Active**: During conversation
3. **Update**: When modified (title, system prompt)
4. **Archive**: Soft delete (is_active = false)

## Security Features

- **Row Level Security (RLS)**: Users can only access their own data
- **JWT Authentication**: All endpoints require valid authentication
- **Input Validation**: Pydantic models validate all inputs
- **SQL Injection Protection**: Supabase client handles parameterization
- **Custom User System**: Integrates with your existing `public.users` table

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `CHAT_TIMEOUT` | 30 | Timeout for edge function calls (seconds) |
| `MAX_CONTEXT_MESSAGES` | 10 | Maximum messages to include in context |
| `DEFAULT_TEMPERATURE` | 0.7 | Default AI response randomness |
| `DEFAULT_MAX_TOKENS` | 1000 | Default maximum response length |

## Error Handling

The system handles various error scenarios:

- **Invalid Session**: Returns 404 for non-existent sessions
- **Edge Function Errors**: Gracefully handles API failures
- **Database Errors**: Proper error messages for data issues
- **Authentication Errors**: JWT validation and user verification

## Monitoring and Logging

- All API calls are logged
- Error responses include detailed information
- Database queries are optimized with proper indexing
- Session timestamps track user activity

## Performance Considerations

- **Indexing**: Database tables are properly indexed
- **Pagination**: Session lists support limit parameters
- **Context Window**: Configurable message history for optimal performance
- **Async Operations**: Non-blocking API calls for better responsiveness

## Troubleshooting

### Common Issues

1. **Edge Function Not Responding**
   - Check `EDGE_FUNCTION_URL` in environment
   - Verify Supabase edge function is deployed
   - Check function logs in Supabase dashboard

2. **Database Connection Issues**
   - Verify Supabase credentials
   - Check RLS policies are properly set
   - Ensure tables exist and are accessible
   - Verify `public.users` table structure

3. **Authentication Errors**
   - Verify JWT token is valid
   - Check token expiration
   - Ensure user exists in `public.users` table

### Debug Mode

Enable debug logging by setting log level in your FastAPI configuration.

## Future Enhancements

- **Streaming Responses**: Real-time message streaming
- **File Uploads**: Support for document-based conversations
- **Multi-modal**: Image and audio support
- **Analytics**: Chat session analytics and insights
- **Webhooks**: Integration with external services
