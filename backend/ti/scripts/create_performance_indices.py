"""
Script para criar índices de performance nas tabelas principais.
Esses índices melhoram a velocidade das queries de métricas e SLA.
"""
from sqlalchemy import text, inspect
from core.db import engine

INDICES = [
    ("idx_chamado_status", "chamado", ["status"]),
    ("idx_chamado_data_abertura", "chamado", ["data_abertura"]),
    ("idx_chamado_prioridade", "chamado", ["prioridade"]),
    ("idx_chamado_status_data", "chamado", ["status", "data_abertura"]),
    ("idx_chamado_data_conclusao", "chamado", ["data_conclusao"]),
    ("idx_chamado_primeira_resposta", "chamado", ["data_primeira_resposta"]),
    ("idx_historico_chamado_created", "historico_status", ["chamado_id", "created_at"]),
    ("idx_historico_status", "historico_status", ["status", "created_at"]),
    ("idx_sla_config_prioridade", "sla_configuration", ["prioridade"]),
    ("idx_sla_config_ativo", "sla_configuration", ["ativo"]),
]

def create_indices():
    """Cria índices se não existirem"""
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        for index_name, table_name, columns in INDICES:
            try:
                # Verifica se a tabela existe
                if not inspector.has_table(table_name):
                    print(f"⚠️  Tabela '{table_name}' não existe, pulando índice '{index_name}'")
                    continue
                
                # Verifica se o índice já existe
                existing_indices = {idx['name'] for idx in inspector.get_indexes(table_name)}
                
                if index_name in existing_indices:
                    print(f"✓ Índice '{index_name}' já existe em '{table_name}'")
                    continue
                
                # Cria o índice
                columns_str = ", ".join(columns)
                sql = f"CREATE INDEX {index_name} ON {table_name} ({columns_str});"
                
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ Índice '{index_name}' criado em '{table_name}'")
                
            except Exception as e:
                print(f"❌ Erro ao criar índice '{index_name}': {e}")
                try:
                    conn.rollback()
                except:
                    pass

if __name__ == "__main__":
    print("🔧 Criando índices de performance...")
    print("-" * 60)
    create_indices()
    print("-" * 60)
    print("✅ Processo concluído!")
