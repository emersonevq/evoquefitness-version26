"""
Script para preencher o campo data_primeira_resposta dos chamados baseado no histórico de status.

Executa: python -m ti.scripts.populate_primeira_resposta
"""
from datetime import datetime
from sqlalchemy.orm import Session
from core.db import SessionLocal, engine
from ti.models.chamado import Chamado
from ti.models.historico_status import HistoricoStatus
from sqlalchemy import and_, or_

def populate_primeira_resposta():
    """
    Preenche data_primeira_resposta de chamados antigos usando o histórico.
    
    Lógica:
    1. Para cada chamado que tem data_primeira_resposta = NULL
    2. Busca o primeiro histórico com status != "Aberto"
    3. Usa a data_inicio desse histórico como data_primeira_resposta
    """
    db = SessionLocal()
    total_atualizados = 0
    total_pulados = 0
    erros = 0
    
    try:
        # Busca chamados que ainda NÃO têm data_primeira_resposta
        chamados_sem_resposta = db.query(Chamado).filter(
            Chamado.data_primeira_resposta.is_(None),
            Chamado.deletado_em.is_(None)
        ).all()
        
        print(f"Total de chamados sem data_primeira_resposta: {len(chamados_sem_resposta)}")
        
        for chamado in chamados_sem_resposta:
            try:
                # Busca o primeiro histórico onde o status mudou de "Aberto"
                primeiro_historico = db.query(HistoricoStatus).filter(
                    and_(
                        HistoricoStatus.chamado_id == chamado.id,
                        HistoricoStatus.status != "Aberto"
                    )
                ).order_by(HistoricoStatus.data_inicio.asc()).first()
                
                if primeiro_historico and primeiro_historico.data_inicio:
                    # Atualiza o chamado com a data da primeira resposta
                    chamado.data_primeira_resposta = primeiro_historico.data_inicio
                    db.add(chamado)
                    total_atualizados += 1
                    
                    if total_atualizados % 10 == 0:
                        db.commit()
                        print(f"✓ {total_atualizados} chamados atualizados...")
                else:
                    # Não encontrou histórico com status diferente de "Aberto"
                    total_pulados += 1
                    
            except Exception as e:
                print(f"✗ Erro ao processar chamado {chamado.id}: {e}")
                erros += 1
                db.rollback()
                continue
        
        # Commit final
        db.commit()
        
        print(f"\n{'='*60}")
        print(f"Processo concluído!")
        print(f"✓ Chamados atualizados: {total_atualizados}")
        print(f"⊘ Chamados sem histórico: {total_pulados}")
        print(f"✗ Erros: {erros}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"Erro crítico ao popular primeira resposta: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("\n🔄 Iniciando preenchimento de data_primeira_resposta...")
    print("Este script vai ler o histórico de status e preencher as datas de primeira resposta.\n")
    populate_primeira_resposta()
