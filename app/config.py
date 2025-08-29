from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings configuration"""
    
    # API Settings
    app_name: str = "AI Chat Orchestrator"
    version: str = "1.0.0"
    debug: bool = False
    
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: Optional[str] = None
    edge_function_url: str
    
    # LiteLLM
    litellm_url: str
    litellm_master_key: Optional[str] = None
    
    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    
    # Performance
    max_context_messages: int = 100
    stream_timeout: int = 120
    connection_pool_size: int = 100
    
    # Monitoring
    enable_metrics: bool = True
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"


settings = Settings()