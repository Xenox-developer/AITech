#!/usr/bin/env python3
"""
Migration script to update users table schema
"""
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_users_table():
    """Migrate users table to match auth.py expectations"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    try:
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
        
        # Rename 'plan' column to 'subscription_type' if it exists
        if 'plan' in columns and 'subscription_type' not in columns:
            # SQLite doesn't support renaming columns directly, so we need to copy data
            c.execute("UPDATE users SET subscription_type = plan WHERE subscription_type IS NULL OR subscription_type = ''")
            logger.info("Copied plan data to subscription_type")
        
        conn.commit()
        logger.info("Migration completed successfully")
        
        # Show final schema
        c.execute("PRAGMA table_info(users)")
        final_columns = [f"{row[1]} ({row[2]})" for row in c.fetchall()]
        logger.info(f"Final schema: {final_columns}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_users_table()