"""
Migration 001: Add missing columns to users table
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Apply migration"""
    c = conn.cursor()
    
    # Check current schema
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    logger.info(f"Current columns: {columns}")
    
    # Add missing columns if they don't exist
    missing_columns = {
        'username': 'TEXT NOT NULL DEFAULT ""',
        'password_hash': 'TEXT NOT NULL DEFAULT ""',
        'is_active': 'BOOLEAN DEFAULT TRUE',
        'subscription_type': 'TEXT DEFAULT "free"',
        'last_login': 'TIMESTAMP',
        'profile_image': 'TEXT'
    }
    
    for column, definition in missing_columns.items():
        if column not in columns:
            try:
                c.execute(f'ALTER TABLE users ADD COLUMN {column} {definition}')
                logger.info(f"Added column: {column}")
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not add column {column}: {e}")
    
    # Update existing users to have default usernames based on email
    c.execute("UPDATE users SET username = SUBSTR(email, 1, INSTR(email, '@') - 1) WHERE username = '' OR username IS NULL")
    updated_rows = c.rowcount
    if updated_rows > 0:
        logger.info(f"Updated {updated_rows} users with default usernames")
    
    # Copy plan data to subscription_type if needed
    if 'plan' in columns:
        c.execute("UPDATE users SET subscription_type = plan WHERE subscription_type IS NULL OR subscription_type = ''")
        logger.info("Copied plan data to subscription_type")

def down(conn):
    """Rollback migration (not implemented for ALTER TABLE ADD COLUMN)"""
    logger.warning("Rollback not supported for this migration")
    pass