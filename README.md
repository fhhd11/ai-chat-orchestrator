# AI Chat Orchestrator

🚀 A high-performance FastAPI microservice that orchestrates streaming chat completions between Supabase Edge Functions and LiteLLM Proxy.

## ✨ Features

- 🔐 **JWT Authentication** via Supabase
- 🌊 **Server-Sent Events (SSE)** streaming for real-time responses
- 💰 **User Balance Verification** before processing requests
- 🔄 **Response Regeneration** with conversation branching
- 📊 **Prometheus Metrics** for monitoring and observability
- 🛡️ **Comprehensive Error Handling** with graceful degradation
- ⚡ **High Performance** with async/await throughout
- 🏗️ **Production Ready** with proper logging, health checks, and security

## 🏗️ Architecture

```
[Client] → [AI Chat Orchestrator] → [Supabase Edge Functions] → [Database]
                  ↓
            [LiteLLM Proxy] → [Various LLM Providers]
```

The orchestrator serves as a bridge between your frontend and the AI infrastructure, handling:

1. **Authentication** - Validates Supabase JWT tokens
2. **Context Building** - Retrieves conversation history via Edge Functions
3. **Streaming** - Proxies real-time responses from LiteLLM
4. **Persistence** - Saves responses back to the database

## 📁 Project Structure

```
ai-chat-orchestrator/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── models.py               # Pydantic models
│   ├── dependencies.py         # Dependency injection
│   ├── middleware.py           # Custom middleware
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat.py            # Chat completion endpoints
│   │   ├── conversations.py   # Conversation management
│   │   └── health.py          # Health check endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── supabase_client.py # Supabase integration
│   │   ├── litellm_client.py  # LiteLLM streaming client
│   │   └── auth_service.py    # JWT authentication
│   └── utils/
│       ├── __init__.py
│       ├── streaming.py       # SSE utilities
│       └── errors.py          # Custom exceptions
├── tests/
│   ├── __init__.py
│   ├── test_chat.py
│   └── test_integration.py
├── requirements.txt
├── .env.example
├── railway.json               # Railway deployment config
├── Dockerfile
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Supabase project with Edge Functions deployed
- LiteLLM instance running
- Environment variables configured

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd ai-chat-orchestrator
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your actual values
```

4. **Run the application**
```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
python -m app.main
```

5. **Access the API**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

## 🔧 Configuration

### Environment Variables

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key  # Optional
EDGE_FUNCTION_URL=https://your-project.supabase.co/functions/v1/conversation-manager

# LiteLLM Configuration
LITELLM_URL=https://your-litellm-instance.railway.app
LITELLM_MASTER_KEY=your_master_key  # Optional

# Security
JWT_SECRET_KEY=your_supabase_jwt_secret
JWT_ALGORITHM=HS256

# Performance Tuning
MAX_CONTEXT_MESSAGES=100
STREAM_TIMEOUT=120
CONNECTION_POOL_SIZE=100

# Monitoring
ENABLE_METRICS=true
LOG_LEVEL=INFO
DEBUG=false
```

### Required Supabase Setup

Ensure your Supabase project has:

1. **Edge Function** deployed at `/conversation-manager` with endpoints:
   - `POST /add-message`
   - `POST /build-context`
   - `POST /save-response`
   - `POST /create-branch`

2. **Database table** `user_profiles` with columns:
   - `id` (UUID, primary key)
   - `litellm_key` (text)
   - `email` (text)
   - `spend` (numeric)
   - `max_budget` (numeric)
   - `available_balance` (numeric)

3. **JWT Secret** configured in your environment

## 📚 API Endpoints

### Chat Completions

**POST** `/v1/chat/completions`

Stream or non-stream chat completions.

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how are you?",
    "stream": true,
    "model": "gpt-4",
    "temperature": 0.7
  }'
```

**Request Body:**
```json
{
  "conversation_id": "uuid",        // Optional, creates new if not provided
  "message": "User message",        // Required
  "model": "gpt-4",                // Optional, uses conversation default
  "temperature": 0.7,              // Optional, 0-2
  "max_tokens": 2000,              // Optional
  "stream": true,                  // Optional, default true
  "parent_message_id": "uuid"      // Optional, for branching
}
```

### Response Regeneration

**POST** `/v1/chat/regenerate`

Regenerate an assistant response by creating a new branch.

```bash
curl -X POST http://localhost:8000/v1/chat/regenerate \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conversation-uuid",
    "message_id": "message-uuid",
    "model": "gpt-4"
  }'
```

### Conversation Management

**GET** `/v1/conversations/{conversation_id}`

Retrieve conversation details and message tree.

```bash
curl -X GET http://localhost:8000/v1/conversations/your-conversation-id \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Health Checks

- **GET** `/health` - Comprehensive health check
- **GET** `/ready` - Readiness probe for Kubernetes
- **GET** `/live` - Liveness probe for Kubernetes

### Monitoring

- **GET** `/metrics` - Prometheus metrics (if enabled)
- **GET** `/info` - Service information

## 🐳 Deployment

### Docker

```bash
# Build image
docker build -t ai-chat-orchestrator .

# Run container
docker run -p 8000:8000 --env-file .env ai-chat-orchestrator
```

### Railway

1. **Connect your repository** to Railway
2. **Set environment variables** in Railway dashboard
3. **Deploy** - Railway will automatically use `railway.json` configuration

The service will be available at your Railway-provided URL.

### Production Considerations

- Set `DEBUG=false` in production
- Use proper logging levels (`INFO` or `WARNING`)
- Configure proper CORS origins instead of `*`
- Set up proper monitoring and alerting
- Use a reverse proxy (nginx) for additional security
- Configure proper health checks for orchestration platforms

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_chat.py

# Run integration tests only
pytest tests/test_integration.py -v
```

## 📊 Monitoring & Metrics

The service exposes Prometheus metrics at `/metrics` when enabled:

- `http_requests_total` - Total HTTP requests by method, endpoint, status
- `http_request_duration_seconds` - Request duration histogram
- `streaming_requests_total` - Streaming chat requests
- `active_streams_gauge` - Currently active streams

### Grafana Dashboard

Create dashboards to monitor:
- Request rates and latencies
- Error rates by endpoint
- Stream success/failure rates
- Service health and uptime

## 🔒 Security

- JWT token validation on all authenticated endpoints
- Input validation with Pydantic models
- Rate limiting ready (implement as needed)
- Secure headers middleware
- Request ID tracking for security auditing
- No sensitive data in logs

## 🛠️ Development

### Code Style

- Follow PEP 8
- Use type hints throughout
- Async/await for all I/O operations
- Comprehensive error handling
- Structured logging

### Adding New Endpoints

1. Create route in appropriate router file
2. Add Pydantic models in `models.py`
3. Update dependencies if needed
4. Add comprehensive tests
5. Update this README

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors (401)**
- Verify JWT secret key matches Supabase
- Check token expiration
- Ensure proper Authorization header format

**Edge Function Errors (500)**
- Check Supabase Edge Function logs
- Verify edge function URL
- Confirm edge function is deployed and accessible

**LiteLLM Errors**
- Verify LiteLLM instance is running
- Check user's litellm_key is valid
- Monitor rate limits

**Streaming Issues**
- Check client SSE implementation
- Verify network doesn't buffer responses
- Monitor connection timeouts

### Logs

Logs are structured and include:
- Request IDs for tracing
- User context (when available)
- Performance metrics
- Error details with stack traces

```bash
# View logs in development
tail -f logs/app.log

# In production with systemd
journalctl -u ai-chat-orchestrator -f
```

## 📄 License

[MIT License](LICENSE)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📞 Support

For issues and questions:
- Check the troubleshooting section
- Review logs for error details
- Open an issue with detailed information

---

Built with ❤️ using FastAPI, Supabase, and LiteLLM