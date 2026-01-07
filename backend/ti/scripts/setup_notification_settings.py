#!/usr/bin/env python3
"""
Script para criar a tabela notification_settings no banco de dados.
Pode ser executado via: python -m ti.scripts.setup_notification_settings
"""

import sys
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from core.db import engine, Base

def create_notification_settings_table():
    """
    Cria a tabela notification_settings se ela não existir.
    Também insere a configuração padrão.
    """
    try:
        # Importar o modelo para registrá-lo em Base.metadata
        from ti.models.notification_settings import NotificationSettings
        
        # Verificar se a tabela já existe
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'notification_settings' in tables:
            print("✓ Tabela 'notification_settings' já existe!")
        else:
            print("➜ Criando tabela 'notification_settings'...")
            # Criar a tabela usando o Base.metadata
            Base.metadata.create_all(bind=engine)
            print("✓ Tabela 'notification_settings' criada com sucesso!")
        
        # Inserir configuração padrão se não existir
        print("➜ Verificando configuração padrão...")
        with engine.connect() as conn:
            # Verificar se já existe uma configuração
            result = conn.execute(text("SELECT COUNT(*) FROM notification_settings"))
            count = result.scalar()
            
            if count == 0:
                # Inserir configuração padrão
                conn.execute(text("""
                    INSERT INTO notification_settings (
                        chamado_enabled,
                        sistema_enabled,
                        alerta_enabled,
                        erro_enabled,
                        som_habilitado,
                        som_tipo,
                        estilo_exibicao,
                        posicao,
                        duracao,
                        tamanho,
                        mostrar_icone,
                        mostrar_acao,
                        criado_em,
                        atualizado_em
                    ) VALUES (
                        TRUE, TRUE, TRUE, TRUE, TRUE, 'notificacao', 'toast', 'top-right', 5, 'medio', TRUE, TRUE, NOW(), NOW()
                    )
                """))
                conn.commit()
                print("✓ Configuração padrão inserida com sucesso")
            else:
                print(f"✓ Configuração padrão já existe ({count} registro(s))")
        
        return True
        
    except SQLAlchemyError as e:
        print(f"✗ Erro de banco de dados: {e}")
        return False
    except Exception as e:
        print(f"✗ Erro ao criar tabela notification_settings: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_notification_settings_table()
    sys.exit(0 if success else 1)
