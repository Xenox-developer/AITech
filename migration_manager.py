"""
Database migration manager
"""
import sqlite3
import os
import importlib.util
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MigrationManager:
    def __init__(self, db_path='ai_study.db', migrations_dir='migrations'):
        self.db_path = db_path
        self.migrations_dir = Path(migrations_dir)
        self.init_migrations_table()
    
    def init_migrations_table(self):
        """Initialize migrations tracking table"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_applied_migrations(self):
        """Get list of applied migrations"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT migration_name FROM migrations ORDER BY migration_name')
        applied = [row[0] for row in c.fetchall()]
        
        conn.close()
        return applied
    
    def get_available_migrations(self):
        """Get list of available migration files"""
        if not self.migrations_dir.exists():
            return []
        
        migrations = []
        for file in self.migrations_dir.glob('*.py'):
            if file.name != '__init__.py':
                migrations.append(file.stem)
        
        return sorted(migrations)
    
    def get_pending_migrations(self):
        """Get list of migrations that need to be applied"""
        applied = set(self.get_applied_migrations())
        available = self.get_available_migrations()
        
        return [m for m in available if m not in applied]
    
    def load_migration(self, migration_name):
        """Load migration module"""
        migration_file = self.migrations_dir / f"{migration_name}.py"
        
        if not migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_file}")
        
        spec = importlib.util.spec_from_file_location(migration_name, migration_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    
    def apply_migration(self, migration_name):
        """Apply a single migration"""
        logger.info(f"Applying migration: {migration_name}")
        
        conn = sqlite3.connect(self.db_path)
        try:
            migration_module = self.load_migration(migration_name)
            
            # Apply the migration
            migration_module.up(conn)
            
            # Record that migration was applied
            c = conn.cursor()
            c.execute('INSERT INTO migrations (migration_name) VALUES (?)', (migration_name,))
            
            conn.commit()
            logger.info(f"Successfully applied migration: {migration_name}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to apply migration {migration_name}: {e}")
            raise
        finally:
            conn.close()
    
    def migrate(self):
        """Apply all pending migrations"""
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations")
            return
        
        logger.info(f"Applying {len(pending)} migrations: {pending}")
        
        for migration_name in pending:
            self.apply_migration(migration_name)
        
        logger.info("All migrations applied successfully")
    
    def status(self):
        """Show migration status"""
        applied = self.get_applied_migrations()
        available = self.get_available_migrations()
        pending = self.get_pending_migrations()
        
        print(f"Applied migrations ({len(applied)}):")
        for migration in applied:
            print(f"  ✓ {migration}")
        
        if pending:
            print(f"\nPending migrations ({len(pending)}):")
            for migration in pending:
                print(f"  ○ {migration}")
        else:
            print("\nNo pending migrations")

def run_migrations():
    """Run all pending migrations"""
    manager = MigrationManager()
    manager.migrate()

if __name__ == "__main__":
    import sys
    
    manager = MigrationManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "status":
            manager.status()
        elif command == "migrate":
            manager.migrate()
        else:
            print("Usage: python migration_manager.py [status|migrate]")
    else:
        manager.migrate()