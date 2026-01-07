"""
Script para migrar a tabela alert e adicionar colunas de imagem.
Execute manualmente se precisar adicionar as colunas à tabela existente.

python -m ti.scripts.migrate_alert_image
"""

from sqlalchemy import inspect, text
from core.db import engine
import sys

def migrate_alert_image():
    """Adiciona colunas de imagem à tabela alert se não existirem."""
    
    with engine.connect() as conn:
        inspector = inspect(engine)
        
        # Verificar se a tabela existe
        tables = inspector.get_table_names()
        if 'alert' not in tables:
            print("[MIGRATE] Tabela 'alert' não existe. Abortando.")
            return False
        
        # Verificar colunas existentes
        columns = [col['name'] for col in inspector.get_columns('alert')]
        print(f"[MIGRATE] Colunas atuais em 'alert': {columns}")
        
        # Adicionar coluna imagem_blob se não existir
        if 'imagem_blob' not in columns:
            print("[MIGRATE] Adicionando coluna 'imagem_blob'...")
            try:
                conn.execute(text(
                    "ALTER TABLE alert ADD COLUMN imagem_blob LONGBLOB NULL"
                ))
                conn.commit()
                print("[MIGRATE] Coluna 'imagem_blob' adicionada com sucesso.")
            except Exception as e:
                print(f"[MIGRATE] Erro ao adicionar coluna 'imagem_blob': {e}")
                conn.rollback()
        else:
            print("[MIGRATE] Coluna 'imagem_blob' já existe.")
        
        # Adicionar coluna imagem_mime_type se não existir
        if 'imagem_mime_type' not in columns:
            print("[MIGRATE] Adicionando coluna 'imagem_mime_type'...")
            try:
                conn.execute(text(
                    "ALTER TABLE alert ADD COLUMN imagem_mime_type VARCHAR(100) NULL"
                ))
                conn.commit()
                print("[MIGRATE] Coluna 'imagem_mime_type' adicionada com sucesso.")
            except Exception as e:
                print(f"[MIGRATE] Erro ao adicionar coluna 'imagem_mime_type': {e}")
                conn.rollback()
        else:
            print("[MIGRATE] Coluna 'imagem_mime_type' já existe.")
    
    print("[MIGRATE] Migração concluída!")
    return True

if __name__ == "__main__":
    success = migrate_alert_image()
    sys.exit(0 if success else 1)
