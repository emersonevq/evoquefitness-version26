#!/usr/bin/env python
"""
Migration script to ensure historico_status table has the correct structure.
This handles both:
1. Creating the table with new structure if it doesn't exist
2. Migrating old column names to new ones if needed
"""

from sqlalchemy import inspect
from core.db import engine

def migrate_historico_status():
    """Migrate historico_status table to new schema"""
    
    try:
        insp = inspect(engine)
        
        # Check if table exists
        if not insp.has_table("historico_status"):
            print("[migration] Table historico_status does not exist. Skipping migration.")
            return
        
        # Get existing columns
        existing_cols = {c.get("name"): c for c in insp.get_columns("historico_status")}
        existing_names = set(existing_cols.keys())
        
        # Expected new columns
        expected_cols = {
            "id", "chamado_id", "status", "data_inicio", "data_fim",
            "usuario_id", "descricao", "created_at", "updated_at"
        }
        
        # Check if we need to migrate (old schema has status_anterior/status_novo)
        has_old_schema = "status_anterior" in existing_names or "status_novo" in existing_names
        
        with engine.begin() as conn:
            if has_old_schema:
                print("[migration] Detected old schema. Migrating historico_status...")
                
                # Create temp table with new structure
                conn.exec_driver_sql("""
                    CREATE TABLE historico_status_new (
                        id INT NOT NULL AUTO_INCREMENT,
                        chamado_id INT NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        data_inicio DATETIME NULL,
                        data_fim DATETIME NULL,
                        usuario_id INT NULL,
                        descricao TEXT NULL,
                        created_at DATETIME NULL,
                        updated_at DATETIME NULL,
                        PRIMARY KEY (id),
                        KEY chamado_id (chamado_id),
                        KEY usuario_id (usuario_id),
                        KEY status (status),
                        CONSTRAINT historico_status_new_ibfk_1 FOREIGN KEY (chamado_id) 
                            REFERENCES chamado (id) ON DELETE CASCADE,
                        CONSTRAINT historico_status_new_ibfk_2 FOREIGN KEY (usuario_id) 
                            REFERENCES user (id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # Migrate data from old table to new table
                # Map old columns to new ones
                migrate_sql = """
                    INSERT INTO historico_status_new 
                    (chamado_id, status, data_inicio, usuario_id, descricao, created_at, updated_at)
                    SELECT 
                        chamado_id,
                        COALESCE(status_novo, 'Aberto'),
                        COALESCE(data_mudanca, NOW()),
                        usuario_id,
                        CONCAT(
                            COALESCE(status_anterior, 'Aberto'),
                            ' → ',
                            COALESCE(status_novo, 'Aberto'),
                            CASE WHEN motivo IS NOT NULL AND motivo != '' 
                                THEN CONCAT(' (', motivo, ')') 
                                ELSE '' 
                            END
                        ) as descricao,
                        data_mudanca,
                        data_mudanca
                    FROM historico_status
                """
                conn.exec_driver_sql(migrate_sql)
                print(f"[migration] Migrated data from old table")
                
                # Drop old table and rename new one
                conn.exec_driver_sql("DROP TABLE historico_status")
                conn.exec_driver_sql("RENAME TABLE historico_status_new TO historico_status")
                print("[migration] Table migration completed successfully")
            else:
                # Check for missing columns and add them
                missing_cols = expected_cols - existing_names
                
                if missing_cols:
                    print(f"[migration] Adding missing columns: {missing_cols}")
                    
                    col_defs = {
                        "status": "VARCHAR(50) NOT NULL",
                        "data_inicio": "DATETIME NULL",
                        "data_fim": "DATETIME NULL",
                        "descricao": "TEXT NULL",
                        "created_at": "DATETIME NULL",
                        "updated_at": "DATETIME NULL",
                    }
                    
                    for col in missing_cols:
                        if col in col_defs:
                            try:
                                conn.exec_driver_sql(
                                    f"ALTER TABLE historico_status ADD COLUMN {col} {col_defs[col]}"
                                )
                                print(f"[migration] Added column: {col}")
                            except Exception as e:
                                print(f"[migration] Error adding column {col}: {e}")
                
                # Ensure indices exist
                try:
                    conn.exec_driver_sql(
                        "CREATE INDEX IF NOT EXISTS idx_status ON historico_status (status)"
                    )
                    print("[migration] Ensured index on status column")
                except Exception:
                    pass
        
        print("[migration] historico_status migration completed")
        
    except Exception as e:
        print(f"[migration] Error during migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_historico_status()
    print("Migration finished successfully!")
