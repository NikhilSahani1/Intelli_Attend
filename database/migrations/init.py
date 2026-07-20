"""
Database migrations package
Export migration modules and MigrationManager
"""
from database.migrations.migration_manager import MigrationManager

# Import migration modules for easy access
from database.migrations import migration_001_initial
from database.migrations import migration_002_add_ml_tables
from database.migrations import migration_003_add_verification_tables
from database.migrations import migration_004_add_audit_tables
from database.migrations import migration_005_add_face_encoding_tables

# List of all migration versions for reference
MIGRATIONS = [
    (1, '001_initial_schema.sql'),
    (2, '002_add_ml_tables.sql'),
    (3, '003_add_verification_tables.sql'),
    (4, '004_add_audit_tables.sql'),
    (5, '005_add_face_encoding_tables.sql'),
]

__all__ = [
    'MigrationManager',
    'migration_001_initial',
    'migration_002_add_ml_tables',
    'migration_003_add_verification_tables',
    'migration_004_add_audit_tables',
    'migration_005_add_face_encoding_tables',
    'MIGRATIONS'
]