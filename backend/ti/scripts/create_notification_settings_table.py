"""
Script para criar a tabela notification_settings se ela não existir.
"""

from core.db import engine, Base
from backend.ti.models.notification_settings import NotificationSettings

def create_notification_settings_table():
    """Cria a tabela notification_settings"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Tabela 'notification_settings' criada/verificada com sucesso!")
        return True
    except Exception as e:
        print(f"✗ Erro ao criar tabela: {e}")
        return False

if __name__ == "__main__":
    create_notification_settings_table()
