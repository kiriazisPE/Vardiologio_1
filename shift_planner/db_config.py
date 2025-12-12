"""
PostgreSQL Database Configuration
Provides connection and migration utilities for PostgreSQL production database
"""

import os
from typing import Optional
from urllib.parse import urlparse

def get_database_url() -> str:
    """
    Get database URL from environment.
    Falls back to SQLite if PostgreSQL not configured.
    """
    db_url = os.getenv('DATABASE_URL')
    
    if db_url:
        # Parse and validate PostgreSQL URL
        parsed = urlparse(db_url)
        if parsed.scheme in ('postgres', 'postgresql'):
            return db_url
    
    # Fallback to SQLite for development
    sqlite_path = os.getenv('DB_PATH', 'shift_maker.sqlite3')
    return f'sqlite:///{sqlite_path}'

def get_connection_params() -> dict:
    """
    Get database connection parameters for asyncpg or psycopg2.
    """
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        return {'type': 'sqlite', 'path': os.getenv('DB_PATH', 'shift_maker.sqlite3')}
    
    parsed = urlparse(db_url)
    
    if parsed.scheme in ('postgres', 'postgresql'):
        return {
            'type': 'postgresql',
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password,
            'sslmode': os.getenv('DB_SSLMODE', 'prefer')
        }
    
    return {'type': 'sqlite', 'path': 'shift_maker.sqlite3'}

# Connection pool configuration
POOL_CONFIG = {
    'min_size': int(os.getenv('DB_POOL_MIN', '2')),
    'max_size': int(os.getenv('DB_POOL_MAX', '10')),
    'max_queries': int(os.getenv('DB_POOL_MAX_QUERIES', '50000')),
    'max_inactive_connection_lifetime': float(os.getenv('DB_POOL_MAX_LIFETIME', '300.0')),
}
