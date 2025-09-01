"""Prometheus metrics helpers and business metrics collection"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
import asyncio
from collections import defaultdict

from ..config import settings


class MetricsCollector:
    """Enhanced metrics collection for monitoring and analytics"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        
        # HTTP metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code', 'user_id'],
            registry=self.registry
        )
        
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        # Service metrics
        self.service_calls_total = Counter(
            'service_calls_total',
            'Total service calls',
            ['service', 'operation', 'status'],
            registry=self.registry
        )
        
        self.service_call_duration = Histogram(
            'service_call_duration_seconds',
            'Service call duration',
            ['service', 'operation'],
            registry=self.registry
        )
        
        # Chat metrics
        self.chat_completions_total = Counter(
            'chat_completions_total',
            'Total chat completions',
            ['model', 'user_id', 'status'],
            registry=self.registry
        )
        
        self.chat_tokens_total = Counter(
            'chat_tokens_total',
            'Total tokens processed',
            ['model', 'type'],  # type: input/output
            registry=self.registry
        )
        
        self.chat_completion_duration = Histogram(
            'chat_completion_duration_seconds',
            'Chat completion duration',
            ['model', 'stream'],
            registry=self.registry
        )
        
        self.active_streams = Gauge(
            'active_streams_current',
            'Currently active streaming connections',
            registry=self.registry
        )
        
        # Conversation metrics
        self.conversations_total = Counter(
            'conversations_total',
            'Total conversations',
            ['user_id', 'operation'],  # operation: created/updated/deleted
            registry=self.registry
        )
        
        self.messages_total = Counter(
            'messages_total',
            'Total messages',
            ['user_id', 'role', 'model'],  # role: user/assistant
            registry=self.registry
        )
        
        self.branches_total = Counter(
            'branches_total',
            'Total branches created',
            ['user_id', 'conversation_id'],
            registry=self.registry
        )
        
        # User metrics
        self.user_balance_changes = Counter(
            'user_balance_changes_total',
            'User balance changes',
            ['user_id', 'type'],  # type: charge/refund
            registry=self.registry
        )
        
        self.user_spending = Histogram(
            'user_spending_amount',
            'User spending amounts',
            ['user_id', 'model'],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_operations_total = Counter(
            'cache_operations_total',
            'Cache operations',
            ['operation', 'namespace', 'hit'],  # operation: get/set/delete
            registry=self.registry
        )
        
        self.cache_size = Gauge(
            'cache_size_bytes',
            'Cache size in bytes',
            ['namespace', 'backend'],  # backend: redis/memory
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'errors_total',
            'Total errors',
            ['error_type', 'service', 'endpoint'],
            registry=self.registry
        )
        
        # Business metrics
        self.revenue_total = Counter(
            'revenue_total_usd',
            'Total revenue in USD',
            ['model', 'user_tier'],
            registry=self.registry
        )
        
        # System metrics
        self.system_info = Info(
            'system_info',
            'System information',
            registry=self.registry
        )
        
        # Set system info
        self.system_info.info({
            'version': settings.version,
            'environment': settings.environment,
            'service': settings.app_name
        })
        
        # In-memory metrics for analytics
        self._daily_stats = defaultdict(lambda: defaultdict(int))
        self._user_sessions = {}
    
    # HTTP Metrics
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        user_id: Optional[str] = None
    ):
        """Record HTTP request metrics"""
        labels = {
            'method': method,
            'endpoint': endpoint,
            'status_code': str(status_code)
        }
        
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
            user_id=user_id or 'anonymous'
        ).inc()
        
        self.http_request_duration.labels(**labels).observe(duration)
    
    # Service Metrics
    def record_service_call(
        self,
        service: str,
        operation: str,
        duration: float,
        success: bool = True
    ):
        """Record service call metrics"""
        status = 'success' if success else 'error'
        
        self.service_calls_total.labels(
            service=service,
            operation=operation,
            status=status
        ).inc()
        
        self.service_call_duration.labels(
            service=service,
            operation=operation
        ).observe(duration)
    
    # Chat Metrics
    def record_chat_completion(
        self,
        model: str,
        user_id: str,
        duration: float,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        success: bool = True,
        streaming: bool = True
    ):
        """Record chat completion metrics"""
        status = 'success' if success else 'error'
        
        self.chat_completions_total.labels(
            model=model,
            user_id=user_id,
            status=status
        ).inc()
        
        self.chat_tokens_total.labels(
            model=model,
            type='input'
        ).inc(input_tokens)
        
        self.chat_tokens_total.labels(
            model=model,
            type='output'
        ).inc(output_tokens)
        
        self.chat_completion_duration.labels(
            model=model,
            stream=str(streaming).lower()
        ).observe(duration)
        
        if success:
            self.revenue_total.labels(
                model=model,
                user_tier='standard'  # Could be dynamic based on user
            ).inc(cost)
            
            # Record in daily stats
            today = datetime.now().date().isoformat()
            self._daily_stats[today]['total_requests'] += 1
            self._daily_stats[today]['total_tokens'] += input_tokens + output_tokens
            self._daily_stats[today]['total_revenue'] += cost
    
    def increment_active_streams(self):
        """Increment active streams counter"""
        self.active_streams.inc()
    
    def decrement_active_streams(self):
        """Decrement active streams counter"""
        self.active_streams.dec()
    
    # Conversation Metrics
    def record_conversation_operation(
        self,
        operation: str,  # created/updated/deleted
        user_id: str,
        conversation_id: Optional[str] = None
    ):
        """Record conversation operations"""
        self.conversations_total.labels(
            user_id=user_id,
            operation=operation
        ).inc()
        
        # Update daily stats
        today = datetime.now().date().isoformat()
        self._daily_stats[today][f'conversations_{operation}'] += 1
    
    def record_message(
        self,
        user_id: str,
        role: str,  # user/assistant
        model: Optional[str] = None
    ):
        """Record message creation"""
        self.messages_total.labels(
            user_id=user_id,
            role=role,
            model=model or 'unknown'
        ).inc()
        
        # Update daily stats
        today = datetime.now().date().isoformat()
        self._daily_stats[today][f'{role}_messages'] += 1
    
    def record_branch_creation(
        self,
        user_id: str,
        conversation_id: str
    ):
        """Record branch creation"""
        self.branches_total.labels(
            user_id=user_id,
            conversation_id=conversation_id
        ).inc()
        
        # Update daily stats
        today = datetime.now().date().isoformat()
        self._daily_stats[today]['branches_created'] += 1
    
    # User Metrics
    def record_balance_change(
        self,
        user_id: str,
        amount: float,
        change_type: str  # charge/refund
    ):
        """Record user balance changes"""
        self.user_balance_changes.labels(
            user_id=user_id,
            type=change_type
        ).inc()
        
        if change_type == 'charge':
            self.user_spending.labels(
                user_id=user_id,
                model='mixed'  # Could track per-model spending
            ).observe(amount)
    
    # Cache Metrics
    def record_cache_operation(
        self,
        operation: str,  # get/set/delete
        namespace: str,
        hit: bool,
        backend: str = 'redis'
    ):
        """Record cache operations"""
        self.cache_operations_total.labels(
            operation=operation,
            namespace=namespace,
            hit=str(hit).lower()
        ).inc()
    
    def update_cache_size(
        self,
        namespace: str,
        size_bytes: int,
        backend: str = 'redis'
    ):
        """Update cache size metrics"""
        self.cache_size.labels(
            namespace=namespace,
            backend=backend
        ).set(size_bytes)
    
    # Error Metrics
    def record_error(
        self,
        error_type: str,
        service: str,
        endpoint: Optional[str] = None
    ):
        """Record error occurrences"""
        self.errors_total.labels(
            error_type=error_type,
            service=service,
            endpoint=endpoint or 'unknown'
        ).inc()
        
        # Update daily stats
        today = datetime.now().date().isoformat()
        self._daily_stats[today]['total_errors'] += 1
        self._daily_stats[today][f'errors_{error_type.lower()}'] += 1
    
    # User Session Tracking
    def start_user_session(self, user_id: str):
        """Start tracking user session"""
        self._user_sessions[user_id] = datetime.now()
    
    def end_user_session(self, user_id: str) -> Optional[float]:
        """End user session and return duration"""
        if user_id in self._user_sessions:
            duration = (datetime.now() - self._user_sessions[user_id]).total_seconds()
            del self._user_sessions[user_id]
            return duration
        return None
    
    # Analytics Methods
    def get_daily_stats(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get daily statistics"""
        if date is None:
            date = datetime.now().date().isoformat()
        
        return dict(self._daily_stats.get(date, {}))
    
    def get_user_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get metrics for specific user (would typically come from database)"""
        # This is a simplified version - in production you'd query your metrics storage
        return {
            "active_session": user_id in self._user_sessions,
            "session_start": self._user_sessions.get(user_id),
            # Add more user-specific metrics here
        }
    
    def cleanup_old_stats(self, days_to_keep: int = 30):
        """Clean up old daily stats"""
        cutoff_date = datetime.now().date() - timedelta(days=days_to_keep)
        
        dates_to_remove = [
            date for date in self._daily_stats.keys()
            if datetime.fromisoformat(date).date() < cutoff_date
        ]
        
        for date in dates_to_remove:
            del self._daily_stats[date]


# Global metrics collector instance
metrics = MetricsCollector()


# Convenience functions
def record_request(method: str, endpoint: str, status_code: int, duration: float, user_id: Optional[str] = None):
    """Record HTTP request"""
    metrics.record_http_request(method, endpoint, status_code, duration, user_id)


def record_chat(model: str, user_id: str, duration: float, input_tokens: int, output_tokens: int, cost: float, success: bool = True):
    """Record chat completion"""
    metrics.record_chat_completion(model, user_id, duration, input_tokens, output_tokens, cost, success)


def record_error(error_type: str, service: str, endpoint: Optional[str] = None):
    """Record error"""
    metrics.record_error(error_type, service, endpoint)