"""
Error Tracking and Monitoring Configuration
Integrates Sentry for error tracking and application monitoring
"""

import os
import streamlit as st
from typing import Optional
import logging

# Sentry configuration (lazy import to avoid dependency issues)
SENTRY_ENABLED = os.getenv('SENTRY_ENABLED', 'false').lower() == 'true'
SENTRY_DSN = os.getenv('SENTRY_DSN')
SENTRY_ENVIRONMENT = os.getenv('APP_ENV', 'development')
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1'))

def init_sentry():
    """
    Initialize Sentry error tracking.
    Only runs if SENTRY_ENABLED=true and SENTRY_DSN is set.
    """
    if not SENTRY_ENABLED or not SENTRY_DSN:
        logging.info("Sentry monitoring disabled")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        # Configure Sentry
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            
            # Enable performance monitoring
            enable_tracing=True,
            
            # Integrations
            integrations=[
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR
                ),
            ],
            
            # Release tracking
            release=os.getenv('VERSION', 'dev'),
            
            # Filter sensitive data
            before_send=filter_sensitive_data,
        )
        
        logging.info(f"Sentry initialized for environment: {SENTRY_ENVIRONMENT}")
        return True
        
    except ImportError:
        logging.warning("Sentry SDK not installed. Run: pip install sentry-sdk")
        return False
    except Exception as e:
        logging.error(f"Failed to initialize Sentry: {e}")
        return False

def filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending to Sentry.
    Removes API keys, passwords, and other secrets.
    """
    # Remove environment variables with sensitive data
    if 'server_name' in event:
        env = event.get('server_name', {})
        sensitive_keys = ['API_KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'DSN']
        
        for key in list(env.keys()):
            if any(sensitive in key.upper() for sensitive in sensitive_keys):
                env[key] = '[FILTERED]'
    
    # Filter request data
    if 'request' in event:
        request = event['request']
        if 'headers' in request:
            headers = request['headers']
            for key in ['Authorization', 'Cookie', 'X-API-Key']:
                if key in headers:
                    headers[key] = '[FILTERED]'
    
    return event

def capture_exception(exception: Exception, context: Optional[dict] = None):
    """
    Capture and report an exception to Sentry.
    
    Args:
        exception: The exception to capture
        context: Additional context data
    """
    if not SENTRY_ENABLED:
        logging.error(f"Exception: {exception}", exc_info=True)
        return
    
    try:
        import sentry_sdk
        
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, value)
                sentry_sdk.capture_exception(exception)
        else:
            sentry_sdk.capture_exception(exception)
            
    except ImportError:
        logging.error(f"Exception: {exception}", exc_info=True)

def capture_message(message: str, level: str = 'info', context: Optional[dict] = None):
    """
    Capture a message in Sentry.
    
    Args:
        message: Message to capture
        level: Severity level (info, warning, error, fatal)
        context: Additional context
    """
    if not SENTRY_ENABLED:
        log_method = getattr(logging, level.lower(), logging.info)
        log_method(message)
        return
    
    try:
        import sentry_sdk
        
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, value)
                sentry_sdk.capture_message(message, level=level)
        else:
            sentry_sdk.capture_message(message, level=level)
            
    except ImportError:
        log_method = getattr(logging, level.lower(), logging.info)
        log_method(message)

def set_user_context(user_id: Optional[str] = None, username: Optional[str] = None, email: Optional[str] = None):
    """
    Set user context for error tracking.
    
    Args:
        user_id: Unique user identifier
        username: Username
        email: User email
    """
    if not SENTRY_ENABLED:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.set_user({
            "id": user_id,
            "username": username,
            "email": email
        })
    except ImportError:
        pass

def add_breadcrumb(message: str, category: str = 'default', level: str = 'info', data: Optional[dict] = None):
    """
    Add a breadcrumb for debugging context.
    
    Args:
        message: Breadcrumb message
        category: Category (navigation, http, db, etc.)
        level: Severity level
        data: Additional data
    """
    if not SENTRY_ENABLED:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )
    except ImportError:
        pass

# Performance monitoring utilities
class transaction:
    """
    Context manager for Sentry performance transactions.
    
    Usage:
        with transaction('schedule_shift', op='task'):
            # Your code here
            pass
    """
    
    def __init__(self, name: str, op: str = 'task'):
        self.name = name
        self.op = op
        self.span = None
        
    def __enter__(self):
        if not SENTRY_ENABLED:
            return self
        
        try:
            import sentry_sdk
            self.span = sentry_sdk.start_transaction(name=self.name, op=self.op)
            self.span.__enter__()
        except ImportError:
            pass
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            self.span.__exit__(exc_type, exc_val, exc_tb)

# Example integration with Streamlit
def setup_streamlit_monitoring():
    """
    Set up monitoring for Streamlit session.
    Call this early in your Streamlit app.
    """
    if 'monitoring_initialized' not in st.session_state:
        init_sentry()
        st.session_state.monitoring_initialized = True
        
        # Set user context if authenticated
        if 'username' in st.session_state:
            set_user_context(
                username=st.session_state.get('username'),
                user_id=st.session_state.get('user_id')
            )
