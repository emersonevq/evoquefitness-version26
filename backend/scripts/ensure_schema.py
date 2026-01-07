from __future__ import annotations
import sys
from typing import Dict
from sqlalchemy import inspect, text
from core.db import engine

# Expected columns per table (MySQL dialect)
EXPECTED: Dict[str, Dict[str, str]] = {
    "chamado_anexo": {
        "id": "INT PRIMARY KEY AUTO_INCREMENT",
        "chamado_id": "INT NOT NULL",
        "nome_original": "VARCHAR(255) NOT NULL",
        "nome_arquivo": "VARCHAR(255) NOT NULL",
        "caminho_arquivo": "VARCHAR(500) NOT NULL",
        "tamanho_bytes": "INT NULL",
        "tipo_mime": "VARCHAR(100) NULL",
        "extensao": "VARCHAR(20) NULL",
        "hash_arquivo": "VARCHAR(64) NULL",
        "data_upload": "DATETIME NULL",
        "usuario_upload_id": "INT NULL",
        "descricao": "VARCHAR(500) NULL",
        "ativo": "TINYINT(1) NOT NULL DEFAULT 1",
        "conteudo": "MEDIUMBLOB NULL",
    },
    "ticket_anexos": {
        "id": "INT PRIMARY KEY AUTO_INCREMENT",
        "chamado_id": "INT NOT NULL",
        "nome_original": "VARCHAR(255) NOT NULL",
        "nome_arquivo": "VARCHAR(255) NOT NULL",
        "caminho_arquivo": "VARCHAR(500) NOT NULL",
        "tamanho_bytes": "INT NULL",
        "tipo_mime": "VARCHAR(100) NULL",
        "extensao": "VARCHAR(20) NULL",
        "hash_arquivo": "VARCHAR(64) NULL",
        "data_upload": "DATETIME NULL",
        "usuario_upload_id": "INT NULL",
        "descricao": "VARCHAR(500) NULL",
        "ativo": "TINYINT(1) NOT NULL DEFAULT 1",
        "origem": "VARCHAR(50) NULL",
        "conteudo": "MEDIUMBLOB NULL",
    },
    "historicos_tickets": {
        "id": "INT PRIMARY KEY AUTO_INCREMENT",
        "chamado_id": "INT NOT NULL",
        "usuario_id": "INT NULL",
        "assunto": "VARCHAR(255) NOT NULL",
        "mensagem": "TEXT NOT NULL",
        "destinatarios": "VARCHAR(255) NOT NULL",
        "data_envio": "DATETIME NULL",
    },
    "historico_status": {
        "id": "INT PRIMARY KEY AUTO_INCREMENT",
        "chamado_id": "INT NOT NULL",
        "status": "VARCHAR(50) NOT NULL",
        "data_inicio": "DATETIME NULL",
        "data_fim": "DATETIME NULL",
        "usuario_id": "INT NULL",
        "descricao": "TEXT NULL",
        "created_at": "DATETIME NULL",
        "updated_at": "DATETIME NULL",
    },
    "metrics_cache_db": {
        "id": "INT PRIMARY KEY AUTO_INCREMENT",
        "cache_key": "VARCHAR(100) NOT NULL UNIQUE KEY",
        "cache_value": "TEXT NOT NULL",
        "calculated_at": "DATETIME NULL",
        "expires_at": "DATETIME NULL",
    },
}


def ensure_table_and_columns(table: str, cols: Dict[str, str]) -> list[str]:
    insp = inspect(engine)
    existing_cols = {c.get("name"): c for c in insp.get_columns(table)} if insp.has_table(table) else {}
    actions: list[str] = []
    with engine.begin() as conn:
        if not existing_cols:
            # Create table with minimal structure
            ddl_cols = ", ".join([f"{k} {v}" for k, v in cols.items()])
            conn.exec_driver_sql(f"CREATE TABLE IF NOT EXISTS {table} ({ddl_cols}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
            actions.append(f"created-table:{table}")
            return actions
        # Add missing columns
        existing_set = set(existing_cols.keys())
        for name, ddl in cols.items():
            if name not in existing_set:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                actions.append(f"added:{table}.{name}")
    return actions


def main() -> int:
    total_actions: list[str] = []
    for table, cols in EXPECTED.items():
        try:
            actions = ensure_table_and_columns(table, cols)
            total_actions.extend(actions)
        except Exception as e:
            print(f"[error] {table}: {e}")
    if not total_actions:
        print("OK: schema already up to date")
    else:
        for a in total_actions:
            print(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
