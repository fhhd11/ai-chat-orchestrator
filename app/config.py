from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Enhanced application settings configuration with comprehensive options"""
    
    # API Settings
    app_name: str = "AI Chat Orchestrator"
    version: str = "2.0.0"
    debug: bool = False
    environment: str = "production"  # development, staging, production
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # Supabase Configuration
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: Optional[str] = None
    edge_function_url: str
    
    # LiteLLM Configuration
    litellm_url: str
    litellm_master_key: Optional[str] = None
    litellm_timeout: int = 120
    litellm_max_retries: int = 3
    
    # Redis Configuration (for caching)
    redis_url: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_enabled: bool = False
    
    # Cache Settings
    cache_ttl_models: int = 3600  # 1 hour
    cache_ttl_user_profile: int = 900  # 15 minutes
    cache_ttl_conversations: int = 300  # 5 minutes
    
    # Security Settings
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    
    # CORS Settings
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    cors_credentials: bool = True
    
    # Rate Limiting
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 10
    
    # Performance Settings
    max_context_messages: int = 100
    stream_timeout: int = 120
    connection_pool_size: int = 100
    max_concurrent_requests: int = 50
    request_timeout: int = 30
    keepalive_timeout: int = 65
    
    # Monitoring & Observability
    enable_metrics: bool = True
    metrics_port: int = 9090
    log_level: str = "INFO"
    structured_logging: bool = True
    log_requests: bool = True
    log_responses: bool = False  # Only for debugging
    
    # Health Check Settings
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5  # seconds
    
    # Feature Flags
    enable_swagger: bool = True
    enable_redoc: bool = True
    enable_openapi: bool = True
    enable_streaming: bool = True
    enable_regeneration: bool = True
    enable_branching: bool = True
    enable_search: bool = True
    enable_batch_operations: bool = True
    enable_analytics: bool = True
    
    # File Storage (for exports, logs, etc.)
    storage_path: str = "./storage"
    logs_path: str = "./logs"
    exports_path: str = "./exports"
    temp_path: str = "./temp"
    
    # API Limits
    max_conversations_per_user: int = 1000
    max_messages_per_conversation: int = 1000
    max_branches_per_conversation: int = 10
    max_export_conversations: int = 20
    max_batch_operation_size: int = 50
    
    # Pagination Defaults
    default_page_size: int = 20
    max_page_size: int = 100
    
    # Content Limits
    max_message_length: int = 32000
    max_conversation_title_length: int = 200
    max_branch_name_length: int = 100
    max_search_query_length: int = 200
    
    # External Service URLs (for documentation)
    frontend_url: Optional[str] = None
    docs_url: Optional[str] = None
    support_url: Optional[str] = None
    
    # Development Settings
    reload: bool = False
    access_log: bool = True
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development" or self.debug
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"
    
    @property
    def redis_connection_string(self) -> Optional[str]:
        """Get Redis connection string"""
        if self.redis_url:
            return self.redis_url
        
        if not self.redis_enabled:
            return None
            
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def log_config(self) -> dict:
        """Get logging configuration"""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "structured": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "formatter": "structured" if self.structured_logging else "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": self.log_level,
                "handlers": ["default"],
            },
        }
    
    def create_directories(self):
        """Create necessary directories"""
        directories = [
            self.storage_path,
            self.logs_path,
            self.exports_path,
            self.temp_path
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
        # Environment variable prefixes
        env_prefix = ""  # No prefix for backward compatibility
        
        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            return (
                init_settings,
                env_settings,
                file_secret_settings,
            )


# Global settings instance
settings = Settings()

# Create directories on import
if not settings.is_development:
    settings.create_directories()