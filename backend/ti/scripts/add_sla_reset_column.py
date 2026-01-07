"""
Script para adicionar coluna 'ultimo_reset_em' à tabela 'sla_configuration'
Executa: python -m ti.scripts.add_sla_reset_column
"""
from sqlalchemy import text
from core.db import engine

def add_reset_column():
    """Adiciona coluna último_reset_em à tabela sla_configuration"""
    with engine.connect() as connection:
        try:
            # Verifica se a coluna já existe
            result = connection.execute(
                text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'sla_configuration' 
                    AND COLUMN_NAME = 'ultimo_reset_em'
                """)
            )
            
            if result.fetchone():
                print("✅ Coluna 'ultimo_reset_em' já existe")
                return
            
            # Adiciona a coluna
            connection.execute(
                text("""
                    ALTER TABLE sla_configuration 
                    ADD COLUMN ultimo_reset_em DATETIME NULL AFTER atualizado_em
                """)
            )
            connection.commit()
            print("✅ Coluna 'ultimo_reset_em' adicionada com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao adicionar coluna: {e}")
            raise

if __name__ == "__main__":
    add_reset_column()
