"""
Database migration script: SQLite to PostgreSQL
Migrates all data from SQLite database to PostgreSQL
"""

import sqlite3
import psycopg2
from psycopg2 import sql
import os
from typing import List, Tuple
from datetime import datetime

class DatabaseMigration:
    """Handles migration from SQLite to PostgreSQL"""
    
    def __init__(self, sqlite_path: str, postgres_url: str):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        
    def get_sqlite_tables(self) -> List[str]:
        """Get list of tables from SQLite database"""
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    
    def get_table_schema(self, table_name: str) -> List[Tuple]:
        """Get table schema from SQLite"""
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        schema = cursor.fetchall()
        conn.close()
        return schema
    
    def sqlite_to_postgres_type(self, sqlite_type: str) -> str:
        """Convert SQLite types to PostgreSQL types"""
        type_map = {
            'INTEGER': 'INTEGER',
            'TEXT': 'TEXT',
            'REAL': 'DOUBLE PRECISION',
            'BLOB': 'BYTEA',
            'NUMERIC': 'NUMERIC',
            'BOOLEAN': 'BOOLEAN',
            'DATETIME': 'TIMESTAMP',
            'DATE': 'DATE',
            'TIME': 'TIME'
        }
        return type_map.get(sqlite_type.upper(), 'TEXT')
    
    def create_postgres_tables(self, conn):
        """Create tables in PostgreSQL from SQLite schema"""
        tables = self.get_sqlite_tables()
        cursor = conn.cursor()
        
        for table in tables:
            schema = self.get_table_schema(table)
            
            # Build CREATE TABLE statement
            columns = []
            for col in schema:
                col_name = col[1]
                col_type = self.sqlite_to_postgres_type(col[2])
                not_null = 'NOT NULL' if col[3] else ''
                primary_key = 'PRIMARY KEY' if col[5] else ''
                
                columns.append(f"{col_name} {col_type} {not_null} {primary_key}".strip())
            
            create_stmt = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns)})"
            
            print(f"Creating table: {table}")
            cursor.execute(create_stmt)
        
        conn.commit()
    
    def migrate_data(self, conn):
        """Migrate data from SQLite to PostgreSQL"""
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = conn.cursor()
        
        tables = self.get_sqlite_tables()
        
        for table in tables:
            print(f"Migrating table: {table}")
            
            # Get all data from SQLite
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                print(f"  No data in {table}")
                continue
            
            # Get column names
            column_names = [desc[0] for desc in sqlite_cursor.description]
            
            # Insert into PostgreSQL
            placeholders = ','.join(['%s'] * len(column_names))
            insert_stmt = f"INSERT INTO {table} ({','.join(column_names)}) VALUES ({placeholders})"
            
            try:
                pg_cursor.executemany(insert_stmt, rows)
                conn.commit()
                print(f"  Migrated {len(rows)} rows")
            except Exception as e:
                print(f"  Error migrating {table}: {e}")
                conn.rollback()
        
        sqlite_conn.close()
    
    def run_migration(self):
        """Execute complete migration"""
        print(f"Starting migration from {self.sqlite_path} to PostgreSQL")
        print(f"Timestamp: {datetime.now()}")
        
        try:
            # Connect to PostgreSQL
            conn = psycopg2.connect(self.postgres_url)
            
            # Create tables
            print("\n=== Creating Tables ===")
            self.create_postgres_tables(conn)
            
            # Migrate data
            print("\n=== Migrating Data ===")
            self.migrate_data(conn)
            
            print("\n=== Migration Complete ===")
            conn.close()
            
        except Exception as e:
            print(f"\nMigration failed: {e}")
            raise

def main():
    """Run migration from command line"""
    sqlite_path = os.getenv('SQLITE_PATH', 'shift_maker.sqlite3')
    postgres_url = os.getenv('DATABASE_URL')
    
    if not postgres_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Example: postgresql://user:pass@localhost:5432/shiftplanner")
        return
    
    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite database not found: {sqlite_path}")
        return
    
    migration = DatabaseMigration(sqlite_path, postgres_url)
    migration.run_migration()

if __name__ == '__main__':
    main()
