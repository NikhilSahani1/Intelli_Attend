"""
Migration Manager for handling database migrations
"""
import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import sys

class MigrationManager:
    """Manages database migrations"""
    
    def __init__(self, db_path: str, migrations_dir: str = None):
        self.db_path = db_path
        self.migrations_dir = migrations_dir or os.path.join(os.path.dirname(__file__))
        self.logger = logging.getLogger(__name__)
        
        # Setup logging if not already configured
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, 
                              format='%(asctime)s - %(levelname)s - %(message)s')
    
    def get_current_version(self) -> int:
        """Get current database schema version"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if schema_version table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_version'
            """)
            
            if not cursor.fetchone():
                # Create schema_version table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                return 0
                
            cursor.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0
            
        except Exception as e:
            self.logger.error(f"Error getting current version: {e}")
            return 0
        finally:
            conn.close()
    
    def get_available_migrations(self) -> List[Tuple[int, str]]:
        """Get list of available migration files"""
        migrations = []
        
        if not os.path.exists(self.migrations_dir):
            return migrations
        
        for filename in sorted(os.listdir(self.migrations_dir)):
            if filename.endswith('.sql') and filename[0].isdigit():
                # Extract version from filename (e.g., 001_initial_schema.sql -> 1)
                try:
                    version = int(filename[:3])
                    migrations.append((version, filename))
                except ValueError:
                    continue
        
        return migrations
    
    def get_migration_details(self, version: int) -> Dict:
        """Get details about a specific migration"""
        migrations = self.get_available_migrations()
        for v, filename in migrations:
            if v == version:
                # Parse migration details from filename
                parts = filename[4:-4].split('_')
                name = ' '.join(parts).title()
                
                return {
                    'version': version,
                    'filename': filename,
                    'name': name,
                    'path': os.path.join(self.migrations_dir, filename),
                    'applied': version <= self.get_current_version()
                }
        return None
    
    def migrate(self, target_version: int = None) -> bool:
        """Run migrations up to target version"""
        current = self.get_current_version()
        migrations = self.get_available_migrations()
        
        if target_version is None:
            target_version = max([v for v, _ in migrations]) if migrations else current
        
        if current >= target_version:
            self.logger.info(f"Database already at version {current}")
            return True
        
        self.logger.info(f"Migrating from version {current} to {target_version}")
        
        conn = sqlite3.connect(self.db_path)
        conn.executescript("PRAGMA foreign_keys = OFF;")
        
        try:
            for version, filename in migrations:
                if version > current and version <= target_version:
                    self.logger.info(f"Applying migration: {filename}")
                    
                    with open(os.path.join(self.migrations_dir, filename), 'r') as f:
                        sql = f.read()
                    
                    # Execute migration
                    conn.executescript(sql)
                    
                    # Record migration
                    conn.execute(
                        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                        (version,)
                    )
                    
                    self.logger.info(f"Applied migration {filename}")
            
            conn.commit()
            self.logger.info(f"Migration to version {target_version} completed")
            return True
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Migration failed: {e}")
            return False
        finally:
            conn.executescript("PRAGMA foreign_keys = ON;")
            conn.close()
    
    def migrate_all(self) -> bool:
        """Run all pending migrations"""
        return self.migrate()
    
    def create_migration(self, name: str, description: str = "") -> str:
        """Create a new migration file"""
        migrations = self.get_available_migrations()
        next_version = max([v for v, _ in migrations]) + 1 if migrations else 1
        
        # Convert name to snake_case for filename
        import re
        snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        snake_name = re.sub(r'[^a-z0-9]+', '_', snake_name).strip('_')
        
        filename = f"{next_version:03d}_{snake_name}.sql"
        filepath = os.path.join(self.migrations_dir, filename)
        
        template = f"""-- Migration {next_version:03d}: {name}
-- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- Description: {description}

-- Write your migration SQL here
-- Example:
-- ALTER TABLE users ADD COLUMN new_column TEXT;

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES ({next_version});
"""
        
        with open(filepath, 'w') as f:
            f.write(template)
        
        self.logger.info(f"Created migration: {filename}")
        return filepath
    
    def get_migration_status(self) -> List[Dict]:
        """Get status of all migrations"""
        current = self.get_current_version()
        migrations = self.get_available_migrations()
        
        status = []
        for version, filename in migrations:
            # Parse migration name from filename
            name_part = filename[4:-4].replace('_', ' ').title()
            
            status.append({
                'version': version,
                'filename': filename,
                'name': name_part,
                'applied': version <= current,
                'path': os.path.join(self.migrations_dir, filename),
                'applied_at': self._get_applied_time(version) if version <= current else None
            })
        
        return status
    
    def _get_applied_time(self, version: int) -> Optional[str]:
        """Get when a migration was applied"""
        try:
            conn = sqlite3.connect(self.db_path)
            result = conn.execute(
                "SELECT applied_at FROM schema_version WHERE version = ?",
                (version,)
            ).fetchone()
            return result[0] if result else None
        except:
            return None
        finally:
            conn.close()
    
    def rollback(self, steps: int = 1) -> bool:
        """Rollback the last migration steps"""
        current = self.get_current_version()
        target = max(0, current - steps)
        
        if target >= current:
            self.logger.info("No migrations to rollback")
            return True
        
        self.logger.info(f"Rolling back from version {current} to {target}")
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Note: This is a simplified rollback
            # For proper rollback, you need down() methods in migrations
            conn.execute("DELETE FROM schema_version WHERE version > ?", (target,))
            conn.commit()
            
            self.logger.info(f"Rolled back to version {target}")
            return True
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Rollback failed: {e}")
            return False
        finally:
            conn.close()
    
    def get_pending_migrations(self) -> List[Dict]:
        """Get list of pending migrations"""
        current = self.get_current_version()
        all_migrations = self.get_migration_status()
        return [m for m in all_migrations if not m['applied']]
    
    def get_applied_migrations(self) -> List[Dict]:
        """Get list of applied migrations"""
        current = self.get_current_version()
        all_migrations = self.get_migration_status()
        return [m for m in all_migrations if m['applied']]
    
    def validate_migrations(self) -> bool:
        """Validate that migrations are in order and no gaps"""
        migrations = self.get_available_migrations()
        versions = [v for v, _ in migrations]
        
        # Check for gaps
        expected = list(range(1, len(versions) + 1))
        if versions != expected:
            self.logger.error(f"Migration versions have gaps: {versions} vs expected {expected}")
            return False
        
        return True
    
    def get_schema_sql(self) -> str:
        """Get current schema as SQL"""
        conn = sqlite3.connect(self.db_path)
        schema = []
        
        # Get all tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        
        for table in tables:
            # Get CREATE statement
            create_sql = conn.execute(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table[0]}'"
            ).fetchone()
            if create_sql and create_sql[0]:
                schema.append(create_sql[0] + ';')
        
        conn.close()
        return '\n\n'.join(schema)

    # ============================================================
    # Face Enrollment Columns Migration Methods
    # ============================================================
    
    def ensure_schema_version_table(self):
        """Ensure schema_version table exists"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()
    
    def add_face_enrollment_columns(self):
        """Specifically add face enrollment columns to users table"""
        self.logger.info("=" * 60)
        self.logger.info("🔷 Adding face enrollment columns to users table...")
        self.logger.info("=" * 60)
        
        # Ensure schema_version table exists
        self.ensure_schema_version_table()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if users table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                self.logger.error("❌ Users table doesn't exist!")
                return False
            
            # Get current columns
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            self.logger.info(f"📊 Current columns in users table: {columns}")
            
            changes_made = False
            migrations = []
            
            # Check and add role column if missing
            if 'role' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
                self.logger.info("✅ Added 'role' column")
                changes_made = True
                migrations.append("Added role column")
            else:
                self.logger.info("⏭️ 'role' column already exists")
            
            # Check and add verified column if missing
            if 'verified' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
                self.logger.info("✅ Added 'verified' column")
                changes_made = True
                migrations.append("Added verified column")
            else:
                self.logger.info("⏭️ 'verified' column already exists")
            
            # Check and add face_enrolled column if missing
            if 'face_enrolled' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN face_enrolled INTEGER DEFAULT 0")
                self.logger.info("✅ Added 'face_enrolled' column")
                changes_made = True
                migrations.append("Added face_enrolled column")
            else:
                self.logger.info("⏭️ 'face_enrolled' column already exists")
            
            # Check and add face_image_path column if missing
            if 'face_image_path' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN face_image_path TEXT")
                self.logger.info("✅ Added 'face_image_path' column")
                changes_made = True
                migrations.append("Added face_image_path column")
            else:
                self.logger.info("⏭️ 'face_image_path' column already exists")
            
            # Check and add updated_at column if missing
            if 'updated_at' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                self.logger.info("✅ Added 'updated_at' column")
                changes_made = True
                migrations.append("Added updated_at column")
            else:
                self.logger.info("⏭️ 'updated_at' column already exists")
            
            # Check and add phone_number column if missing
            if 'phone_number' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
                self.logger.info("✅ Added 'phone_number' column")
                changes_made = True
                migrations.append("Added phone_number column")
            else:
                self.logger.info("⏭️ 'phone_number' column already exists")
            
            # Check events table for time column
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(events)")
                event_columns = [column[1] for column in cursor.fetchall()]
                
                if 'time' not in event_columns:
                    cursor.execute("ALTER TABLE events ADD COLUMN time TIME")
                    self.logger.info("✅ Added 'time' column to events table")
                    changes_made = True
                    migrations.append("Added time column to events table")
                else:
                    self.logger.info("⏭️ 'time' column already exists in events table")
            
            if changes_made:
                conn.commit()
                self.logger.info("✅" + "=" * 58)
                self.logger.info("✅ Face enrollment columns added successfully!")
                self.logger.info("✅" + "=" * 58)
                
                # Verify the changes
                cursor.execute("PRAGMA table_info(users)")
                updated_columns = [column[1] for column in cursor.fetchall()]
                self.logger.info(f"📊 Updated columns: {updated_columns}")
                
                # Record this as a migration (version 6)
                try:
                    current_version = self.get_current_version()
                    new_version = max(6, current_version + 1)
                    
                    cursor.execute(
                        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                        (new_version,)
                    )
                    conn.commit()
                    self.logger.info(f"✅ Recorded migration version {new_version}")
                    self.logger.info(f"📝 Migrations applied: {', '.join(migrations)}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not record migration version: {e}")
            else:
                self.logger.info("✅" + "=" * 58)
                self.logger.info("✅ No changes needed - all columns already exist")
                self.logger.info("✅" + "=" * 58)
            
            return True
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"❌ Error adding columns: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            conn.close()
    
    @staticmethod
    def run_face_migration(db_path=None):
        """Static method to run face enrollment migration from command line"""
        print("\n" + "=" * 60)
        print("🔷 Face Enrollment Migration Tool 🔷")
        print("=" * 60)
        
        if db_path is None:
            # Try to find the database
            possible_paths = [
                # Absolute paths based on common project structures
                os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'event_system.db'),
                os.path.join(os.path.dirname(__file__), '..', 'event_system.db'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                            'database', 'event_system.db'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                            'backend', 'database', 'event_system.db'),
                # Current working directory paths
                os.path.join(os.getcwd(), 'database', 'event_system.db'),
                os.path.join(os.getcwd(), 'event_system.db'),
                # Project root paths
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                            'event_system.db')
            ]
            
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    db_path = abs_path
                    print(f"✅ Found database at: {db_path}")
                    break
            
            if db_path is None:
                print("❌ Could not find database file!")
                print("\n📁 Searched in:")
                for path in possible_paths:
                    print(f"   - {os.path.abspath(path)}")
                
                # Ask user for path
                print("\n📝 Please enter the path to your database file:")
                user_path = input("Database path: ").strip()
                if user_path and os.path.exists(user_path):
                    db_path = user_path
                    print(f"✅ Using database: {db_path}")
                else:
                    print("❌ Invalid database path!")
                    return False
        
        print(f"\n📁 Using database: {db_path}")
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        
        manager = MigrationManager(db_path)
        return manager.add_face_enrollment_columns()


# ============================================================
# Command Line Interface
# ============================================================

def print_menu():
    """Print the migration menu"""
    print("\n" + "=" * 60)
    print("🔷 Database Migration Tool 🔷")
    print("=" * 60)
    print("1. Run all pending migrations")
    print("2. Run face enrollment migration ONLY")
    print("3. Check migration status")
    print("4. Create new migration")
    print("5. Validate migrations")
    print("6. Show database schema")
    print("7. Exit")
    print("=" * 60)

if __name__ == "__main__":
    
    # Parse command line arguments for non-interactive mode
    if len(sys.argv) > 1:
        command = sys.argv[1]
        db_path_arg = sys.argv[2] if len(sys.argv) > 2 else None
        
        if command == "face":
            # Run face migration
            success = MigrationManager.run_face_migration(db_path_arg)
            sys.exit(0 if success else 1)
        
        elif command == "status":
            # Show migration status
            if not db_path_arg:
                print("❌ Please provide database path")
                sys.exit(1)
            
            if not os.path.exists(db_path_arg):
                print(f"❌ Database not found: {db_path_arg}")
                sys.exit(1)
                
            manager = MigrationManager(db_path_arg)
            status = manager.get_migration_status()
            current = manager.get_current_version()
            
            print("\n" + "=" * 60)
            print(f"📊 Migration Status (Current version: {current})")
            print("=" * 60)
            
            for m in status:
                status_icon = "✅" if m['applied'] else "⏳"
                applied_info = f" (at: {m['applied_at']})" if m['applied_at'] else ""
                print(f"  {status_icon} Version {m['version']:03d}: {m['name']}{applied_info}")
            
            print("=" * 60)
            sys.exit(0)
    
    # Interactive mode
    # Find database for interactive mode
    db_path = None
    possible_paths = [
        os.path.join('database', 'event_system.db'),
        'event_system.db',
        os.path.join('..', 'database', 'event_system.db'),
        os.path.join(os.getcwd(), 'database', 'event_system.db')
    ]
    
    print("\n🔍 Looking for database...")
    for path in possible_paths:
        if os.path.exists(path):
            db_path = os.path.abspath(path)
            print(f"✅ Found database: {db_path}")
            break
    
    if not db_path:
        print("❌ Database not found in common locations.")
        db_path = input("\n📁 Enter database path: ").strip()
        if not db_path or not os.path.exists(db_path):
            print("❌ Invalid database path!")
            sys.exit(1)
    
    manager = MigrationManager(db_path)
    
    while True:
        print_menu()
        choice = input("\nSelect option (1-7): ").strip()
        
        if choice == "1":
            print("\n🔄 Running all pending migrations...")
            success = manager.migrate_all()
            if success:
                print("✅ All migrations completed successfully!")
            else:
                print("❌ Migrations failed!")
        
        elif choice == "2":
            print("\n🔄 Running face enrollment migration...")
            success = manager.add_face_enrollment_columns()
            if success:
                print("✅ Face enrollment migration completed!")
            else:
                print("❌ Face enrollment migration failed!")
        
        elif choice == "3":
            status = manager.get_migration_status()
            current = manager.get_current_version()
            
            print("\n" + "=" * 60)
            print(f"📊 Migration Status (Current version: {current})")
            print("=" * 60)
            
            if not status:
                print("  No migrations found")
            else:
                for m in status:
                    status_icon = "✅" if m['applied'] else "⏳"
                    applied_info = f" (at: {m['applied_at']})" if m['applied_at'] else ""
                    print(f"  {status_icon} Version {m['version']:03d}: {m['name']}{applied_info}")
            
            print("=" * 60)
        
        elif choice == "4":
            name = input("Enter migration name: ").strip()
            desc = input("Enter description (optional): ").strip()
            if name:
                filepath = manager.create_migration(name, desc)
                print(f"✅ Created migration: {filepath}")
            else:
                print("❌ Migration name required!")
        
        elif choice == "5":
            valid = manager.validate_migrations()
            if valid:
                print("✅ Migrations are valid!")
            else:
                print("❌ Migration validation failed!")
        
        elif choice == "6":
            schema = manager.get_schema_sql()
            print("\n📊 Database Schema:")
            print("-" * 60)
            print(schema)
            print("-" * 60)
        
        elif choice == "7":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option! Please select 1-7")
        
        input("\nPress Enter to continue...")