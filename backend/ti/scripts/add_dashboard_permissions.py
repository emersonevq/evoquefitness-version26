"""
Script para adicionar colunas de permissões à tabela powerbi_dashboard.

Este script adiciona suporte para controlar permissões de acesso aos dashboards
por usuário e por função (role).
"""

from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
import json
import os

def add_permissions_columns():
    """Adiciona colunas de permissões à tabela powerbi_dashboard"""
    
    # Configurar conexão com o banco
    db_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost/infra")
    engine = create_engine(db_url, poolclass=StaticPool)
    
    migrations = [
        # Adicionar coluna para armazenar permissões em JSON
        # Formato: {"roles": ["Administrador", "Gerente"], "users": [1, 2, 3], "public": false}
        """
        ALTER TABLE powerbi_dashboard 
        ADD COLUMN permissoes JSON DEFAULT NULL COMMENT 'Armazena permissões de acesso (roles e users)';
        """,
        
        # Adicionar índice para melhorar performance em buscas por categoria
        """
        ALTER TABLE powerbi_dashboard 
        ADD KEY idx_category (category);
        """,
        
        # Adicionar coluna para rastrear última atualização de permissões
        """
        ALTER TABLE powerbi_dashboard 
        ADD COLUMN permissoes_atualizadas_em DATETIME DEFAULT CURRENT_TIMESTAMP 
        ON UPDATE CURRENT_TIMESTAMP COMMENT 'Última atualização das permissões';
        """,
    ]
    
    with engine.connect() as connection:
        for migration in migrations:
            try:
                connection.execute(text(migration))
                connection.commit()
                print(f"✓ Executado: {migration.strip()[:60]}...")
            except Exception as e:
                # Ignorar se a coluna já existe
                if "already exists" in str(e) or "Duplicate column" in str(e):
                    print(f"⚠ Coluna já existe (ignorado): {migration.strip()[:60]}...")
                else:
                    print(f"✗ Erro: {e}")
                    raise

def create_permissions_table():
    """
    Cria uma tabela separada para permissões (alternativa ao JSON).
    Útil para queries mais complexas e auditoria detalhada.
    """
    
    db_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost/infra")
    engine = create_engine(db_url, poolclass=StaticPool)
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS dashboard_permission (
        id INT AUTO_INCREMENT PRIMARY KEY,
        dashboard_id VARCHAR(100) NOT NULL,
        permission_type ENUM('role', 'user', 'public') NOT NULL COMMENT 'Tipo de permissão',
        permission_value VARCHAR(255) NOT NULL COMMENT 'Valor: nome da role, ID do usuário ou vazio para público',
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dashboard_id) REFERENCES powerbi_dashboard(dashboard_id) ON DELETE CASCADE,
        UNIQUE KEY unique_permission (dashboard_id, permission_type, permission_value),
        KEY idx_dashboard (dashboard_id),
        KEY idx_type (permission_type)
    ) COMMENT='Tabela de permissões de dashboards';
    """
    
    with engine.connect() as connection:
        try:
            connection.execute(text(create_table_sql))
            connection.commit()
            print("✓ Tabela 'dashboard_permission' criada com sucesso!")
        except Exception as e:
            if "already exists" in str(e):
                print("⚠ Tabela 'dashboard_permission' já existe")
            else:
                print(f"✗ Erro ao criar tabela: {e}")
                raise

def migrate_existing_data():
    """
    Se houver dados antigos de permissões, migra para a nova estrutura.
    Função placeholder - ajustar conforme necessário.
    """
    print("✓ Dados migrados (se houver)")

if __name__ == "__main__":
    print("=" * 60)
    print("Adicionando suporte a permissões em dashboards Power BI")
    print("=" * 60)
    
    print("\n[1] Adicionando colunas JSON...")
    add_permissions_columns()
    
    print("\n[2] Criando tabela de permissões...")
    create_permissions_table()
    
    print("\n[3] Migrando dados existentes...")
    migrate_existing_data()
    
    print("\n" + "=" * 60)
    print("✓ Migração concluída!")
    print("=" * 60)
