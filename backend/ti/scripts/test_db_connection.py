from __future__ import annotations
import os
import sys
import time
from typing import Optional

import pymysql
from dotenv import load_dotenv


def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v


def main() -> int:
    load_dotenv()

    host = getenv("DB_HOST", "localhost")
    user = getenv("DB_USER", "root")
    password = getenv("DB_PASSWORD", "")
    db = getenv("DB_NAME", "test")
    port = int(getenv("DB_PORT", "3306") or 3306)
    ssl_ca = getenv("DB_SSL_CA")

    conn_kwargs = dict(
        host=host,
        user=user,
        password=password,
        database=db,
        port=port,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=7,
        write_timeout=7,
        charset="utf8mb4",
        autocommit=True,
    )
    if ssl_ca:
        conn_kwargs["ssl"] = {"ca": ssl_ca}

    t0 = time.time()
    try:
        with pymysql.connect(**conn_kwargs) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() AS version")
                ver = cur.fetchone()
                # Try common tables
                total_unidades = None
                for sql in (
                    "SELECT COUNT(*) AS c FROM unidade",
                    "SELECT COUNT(*) AS c FROM unidades",
                ):
                    try:
                        cur.execute(sql)
                        row = cur.fetchone()
                        if row and "c" in row:
                            total_unidades = int(row["c"])  # type: ignore
                            break
                    except Exception:
                        continue
                # Try called problems tables
                total_problemas = None
                for sql in (
                    "SELECT COUNT(*) AS c FROM problema",
                    "SELECT COUNT(*) AS c FROM problemas",
                    "SELECT COUNT(*) AS c FROM problema_reportado",
                    "SELECT COUNT(*) AS c FROM problemas_reportados",
                ):
                    try:
                        cur.execute(sql)
                        row = cur.fetchone()
                        if row and "c" in row:
                            total_problemas = int(row["c"])  # type: ignore
                            break
                    except Exception:
                        continue
        dt = time.time() - t0
        print(
            {
                "ok": True,
                "version": ver.get("version") if isinstance(ver, dict) else ver,
                "total_unidades": total_unidades,
                "total_problemas": total_problemas,
                "elapsed_sec": round(dt, 3),
            }
        )
        return 0
    except Exception as e:
        dt = time.time() - t0
        print({"ok": False, "error": str(e), "elapsed_sec": round(dt, 3)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
