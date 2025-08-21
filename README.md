# Pulse

A FastAPI application with JWT + Supabase authentication.

## Features

- 🔐 JWT-based authentication
- 🗄️ Supabase database integration
- 🔒 Password hashing with bcrypt
- 🚀 FastAPI with automatic API documentation
- 🛡️ Protected routes with middleware

## Setup

### 1. Environment Variables

Create a `.env` file in the root directory:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
```

### 2. Database Setup

1. Go to your Supabase project dashboard
2. Navigate to the SQL Editor
3. Run the following SQL to create the users table:

```sql
-- Create users table
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Create policy for users to read their own data
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

-- Create policy for users to update their own data
CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);

-- Create policy for public registration
CREATE POLICY "Allow public registration" ON users
    FOR INSERT WITH CHECK (true);
```

### 3. Install Dependencies

1. Activate your virtual environment:
   ```bash
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

### Option 1: Using the launcher script (Recommended)
```bash
python run.py
```

### Option 2: Using uvicorn directly
```bash
uvicorn Pulse.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: From the Pulse directory
```bash
cd Pulse
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Public Endpoints
- `GET /` - Welcome message
- `GET /health` - Health check
- `POST /auth/register` - User registration
- `POST /auth/login` - User login

### Protected Endpoints (Require JWT Token)
- `GET /auth/me` - Get current user profile
- `GET /auth/verify` - Verify token validity

## Authentication Flow

1. **Register**: `POST /auth/register` with email, password, first_name, and last_name
2. **Login**: `POST /auth/login` with email and password to get JWT token
3. **Use Token**: Include `Authorization: Bearer <token>` header for protected routes

## Example Usage

### Register a new user
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123", "first_name": "John", "last_name": "Doe"}'
```

### Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### Access protected route
```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer <your-jwt-token>"
```

## Access

- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Security Features

- Password hashing with bcrypt
- JWT token expiration (30 minutes by default)
- Protected routes with middleware
- Supabase Row Level Security (RLS)

## Troubleshooting

If you encounter import errors, make sure you're running the application from the root directory using one of the methods above. The launcher script (`python run.py`) is the most reliable method.
