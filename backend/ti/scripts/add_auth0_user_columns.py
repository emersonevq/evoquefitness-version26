"""
Script para adicionar colunas 'email_verified' e 'auth0_id' à tabela 'user'
Executa: python -m ti.scripts.add_auth0_user_columns
"""
from sqlalchemy import text
from core.db import engine

def add_auth0_columns():
    """Adiciona colunas email_verified e auth0_id à tabela user"""
    with engine.connect() as connection:
        try:
            # Verifica se a coluna email_verified já existe
            result = connection.execute(
                text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'user' 
                    AND COLUMN_NAME = 'email_verified'
                """)
            )
            
            email_verified_exists = result.fetchone() is not None
            
            # Verifica se a coluna auth0_id já existe
            result = connection.execute(
                text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'user' 
                    AND COLUMN_NAME = 'auth0_id'
                """)
            )
            
            auth0_id_exists = result.fetchone() is not None
            
            # Adiciona coluna email_verified se não existe
            if not email_verified_exists:
                connection.execute(
                    text("""
                        ALTER TABLE user 
                        ADD COLUMN email_verified BOOLEAN DEFAULT FALSE 
                        AFTER bloqueado
                    """)
                )
                connection.commit()
                print("✅ Coluna 'email_verified' adicionada com sucesso!")
            else:
                print("✅ Coluna 'email_verified' já existe")
            
            # Adiciona coluna auth0_id se não existe
            if not auth0_id_exists:
                connection.execute(
                    text("""
                        ALTER TABLE user 
                        ADD COLUMN auth0_id VARCHAR(255) UNIQUE NULL 
                        AFTER email_verified
                    """)
                )
                connection.commit()
                print("✅ Coluna 'auth0_id' adicionada com sucesso!")
            else:
                print("✅ Coluna 'auth0_id' já existe")
            
        except Exception as e:
            print(f"❌ Erro ao adicionar colunas: {e}")
            raise

if __name__ == "__main__":
    add_auth0_columns()
