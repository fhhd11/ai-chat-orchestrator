# AI Chat Orchestrator

🚀 A production-ready FastAPI microservice that serves as a universal gateway to multiple LLM providers through Supabase Edge Functions and LiteLLM integration.

## ✨ Features

### 🏗️ Architecture & Performance
- 🔐 **JWT Authentication** via Supabase with intelligent user caching
- 🌊 **Server-Sent Events (SSE)** streaming for real-time chat responses
- ⚡ **Universal Edge Function Proxy** with intelligent request routing
- 🗄️ **Redis Caching** with in-memory fallback for high performance
- 🔄 **Advanced Conversation Branching** with message trees and merging
- 📊 **Comprehensive Monitoring** with Prometheus metrics and structured logging

### 🤖 LLM Integration
- 🎯 **Multi-Provider Support** (OpenAI, Anthropic, Google, Meta, Mistral)
- 🔍 **Dynamic Model Discovery** with metadata parsing and caching
- 💰 **Cost Tracking** and user balance verification
- 🎛️ **Advanced Model Comparison** and filtering capabilities
- ⚙️ **Flexible Model Configuration** per conversation

### 🛡️ Production Features
- 🛡️ **Comprehensive Error Handling** with custom exception hierarchy
- 🔍 **Request Tracing** with structured logging and business metrics
- 🚀 **High-Performance Design** with async/await throughout
- 🔒 **Security-First** approach with input validation and sanitization
- 📈 **Analytics & Insights** with user dashboards and usage statistics
- 🏥 **Health Monitoring** with readiness/liveness probes

## 🏗️ Architecture

```
[Frontend] ←→ [AI Chat Orchestrator] ←→ [Supabase Edge Functions] ←→ [Database]
                       ↓
              [Universal Edge Proxy]
                       ↓
               [LiteLLM Service] ←→ [Multiple LLM Providers]
                       ↓
                [Redis Cache Layer]
```

### Service Components

1. **Universal Edge Proxy** - Intelligent request routing to Supabase Edge Functions
2. **LiteLLM Service** - Model management and metadata parsing
3. **Cache Service** - Redis with in-memory fallback for optimal performance
4. **Authentication Service** - JWT validation with user profile caching
5. **Metrics Collection** - Prometheus integration with business analytics

## 📁 Project Structure

```
ai-chat-orchestrator/
├── app/
│   ├── main.py                     # FastAPI application with middleware
│   ├── config.py                   # Comprehensive configuration (50+ settings)
│   ├── dependencies.py             # Service injection and user management
│   ├── models/                     # Pydantic v2 models
│   │   ├── chat.py                # Chat completion models
│   │   ├── conversation.py        # Conversation and branch models  
│   │   ├── message.py             # Message management models
│   │   ├── user.py                # User profile and analytics models
│   │   ├── litellm.py             # LLM model metadata
│   │   └── common.py              # Shared response/pagination models
│   ├── routers/                    # API endpoints
│   │   ├── chat.py                # Enhanced chat completions
│   │   ├── conversations.py       # Full conversation CRUD + search
│   │   ├── branches.py            # Branch management & merging
│   │   ├── messages.py            # Message editing & regeneration
│   │   ├── models.py              # Model discovery & comparison
│   │   ├── users.py               # User profiles & analytics
│   │   └── health.py              # Health checks & monitoring
│   ├── services/                   # Core services
│   │   ├── edge_proxy.py          # Universal Edge Function proxy
│   │   ├── litellm_client.py      # Enhanced LiteLLM service
│   │   ├── cache_service.py       # Redis caching layer
│   │   └── auth_service.py        # JWT authentication
│   └── utils/                      # Utilities
│       ├── errors.py              # Custom exception hierarchy
│       ├── logging.py             # Structured logging system
│       ├── validators.py          # Pydantic validators
│       ├── metrics.py             # Prometheus metrics collection
│       └── streaming.py           # SSE utilities
├── tests/                          # Comprehensive test suite
├── requirements.txt
├── .env.example                    # Environment template
├── railway.json                    # Railway deployment config
├── Dockerfile                      # Production container
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Redis (optional, will fallback to in-memory cache)
- Supabase project with Edge Functions
- LiteLLM instance or API keys for direct provider access

### Local Development

1. **Clone and setup**
```bash
git clone <repository-url>
cd ai-chat-orchestrator
pip install -r requirements.txt
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Run the application**
```bash
# Development with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python module
python -m app.main
```

4. **Access services**
- **API Documentation**: http://localhost:8000/docs
- **Health Dashboard**: http://localhost:8000/health  
- **Prometheus Metrics**: http://localhost:8000/metrics
- **Service Info**: http://localhost:8000/info

## 🔧 Configuration

### Core Environment Variables

```env
# Application
APP_NAME="AI Chat Orchestrator"
VERSION="2.0.0"
ENVIRONMENT="development"
DEBUG=false
LOG_LEVEL="INFO"

# Supabase Integration  
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key
EDGE_FUNCTION_URL=https://your-project.supabase.co/functions/v1

# LiteLLM Configuration
LITELLM_URL=https://your-litellm.railway.app
LITELLM_MASTER_KEY=your_master_key
LITELLM_TIMEOUT=120

# Redis Caching (Optional)
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379
CACHE_TTL_DEFAULT=3600
CACHE_TTL_USER_PROFILE=1800
CACHE_TTL_MODELS=3600

# Security & JWT  
JWT_SECRET_KEY=your_supabase_jwt_secret
JWT_ALGORITHM=HS256
CORS_ORIGINS=["http://localhost:3000"]

# Performance Tuning
MAX_CONTEXT_MESSAGES=100
STREAM_TIMEOUT=120
CONNECTION_POOL_SIZE=100
MAX_CONCURRENT_REQUESTS=50

# Business Logic
MAX_BRANCHES_PER_CONVERSATION=10
MAX_CONVERSATIONS_PER_USER=1000
MAX_MESSAGES_PER_CONVERSATION=500
MIN_BALANCE_THRESHOLD=0.01

# Feature Flags
ENABLE_BRANCH_MERGING=true
ENABLE_MESSAGE_EDITING=true
ENABLE_CONVERSATION_EXPORT=true
ENABLE_USER_ANALYTICS=true
ENABLE_BATCH_OPERATIONS=true

# Monitoring
ENABLE_METRICS=true
ENABLE_STRUCTURED_LOGGING=true
METRICS_PORT=9090
```

### Redis Configuration (Optional)

If Redis is not available, the system automatically falls back to in-memory caching:

```env
# Redis Settings
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your_password
REDIS_MAX_CONNECTIONS=10
REDIS_RETRY_ATTEMPTS=3
```

## 📚 API Reference

### 🎯 Chat Completions

**POST** `/v1/chat/completions`

Enhanced streaming chat with conversation context and branching.

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum computing",
    "conversation_id": "optional-uuid",
    "model": "gpt-4",
    "stream": true,
    "temperature": 0.7,
    "max_tokens": 2000,
    "parent_message_id": "uuid-for-branching"
  }'
```

### 💬 Conversation Management

**GET** `/v1/conversations` - List user conversations with search/filter
**POST** `/v1/conversations` - Create new conversation
**GET** `/v1/conversations/{id}` - Get conversation details
**GET** `/v1/conversations/{id}/full` - Get complete message tree
**POST** `/v1/conversations/batch` - Batch operations
**GET** `/v1/conversations/{id}/export` - Export conversation data

### 🌳 Branch Management

**GET** `/v1/conversations/{id}/branches` - List branches
**POST** `/v1/conversations/{id}/branches` - Create branch
**POST** `/v1/conversations/{id}/branches/{branch_id}/activate` - Switch branch
**POST** `/v1/conversations/{id}/branches/{branch_id}/merge` - Merge branches
**GET** `/v1/conversations/{id}/branches/{branch_id}/stats` - Branch statistics

### 💬 Message Operations

**GET** `/v1/conversations/{id}/messages` - List messages with pagination
**POST** `/v1/conversations/{id}/messages` - Add message
**PATCH** `/v1/conversations/{id}/messages/{msg_id}` - Edit message
**POST** `/v1/conversations/{id}/messages/{msg_id}/regenerate` - Regenerate response
**POST** `/v1/conversations/{id}/messages/search` - Search messages

### 🤖 Model Management

**GET** `/v1/models` - List available models with filtering
**GET** `/v1/models/{model_id}` - Get model details
**GET** `/v1/models/providers` - List providers with statistics  
**GET** `/v1/models/search?q=query` - Search models
**GET** `/v1/models/compare?model_ids=id1,id2` - Compare models
**POST** `/v1/models/refresh` - Refresh model cache

### 👤 User Management

**GET** `/v1/users/me` - Current user profile
**PATCH** `/v1/users/me` - Update profile
**GET** `/v1/users/me/usage` - Usage statistics
**GET** `/v1/users/me/balance` - Balance information
**GET** `/v1/users/me/analytics/dashboard` - Analytics dashboard
**GET** `/v1/users/me/api-keys` - List API keys
**POST** `/v1/users/me/api-keys` - Create API key
**GET** `/v1/users/me/export` - Export user data (GDPR)

### 🏥 Health & Monitoring

**GET** `/health` - Comprehensive health check
**GET** `/ready` - Readiness probe  
**GET** `/live` - Liveness probe
**GET** `/metrics` - Prometheus metrics
**GET** `/info` - Service information

## 🐳 Deployment

### Docker Production

```bash
# Build optimized image
docker build -t ai-chat-orchestrator .

# Run with environment file
docker run -p 8000:8000 --env-file .env ai-chat-orchestrator

# With Redis
docker-compose up -d
```

### Railway Deployment

1. **Fork repository** and connect to Railway
2. **Set environment variables** in Railway dashboard
3. **Deploy** - Automatic deployment via `railway.json`

### Environment-Specific Configuration

**Development:**
```env
DEBUG=true
LOG_LEVEL=DEBUG
REDIS_ENABLED=false  # Use in-memory cache
```

**Production:**
```env
DEBUG=false
LOG_LEVEL=INFO
REDIS_ENABLED=true
ENABLE_METRICS=true
```

## 📊 Monitoring & Analytics

### Prometheus Metrics

Available at `/metrics`:

**HTTP Metrics:**
- `http_requests_total` - Request counts by endpoint/status
- `http_request_duration_seconds` - Response time histograms

**Business Metrics:**
- `chat_completions_total` - Chat requests by model/user
- `chat_tokens_total` - Token usage tracking
- `conversations_total` - Conversation operations
- `revenue_total_usd` - Revenue tracking

**System Metrics:**
- `active_streams_current` - Live streaming connections
- `cache_operations_total` - Cache hit/miss rates
- `errors_total` - Error tracking by type

### Structured Logging

Logs include contextual information:
- Request IDs for tracing
- User context and operations
- Performance metrics
- Business events

### Analytics Dashboard

User analytics include:
- Token usage over time
- Model preference analysis  
- Conversation patterns
- Cost tracking
- Feature adoption metrics

## 🔒 Security Features

- **JWT Authentication** with Supabase integration
- **Input Sanitization** with custom Pydantic validators
- **SQL Injection Prevention** in search queries
- **Rate Limiting** ready for implementation
- **Secure Headers** middleware
- **Request Tracing** for security auditing
- **CORS Configuration** with environment-specific origins
- **API Key Management** with scoping and expiration

## 🧪 Testing

```bash
# Run full test suite
pytest

# With coverage reporting
pytest --cov=app --cov-report=html

# Integration tests
pytest tests/test_integration.py -v

# Specific router tests
pytest tests/test_chat.py tests/test_conversations.py
```

## 🛠️ Development

### Code Standards

- **Type Safety**: Full type hints with mypy compliance
- **Async Design**: Non-blocking I/O throughout
- **Error Handling**: Comprehensive exception hierarchy
- **Testing**: Unit and integration test coverage
- **Documentation**: OpenAPI/Swagger with detailed schemas

### Adding Features

1. **Model Definition**: Add Pydantic models in `app/models/`
2. **Router Implementation**: Create endpoints in `app/routers/`
3. **Service Logic**: Implement in `app/services/`
4. **Testing**: Add comprehensive tests
5. **Documentation**: Update OpenAPI schemas

### Performance Optimization

- **Connection Pooling**: Configured for high concurrency
- **Caching Strategy**: Multi-layer with TTL management  
- **Streaming Optimization**: Efficient SSE implementation
- **Resource Management**: Proper cleanup and lifecycle management

## 🐛 Troubleshooting

### Common Issues

**Authentication (401 Errors):**
```bash
# Check JWT configuration
echo $JWT_SECRET_KEY | base64 -d

# Validate token format
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/users/me
```

**Edge Function Connectivity:**
```bash
# Test edge function directly
curl -X POST $EDGE_FUNCTION_URL/conversation-manager \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

**Redis Connection Issues:**
```bash
# Test Redis connectivity
redis-cli -u $REDIS_URL ping

# Check fallback behavior
REDIS_ENABLED=false uvicorn app.main:app
```

**Model Discovery Problems:**
```bash
# Test LiteLLM connection
curl $LITELLM_URL/models -H "Authorization: Bearer $LITELLM_MASTER_KEY"

# Refresh model cache
curl -X POST http://localhost:8000/v1/models/refresh \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Performance Debugging

Monitor key metrics:
- Response times via `/metrics`
- Cache hit rates in logs
- Connection pool utilization
- Memory usage patterns

### Log Analysis

```bash
# Filter by request ID
grep "req_12345" logs/app.log

# Monitor error patterns  
grep "ERROR" logs/app.log | tail -20

# Business metrics
grep "business_event" logs/app.log | jq .
```

## 🔄 Migration from v1.x

Key changes in v2.0:
- **New routing structure** with domain separation
- **Enhanced caching** with Redis integration
- **Improved error handling** with custom exceptions
- **Advanced conversation features** with branching
- **Comprehensive monitoring** with business metrics

Migration steps:
1. Update environment variables (see `.env.example`)
2. Update API client code for new endpoints
3. Test new caching behavior
4. Configure monitoring and alerts

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. **Fork** the repository
2. **Create** feature branch (`git checkout -b feature/amazing-feature`)
3. **Add** comprehensive tests
4. **Ensure** all tests pass (`pytest`)
5. **Submit** pull request with detailed description

## 📞 Support

- **Issues**: GitHub Issues with detailed reproduction steps  
- **Discussions**: GitHub Discussions for questions
- **Documentation**: Check `/docs` endpoint for API reference
- **Monitoring**: Use `/health` endpoint for diagnostics

---

**Built with ❤️ for the LLM ecosystem**

*Leveraging FastAPI, Supabase, LiteLLM, Redis, and Prometheus for production-scale AI applications.*