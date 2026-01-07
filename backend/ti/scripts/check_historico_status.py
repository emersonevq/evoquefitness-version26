#!/usr/bin/env python
"""
Diagnostic script to check historico_status table structure and report issues.
"""

from sqlalchemy import inspect, text
from core.db import engine

def check_historico_status():
    """Check historico_status table structure"""
    
    print("\n" + "="*80)
    print("DIAGNÓSTICO: Tabela historico_status")
    print("="*80 + "\n")
    
    try:
        insp = inspect(engine)
        
        # Check if table exists
        if not insp.has_table("historico_status"):
            print("❌ ERRO: Tabela 'historico_status' não existe no banco de dados!")
            return False
        
        print("✅ Tabela 'historico_status' existe\n")
        
        # Get existing columns
        cols = insp.get_columns("historico_status")
        existing_names = {c.get("name") for c in cols}
        
        print("Colunas existentes:")
        for c in cols:
            nullable = "NULL" if c.get("nullable") else "NOT NULL"
            col_type = c.get("type")
            print(f"  - {c.get('name'):20} {col_type:20} {nullable}")
        
        # Expected columns (from ORM model)
        expected_cols = {
            "id": "INTEGER",
            "chamado_id": "INTEGER",
            "status": "VARCHAR",
            "data_inicio": "DATETIME",
            "data_fim": "DATETIME",
            "usuario_id": "INTEGER",
            "descricao": "TEXT",
            "created_at": "DATETIME",
            "updated_at": "DATETIME",
        }
        
        print("\n" + "-"*80)
        print("Verificação de colunas obrigatórias:")
        print("-"*80)
        
        issues = []
        for col_name in expected_cols:
            if col_name not in existing_names:
                issues.append(f"  ❌ FALTA: {col_name}")
                print(f"  ❌ FALTA: {col_name}")
            else:
                print(f"  ✅ Existe: {col_name}")
        
        # Check for old columns
        old_cols = {"status_anterior", "status_novo", "data_mudanca", "motivo"}
        print("\n" + "-"*80)
        print("Verificação de colunas antigas (devem ser removidas):")
        print("-"*80)
        
        old_found = existing_names & old_cols
        if old_found:
            print(f"  ⚠️  Colunas antigas encontradas: {old_found}")
            issues.append(f"Colunas antigas encontradas: {old_found}")
        else:
            print("  ✅ Nenhuma coluna antiga encontrada")
        
        # Check table size
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM historico_status")).scalar()
            print(f"\n✅ Total de registros: {result}")
        
        # Summary
        print("\n" + "="*80)
        if not issues:
            print("✅ SUCESSO: Tabela estruturada corretamente!")
        else:
            print("❌ PROBLEMAS ENCONTRADOS:")
            for issue in issues:
                print(f"  {issue}")
            print("\n💡 Solução:")
            print("  Execute o script de migração:")
            print("    python backend/ti/scripts/migrate_historico_status.py")
            print("  Ou reinicie o backend para executar migração automática")
        
        print("="*80 + "\n")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"❌ ERRO ao verificar tabela: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = check_historico_status()
    exit(0 if success else 1)
