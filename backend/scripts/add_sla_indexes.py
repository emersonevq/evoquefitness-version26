"""
Script para adicionar índices críticos para performance de SLA.

Uso:
    python -m scripts.add_sla_indexes

Os índices criados:
- chamado_data_abertura: Acelera buscas por período
- chamado_status_idx: Acelera buscas por status
- chamado_prioridade_idx: Acelera buscas por prioridade
- chamado_composite_sla: Índice composto para a query principal de SLA
- historico_status_chamado_id: Acelera buscas de histórico
- chamado_data_conclusao_idx: Acelera buscas por conclusão
"""

from sqlalchemy import text, inspect
from core.db import engine, SessionLocal
import sys


def index_exists(connection, table_name: str, index_name: str) -> bool:
    """Verifica se um índice já existe"""
    try:
        inspector = inspect(engine)
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception:
        return False


def create_indexes():
    """Cria todos os índices necessários"""
    db = SessionLocal()
    
    try:
        with engine.connect() as conn:
            # Lista de índices para criar
            indexes = [
                {
                    "name": "idx_chamado_data_abertura",
                    "table": "chamado",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_chamado_data_abertura ON chamado(data_abertura);"
                },
                {
                    "name": "idx_chamado_status",
                    "table": "chamado",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_chamado_status ON chamado(status);"
                },
                {
                    "name": "idx_chamado_prioridade",
                    "table": "chamado",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_chamado_prioridade ON chamado(prioridade);"
                },
                {
                    "name": "idx_chamado_data_conclusao",
                    "table": "chamado",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_chamado_data_conclusao ON chamado(data_conclusao);"
                },
                {
                    "name": "idx_chamado_data_primeira_resposta",
                    "table": "chamado",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_chamado_data_primeira_resposta ON chamado(data_primeira_resposta);"
                },
                {
                    "name": "idx_chamado_composite_sla",
                    "table": "chamado",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_chamado_composite_sla ON chamado(data_abertura, status, prioridade);"
                },
                {
                    "name": "idx_historico_status_chamado_id",
                    "table": "historico_status",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_historico_status_chamado_id ON historico_status(chamado_id);"
                },
                {
                    "name": "idx_historico_status_data",
                    "table": "historico_status",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_historico_status_data ON historico_status(data_status);"
                },
                {
                    "name": "idx_metrics_cache_key",
                    "table": "metrics_cache_db",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_metrics_cache_key ON metrics_cache_db(cache_key);"
                },
                {
                    "name": "idx_metrics_cache_expires",
                    "table": "metrics_cache_db",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_metrics_cache_expires ON metrics_cache_db(expires_at);"
                },
            ]
            
            created = 0
            skipped = 0
            
            for idx_info in indexes:
                try:
                    # Tenta executar o CREATE INDEX
                    conn.execute(text(idx_info["sql"]))
                    conn.commit()
                    print(f"✅ Índice criado: {idx_info['name']}")
                    created += 1
                except Exception as e:
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        print(f"⏭️  Índice já existe: {idx_info['name']}")
                        skipped += 1
                    else:
                        print(f"⚠️  Erro ao criar índice {idx_info['name']}: {e}")
            
            print(f"\n{'='*60}")
            print(f"Resumo: {created} criados, {skipped} já existentes")
            print(f"{'='*60}")
            
            return True
    
    except Exception as e:
        print(f"❌ Erro ao criar índices: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()


if __name__ == "__main__":
    print("🔄 Adicionando índices de SLA ao banco de dados...")
    print("="*60)
    
    success = create_indexes()
    
    sys.exit(0 if success else 1)
