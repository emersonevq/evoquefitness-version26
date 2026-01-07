"""
Script para criar notificações de teste no banco de dados.
Use este script para testar a interface de notificações do painel admin.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.db import SessionLocal
from ti.models.notification import Notification
from core.utils import now_brazil_naive
import json


def create_test_notifications():
    """Cria notificações de teste no banco de dados."""
    db = SessionLocal()
    
    try:
        # Limpar notificações anteriores para teste
        existing = db.query(Notification).count()
        print(f"[INFO] Notificações existentes no banco: {existing}")
        
        test_notifications = [
            {
                "tipo": "chamado",
                "titulo": "Novo chamado criado",
                "mensagem": "Um novo chamado foi criado no sistema de TI",
                "recurso": "chamado",
                "recurso_id": 1,
                "acao": "criado",
                "dados": json.dumps({"chamado_numero": "001", "prioridade": "alta"}),
                "lido": False,
            },
            {
                "tipo": "chamado",
                "titulo": "Chamado #002 - Status alterado",
                "mensagem": "O chamado mudou para 'Em Andamento'",
                "recurso": "chamado",
                "recurso_id": 2,
                "acao": "status_alterado",
                "dados": json.dumps({"status_anterior": "Aberto", "novo_status": "Em Andamento"}),
                "lido": False,
            },
            {
                "tipo": "sistema",
                "titulo": "Backup concluído com sucesso",
                "mensagem": "O backup diário do sistema foi concluído",
                "recurso": "sistema",
                "recurso_id": None,
                "acao": "backup_concluido",
                "dados": json.dumps({"tamanho_mb": 1024, "tempo_minutos": 15}),
                "lido": True,
            },
            {
                "tipo": "alerta",
                "titulo": "Espaço em disco baixo",
                "mensagem": "O espaço disponível no servidor está abaixo de 20%",
                "recurso": "servidor",
                "recurso_id": None,
                "acao": "alerta_espaco",
                "dados": json.dumps({"espaco_disponivel_gb": 45, "espaco_total_gb": 500}),
                "lido": False,
            },
            {
                "tipo": "erro",
                "titulo": "Falha na sincronização de dados",
                "mensagem": "Erro durante a sincronização com a base de dados remota",
                "recurso": "sincronizacao",
                "recurso_id": None,
                "acao": "erro_sync",
                "dados": json.dumps({"erro_codigo": 500, "tentativas": 3}),
                "lido": False,
            },
            {
                "tipo": "chamado",
                "titulo": "Chamado fechado",
                "mensagem": "O chamado foi fechado e a solução validada",
                "recurso": "chamado",
                "recurso_id": 3,
                "acao": "fechado",
                "dados": json.dumps({"tempo_resolucao_horas": 2.5}),
                "lido": True,
            },
        ]
        
        for notif_data in test_notifications:
            notification = Notification(
                tipo=notif_data["tipo"],
                titulo=notif_data["titulo"],
                mensagem=notif_data["mensagem"],
                recurso=notif_data.get("recurso"),
                recurso_id=notif_data.get("recurso_id"),
                acao=notif_data.get("acao"),
                dados=notif_data.get("dados"),
                lido=notif_data.get("lido", False),
            )
            
            if notif_data.get("lido"):
                notification.lido_em = now_brazil_naive()
            
            db.add(notification)
            print(f"[✓] Adicionada: {notif_data['titulo']}")
        
        db.commit()
        print(f"\n[✓] {len(test_notifications)} notificações de teste criadas com sucesso!")
        
    except Exception as e:
        db.rollback()
        print(f"[✗] Erro ao criar notificações: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Criando notificações de teste...\n")
    create_test_notifications()
    print("\nNotificações de teste prontas para visualização no painel admin!")
