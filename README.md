# Pacer CIL Chatbot

A FastAPI-based chatbot that integrates with OpenAI GPT-4 and Supabase Edge Functions to provide business analytics and revenue insights.

## Features

- **GPT-4 Integration**: Uses OpenAI's GPT-4 model for natural language understanding
- **Supabase Edge Functions**: Integrates with custom business analytics functions
- **Smart Date Handling**: Automatically generates current dates for relative time references
- **Session Management**: Maintains chat history and context
- **User Context**: Tracks user identity for personalized responses
- **Authentication Required**: All chat APIs require valid JWT authentication
- **Security**: User ID verification ensures users can only access their own data
- **RESTful API**: Clean FastAPI endpoints for easy integration

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file with the following variables:
```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Supabase Edge Function Configuration
SUPABASE_EDGE_FUNCTION_URL=https://your-project.supabase.co/functions/v1
SUPABASE_EDGE_FUNCTION_KEY=your_supabase_edge_function_key
```

### 3. Start the Server
```bash
uvicorn main:app --reload
```

The server will start at `http://localhost:8000`

### 4. Authentication Flow

1. **Register/Login** to get a JWT token
2. **Include token** in Authorization header for all chat APIs
3. **User ID verification** ensures security

### 5. API Endpoints

#### Create Chat Session (Requires Authentication)
```http
POST /api/chat/create_chat
Authorization: Bearer <your_jwt_token>
{
  "user_id": "user123",
  "title": "Business Analytics Chat"
}
```

#### Send Chat Message (Requires Authentication)
```http
POST /api/chat/chat
Authorization: Bearer <your_jwt_token>
{
  "user_id": "user123",
  "session_id": "session123",
  "message": "Show me revenue trends for the last quarter"
}
```

## Security Features

- **JWT Authentication**: All chat endpoints require valid JWT tokens
- **User ID Verification**: Users can only access their own sessions and messages
- **Session Isolation**: Chat sessions are isolated per user
- **Environment Variables**: API keys stored securely in environment files

## Configuration

The following are configured via environment variables:
- OpenAI API Key
- Supabase Base URL and API Keys
- JWT Secret Key
- Database connection settings

## How It Works

1. **User Authentication**: User must be logged in with valid JWT token
2. **User Verification**: System verifies user ID matches authenticated user
3. **Natural Language Processing**: GPT-4 analyzes the business analytics query
4. **Parameter Generation**: GPT automatically determines required parameters
5. **Edge Function Call**: Supabase Edge Function is called with parameters
6. **Response Processing**: Results are analyzed and presented naturally

## Example Queries

- "Show me revenue trends for the last 30 days"
- "What are the order patterns from January to March 2024?"
- "Give me weekly revenue breakdown for Q1 2024"
- "How have our sales been performing over time?"
- "Show me monthly order trends for 2023"

## Project Structure

```
pulse/
├── app/
│   ├── __init__.py
│   ├── auth.py          # Authentication logic
│   ├── chat.py          # Main chatbot logic
│   ├── config.py        # Environment configuration
│   ├── database.py      # Database operations
│   ├── models.py        # Pydantic models
│   └── routes/
│       ├── __init__.py
│       ├── auth.py      # Authentication endpoints
│       └── chat.py      # Chat API endpoints
├── main.py              # FastAPI application
├── requirements.txt
├── .env                 # Environment variables
└── README.md
```

## Dependencies

- FastAPI
- OpenAI
- Supabase
- Uvicorn
- Pydantic
- Python-Jose
- Passlib
- Python-dotenv

## License

This project is proprietary and confidential.
