#!/usr/bin/env python3
"""
Migration script to update users table schema
"""
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_users_table():
    """Migrate users table to new schema"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    try:
        # Check current schema
        c.execute("PRAGMA table_info(users);")
        current_columns = [row[1] for row in c.fetchall()]
        logger.info(f"Current columns: {current_columns}")
        
        # Create new users table with correct schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                subscription_type TEXT DEFAULT 'free',
                last_login TIMESTAMP,
                profile_image TEXT
            )
        ''')
        
        # Copy existing data if any
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        if user_count > 0:
            logger.info(f"Found {user_count} existing users, migrating data...")
            
            # Copy data from old table to new table
            c.execute('''
                INSERT INTO users_new (id, email, username, password_hash, created_at, is_active, subscription_type)
                SELECT 
                    id, 
                    email, 
                    COALESCE(email, 'user' || id) as username,  -- Use email as username or generate one
                    'temp_hash_' || id as password_hash,        -- Temporary password hash
                    created_at,
                    1 as is_active,
                    COALESCE(plan, 'free') as subscription_type
                FROM users
            ''')
            
            logger.info("Data migrated to new table")
        
        # Drop old table and rename new one
        c.execute("DROP TABLE users")
        c.execute("ALTER TABLE users_new RENAME TO users")
        
        logger.info("Users table migration completed successfully!")
        
        # Show final schema
        c.execute("PRAGMA table_info(users);")
        new_columns = [row[1] for row in c.fetchall()]
        logger.info(f"New columns: {new_columns}")
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_users_table()