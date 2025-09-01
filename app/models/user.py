"""User-related Pydantic models"""

from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class UserStatus(str, Enum):
    """User status enumeration"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    PENDING = "pending"


class UserProfile(BaseModel):
    """User profile model"""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    litellm_key: str = Field(..., description="User's LiteLLM API key")
    
    # Profile information
    display_name: Optional[str] = Field(None, description="Display name", max_length=100)
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    timezone: Optional[str] = Field(None, description="User timezone", max_length=50)
    language: str = Field("en", description="Preferred language", max_length=10)
    
    # Account status
    role: UserRole = Field(UserRole.USER, description="User role")
    status: UserStatus = Field(UserStatus.ACTIVE, description="User status")
    
    # Financial information
    spend: float = Field(0.0, ge=0, description="Total amount spent")
    max_budget: float = Field(0.0, ge=0, description="Maximum budget allowed")
    available_balance: Optional[float] = Field(None, ge=0, description="Available balance")
    
    # Preferences
    default_model: Optional[str] = Field(None, description="Default LLM model", max_length=100)
    default_temperature: float = Field(0.7, ge=0, le=2, description="Default temperature")
    default_max_tokens: int = Field(2000, gt=0, le=8192, description="Default max tokens")
    
    # Timestamps
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    
    # Additional data
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional user metadata")
    
    class Config:
        use_enum_values = True


class UserBalance(BaseModel):
    """User balance and financial information"""
    user_id: str = Field(..., description="User ID")
    current_balance: float = Field(..., ge=0, description="Current available balance")
    total_spent: float = Field(..., ge=0, description="Total amount spent")
    max_budget: float = Field(..., ge=0, description="Maximum budget")
    monthly_spent: float = Field(..., ge=0, description="Amount spent this month")
    monthly_budget: Optional[float] = Field(None, ge=0, description="Monthly budget limit")
    
    # Usage limits
    daily_limit: Optional[float] = Field(None, ge=0, description="Daily spending limit")
    daily_spent: float = Field(0.0, ge=0, description="Amount spent today")
    requests_today: int = Field(0, ge=0, description="API requests made today")
    daily_request_limit: Optional[int] = Field(None, ge=0, description="Daily request limit")
    
    # Status
    is_over_budget: bool = Field(False, description="Whether user is over budget")
    is_near_limit: bool = Field(False, description="Whether user is near spending limit")
    can_make_requests: bool = Field(True, description="Whether user can make new requests")
    
    # Timestamps
    last_updated: datetime = Field(..., description="Last balance update")
    last_transaction: Optional[datetime] = Field(None, description="Last transaction timestamp")


class UserUsage(BaseModel):
    """User usage statistics"""
    user_id: str = Field(..., description="User ID")
    
    # Overall statistics
    total_conversations: int = Field(0, ge=0, description="Total conversations created")
    total_messages: int = Field(0, ge=0, description="Total messages sent")
    total_tokens: int = Field(0, ge=0, description="Total tokens used")
    total_cost: float = Field(0.0, ge=0, description="Total cost incurred")
    
    # Current period (month)
    monthly_conversations: int = Field(0, ge=0, description="Conversations this month")
    monthly_messages: int = Field(0, ge=0, description="Messages this month")
    monthly_tokens: int = Field(0, ge=0, description="Tokens used this month")
    monthly_cost: float = Field(0.0, ge=0, description="Cost this month")
    
    # Model usage
    favorite_models: List[Dict[str, Any]] = Field(default_factory=list, description="Most used models")
    models_usage: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Detailed model usage")
    
    # Time-based analytics
    usage_by_hour: Dict[str, int] = Field(default_factory=dict, description="Usage by hour of day")
    usage_by_day: Dict[str, int] = Field(default_factory=dict, description="Usage by day of week")
    usage_by_month: Dict[str, int] = Field(default_factory=dict, description="Usage by month")
    
    # Performance metrics
    average_response_time: Optional[float] = Field(None, ge=0, description="Average response time")
    success_rate: float = Field(1.0, ge=0, le=1, description="Request success rate")
    
    # Timestamps
    period_start: datetime = Field(..., description="Current period start")
    period_end: datetime = Field(..., description="Current period end")
    last_updated: datetime = Field(..., description="Last statistics update")


class UpdateProfileRequest(BaseModel):
    """Update user profile request"""
    display_name: Optional[str] = Field(None, description="Display name", max_length=100)
    timezone: Optional[str] = Field(None, description="User timezone", max_length=50)
    language: Optional[str] = Field(None, description="Preferred language", max_length=10)
    
    # Preferences
    default_model: Optional[str] = Field(None, description="Default LLM model", max_length=100)
    default_temperature: Optional[float] = Field(None, ge=0, le=2, description="Default temperature")
    default_max_tokens: Optional[int] = Field(None, gt=0, le=8192, description="Default max tokens")
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional user metadata")
    
    @validator('display_name')
    def validate_display_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v
    
    @validator('default_model')
    def validate_model(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class UserSettings(BaseModel):
    """User settings and preferences"""
    user_id: str = Field(..., description="User ID")
    
    # Chat preferences
    auto_save_conversations: bool = Field(True, description="Auto-save conversations")
    default_model: Optional[str] = Field(None, description="Default model")
    default_temperature: float = Field(0.7, description="Default temperature")
    default_max_tokens: int = Field(2000, description="Default max tokens")
    
    # UI preferences
    theme: str = Field("light", description="UI theme")
    language: str = Field("en", description="Interface language")
    timezone: Optional[str] = Field(None, description="User timezone")
    
    # Privacy settings
    share_conversations: bool = Field(False, description="Allow sharing conversations")
    analytics_enabled: bool = Field(True, description="Enable usage analytics")
    
    # Notification settings
    email_notifications: bool = Field(True, description="Enable email notifications")
    low_balance_alerts: bool = Field(True, description="Alert on low balance")
    monthly_reports: bool = Field(False, description="Send monthly usage reports")
    
    # Advanced settings
    enable_streaming: bool = Field(True, description="Enable streaming responses")
    max_context_messages: int = Field(50, ge=1, le=200, description="Max context messages")
    custom_system_message: Optional[str] = Field(None, description="Custom system message", max_length=2000)
    
    # Updated timestamp
    updated_at: datetime = Field(..., description="Last update timestamp")


class UserActivity(BaseModel):
    """User activity log entry"""
    id: str = Field(..., description="Activity ID")
    user_id: str = Field(..., description="User ID")
    activity_type: str = Field(..., description="Activity type")
    description: str = Field(..., description="Activity description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional activity data")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    timestamp: datetime = Field(..., description="Activity timestamp")


class UserAnalytics(BaseModel):
    """User analytics and insights"""
    user_id: str = Field(..., description="User ID")
    
    # Engagement metrics
    total_sessions: int = Field(0, ge=0, description="Total chat sessions")
    average_session_length: float = Field(0.0, ge=0, description="Average session length (minutes)")
    messages_per_session: float = Field(0.0, ge=0, description="Average messages per session")
    
    # Quality metrics
    regeneration_rate: float = Field(0.0, ge=0, le=1, description="Message regeneration rate")
    conversation_completion_rate: float = Field(0.0, ge=0, le=1, description="Conversation completion rate")
    
    # Cost efficiency
    cost_per_message: float = Field(0.0, ge=0, description="Average cost per message")
    cost_per_token: float = Field(0.0, ge=0, description="Average cost per token")
    
    # Growth metrics
    usage_trend: str = Field("stable", description="Usage trend (growing/stable/declining)")
    monthly_growth_rate: float = Field(0.0, description="Monthly usage growth rate")
    
    # Timestamps
    period_start: datetime = Field(..., description="Analytics period start")
    period_end: datetime = Field(..., description="Analytics period end")
    generated_at: datetime = Field(..., description="Analytics generation timestamp")


# Additional models for users router
UserProfileUpdate = UpdateProfileRequest  # Alias for backward compatibility
UserPreferences = UserSettings  # Alias for backward compatibility  
UserUsageStats = UserUsage  # Alias for backward compatibility


class UserBalanceHistory(BaseModel):
    """User balance transaction history"""
    id: str = Field(..., description="Transaction ID")
    user_id: str = Field(..., description="User ID")
    transaction_type: str = Field(..., description="Transaction type")
    amount: float = Field(..., description="Transaction amount")
    balance_before: float = Field(..., description="Balance before transaction")
    balance_after: float = Field(..., description="Balance after transaction")
    description: Optional[str] = Field(None, description="Transaction description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional transaction data")
    created_at: datetime = Field(..., description="Transaction timestamp")


class UserApiKeyInfo(BaseModel):
    """User API key information"""
    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    key_prefix: str = Field(..., description="API key prefix (for display)")
    permissions: List[str] = Field(default_factory=list, description="API key permissions")
    is_active: bool = Field(True, description="Whether key is active")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateApiKeyRequest(BaseModel):
    """Create API key request"""
    name: str = Field(..., description="API key name", max_length=100)
    permissions: Optional[List[str]] = Field(None, description="API key permissions")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")


class UpdateApiKeyRequest(BaseModel):
    """Update API key request"""
    name: Optional[str] = Field(None, description="API key name", max_length=100)
    permissions: Optional[List[str]] = Field(None, description="API key permissions")
    is_active: Optional[bool] = Field(None, description="Whether key is active")