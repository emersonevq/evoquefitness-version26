from __future__ import annotations
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from ti.api import chamados_router, unidades_router, problemas_router, notifications_router, notification_settings_router, alerts_router, email_debug_router, sla_router, powerbi_router, metrics_router
from ti.api.usuarios import router as usuarios_router
from ti.api.dashboard_permissions import router as dashboard_permissions_router
from auth0.routes import router as auth0_router
from core.realtime import mount_socketio
import json
from typing import Any, List, Dict
import uuid
from sqlalchemy.orm import Session
from core.db import get_db, engine
from ti.models.media import Media
from ti.scripts.create_performance_indices import create_indices

# Create the FastAPI application (HTTP)
_http = FastAPI(title="Evoque API - TI", version="1.0.0")

# Criar índices de performance na inicialização
try:
    create_indices()
except Exception as e:
    print(f"⚠️  Erro ao criar índices de performance: {e}")

# Criar tabela de cache de métricas na inicialização
try:
    from ti.scripts.create_metrics_cache_table import create_metrics_cache_table
    create_metrics_cache_table()
    print("✅ Tabela metrics_cache_db criada com sucesso")
except Exception as e:
    print(f"⚠️  Erro ao criar tabela metrics_cache_db: {e}")

# Executar migração do historico_status na inicialização
try:
    from ti.scripts.migrate_historico_status import migrate_historico_status
    migrate_historico_status()
    print("✅ Migração historico_status executada com sucesso")
except Exception as e:
    print(f"⚠️  Erro ao migrar historico_status: {e}")

# Criar tabela de configurações de notificações na inicialização
try:
    from ti.scripts.setup_notification_settings import create_notification_settings_table
    create_notification_settings_table()
except Exception as e:
    print(f"⚠️  Erro ao criar tabela notification_settings: {e}")

# Inicializar scheduler de recalculação automática de SLA
try:
    from ti.services.sla_scheduler import init_scheduler
    init_scheduler()
    print("✅ Scheduler de SLA iniciado com sucesso")
except Exception as e:
    print(f"⚠️  Erro ao inicializar scheduler de SLA: {e}")

# Pré-carregar cache do banco na startup
try:
    from ti.services.sla_cache import SLACacheManager
    from core.db import SessionLocal

    db_warmup = SessionLocal()
    try:
        stats = SLACacheManager.warmup_from_database(db_warmup)
        print(f"✅ Cache pré-carregado: {stats['carregados']} entradas carregadas, {stats['expirados']} expiradas, {stats['erros']} erros")
    finally:
        db_warmup.close()
except Exception as e:
    print(f"⚠️  Erro ao pré-carregar cache: {e}")

# Pré-carregar métricas mensais na startup (warmup de métricas)
try:
    from ti.services.cache_manager_incremental import IncrementalMetricsCache
    from core.db import SessionLocal

    db_warmup_metrics = SessionLocal()
    try:
        metricas = IncrementalMetricsCache.get_metrics(db_warmup_metrics)
        print(f"✅ Métricas mensais pré-carregadas: Total={metricas.get('total', 0)}, Dentro_SLA={metricas.get('dentro_sla', 0)}")
    except Exception as warmup_error:
        print(f"⚠️  Aviso (não crítico): Warmup de métricas falhou: {warmup_error}")
    finally:
        db_warmup_metrics.close()
except Exception as e:
    print(f"⚠️  Erro ao pré-carregar métricas: {e}")

# Static uploads mount
_base_dir = Path(__file__).resolve().parent
_uploads = _base_dir / "uploads"
_uploads.mkdir(parents=True, exist_ok=True)
_http.mount("/uploads", StaticFiles(directory=str(_uploads), html=False), name="uploads")

_allowed_origins = [
    "http://localhost:3005",
    "http://127.0.0.1:3005",
    "http://localhost:5173",  # Vite default dev port
    "http://127.0.0.1:5173",
    "http://147.93.70.206:3005",  # VPS production IP
]

# Adicionar domínios de produção se disponíveis nas env vars
_prod_frontend_url = os.getenv("FRONTEND_URL", "").strip()
_prod_domain = os.getenv("PRODUCTION_DOMAIN", "").strip()
_financial_portal_url = os.getenv("FINANCIAL_PORTAL_URL", "").strip()

if _prod_frontend_url:
    _allowed_origins.append(_prod_frontend_url)
if _prod_domain:
    _allowed_origins.append(f"https://{_prod_domain}")
    _allowed_origins.append(f"http://{_prod_domain}")
if _financial_portal_url:
    _allowed_origins.append(_financial_portal_url)

_http.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware para logar todas as requisições Auth0
@_http.middleware("http")
async def log_auth_requests(request: Request, call_next):
    """Log all Auth0-related requests for debugging"""
    if "/api/auth" in request.url.path:
        print(f"\n[MIDDLEWARE] 📥 Incoming request")
        print(f"[MIDDLEWARE] Method: {request.method}")
        print(f"[MIDDLEWARE] Path: {request.url.path}")
        print(f"[MIDDLEWARE] Full URL: {request.url}")
        print(f"[MIDDLEWARE] Headers:")
        for header, value in request.headers.items():
            if header.lower() not in ["authorization"]:
                print(f"[MIDDLEWARE]   - {header}: {value}")
            else:
                print(f"[MIDDLEWARE]   - {header}: ***[REDACTED]***")

    try:
        response = await call_next(request)

        if "/api/auth" in request.url.path:
            print(f"[MIDDLEWARE] 📤 Response status: {response.status_code}")
            print(f"[MIDDLEWARE] Response headers: {dict(response.headers)}")

        return response
    except Exception as e:
        print(f"[MIDDLEWARE] ❌ Exception occurred: {type(e).__name__}: {str(e)}")
        raise

@_http.get("/api/ping")
def ping():
    return {"message": "pong"}

@_http.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        print(f"Database health check failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "database": str(e)}, 500


@_http.get("/api/test-backend")
def test_backend():
    """Simples teste para confirmar que o backend foi reiniciado"""
    return {"status": "Backend está rodando com o código atualizado!", "timestamp": "OK"}


@_http.get("/api/debug/routes")
def debug_routes():
    """Debug - listar todas as rotas registradas"""
    routes = []
    for route in _http.routes:
        if hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": getattr(route, 'methods', []) or ['GET'],
            })
    return {
        "total_routes": len(routes),
        "routes": sorted(routes, key=lambda x: x['path']),
        "powerbi_embed_token_registered": any("/powerbi/embed-token" in r['path'] for r in routes),
    }


@_http.post("/api/login-media/upload")
async def upload_login_media(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file:
        raise HTTPException(status_code=400, detail="Arquivo ausente")

    content_type = (file.content_type or "").lower()
    print(f"[UPLOAD] Arquivo: {file.filename}, Content-Type: {content_type}")

    if content_type.startswith("image/"):
        kind = "foto"
    elif content_type.startswith("video/"):
        kind = "video"
    else:
        raise HTTPException(status_code=400, detail="Tipo de arquivo não suportado")

    original_name = Path(file.filename or "arquivo").name
    titulo = Path(original_name).stem or "mídia"

    data = await file.read()
    print(f"[UPLOAD] Tamanho do arquivo: {len(data)} bytes")

    try:
        m = Media(
            tipo=kind,
            titulo=titulo,
            descricao=None,
            arquivo_blob=data,
            mime_type=content_type,
            tamanho_bytes=len(data),
            status="ativo",
        )
        db.add(m)
        db.commit()
        db.refresh(m)

        print(f"[UPLOAD] Salvo com ID: {m.id}")

        m.url = f"/api/login-media/{m.id}/download"
        db.add(m)
        db.commit()

        media_type = "image" if kind == "foto" else "video"
        result = {
            "id": m.id,
            "type": media_type,
            "url": f"/api/login-media/{m.id}/download",
            "mime": m.mime_type,
        }
        print(f"[UPLOAD] Resposta: {result}")
        return result
    except Exception as e:
        print(f"[UPLOAD] Falha ao salvar registro: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Falha ao salvar registro: {str(e)}")


@_http.get("/api/login-media/debug/all")
def login_media_debug_all(db: Session = Depends(get_db)):
    """Lista TODOS os vídeos (ativo e inativo) para debug"""
    try:
        all_media = db.query(Media).all()
        return {
            "total": len(all_media),
            "items": [
                {
                    "id": m.id,
                    "tipo": m.tipo,
                    "titulo": m.titulo,
                    "mime_type": m.mime_type,
                    "tamanho_bytes": m.tamanho_bytes,
                    "arquivo_blob_size": len(m.arquivo_blob) if m.arquivo_blob else 0,
                    "status": m.status,
                }
                for m in all_media
            ]
        }
    except Exception as e:
        print(f"[DEBUG_ALL] Erro: {e}")
        import traceback
        traceback.print_exc()
        return {"erro": str(e)}


@_http.get("/api/login-media")
def login_media(db: Session = Depends(get_db)):
    try:
        try:
            Media.__table__.create(bind=engine, checkfirst=True)
        except Exception as create_err:
            print(f"Erro ao criar tabela: {create_err}")
        q = db.query(Media).filter(Media.status == "ativo").order_by(Media.id.desc()).all()
        out = []
        for m in q:
            media_type = "image" if m.tipo == "foto" else "video" if m.tipo == "video" else "image"
            out.append(
                {
                    "id": m.id,
                    "type": media_type,
                    "url": f"/api/login-media/{m.id}/download",
                    "title": m.titulo,
                    "description": m.descricao,
                    "mime": m.mime_type,
                }
            )
        return out
    except Exception as e:
        print(f"Erro ao listar mídias: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao listar mídias: {str(e)}")


@_http.get("/api/login-media/{item_id}/download")
def download_login_media(item_id: int, request: Request, db: Session = Depends(get_db)):
    print(f"\n[DL] ==== START ID:{item_id} ====")
    try:
        m = db.query(Media).filter(Media.id == int(item_id)).first()
        print(f"[DL] Query result: {m is not None}")

        if not m:
            print(f"[DL] Not found")
            raise HTTPException(status_code=404, detail="Not found")

        print(f"[DL] Type:{m.tipo} Status:{m.status} Title:{m.titulo}")

        blob = m.arquivo_blob
        print(f"[DL] Blob type: {type(blob).__name__} Size: {len(blob) if blob else 0}")

        if not blob:
            raise HTTPException(status_code=404, detail="No data")

        mime = m.mime_type or "application/octet-stream"
        # Sanitize filename: remove emojis and non-ASCII characters for HTTP headers
        title_clean = (m.titulo or "media").encode("ascii", errors="ignore").decode("ascii")
        name = title_clean.replace(" ", "_").replace("/", "_").replace("\\", "_")
        if not name or name.strip() == "":
            name = "media"
        file_size = len(blob)

        # Check for Range header (HTTP 206 Partial Content)
        range_header = request.headers.get("range")

        if range_header:
            # Parse range header (e.g., "bytes=0-1023")
            try:
                range_value = range_header.replace("bytes=", "")
                if "-" in range_value:
                    start_str, end_str = range_value.split("-")
                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else file_size - 1

                    # Validate range
                    if start < 0 or end >= file_size or start > end:
                        raise ValueError("Invalid range")

                    chunk_size = end - start + 1
                    print(f"[DL] Range request: bytes {start}-{end}/{file_size}")

                    return Response(
                        content=blob[start:end + 1],
                        status_code=206,
                        media_type=mime,
                        headers={
                            "Content-Disposition": f"inline; filename={name}",
                            "Content-Range": f"bytes {start}-{end}/{file_size}",
                            "Accept-Ranges": "bytes",
                            "Content-Length": str(chunk_size),
                        }
                    )
            except (ValueError, AttributeError) as e:
                print(f"[DL] Invalid range header: {e}")
                # Fall through to normal response if range is invalid

        print(f"[DL] Returning: {len(blob)} bytes as {mime}")
        print(f"[DL] ==== END ====\n")

        return Response(
            content=blob,
            media_type=mime,
            headers={
                "Content-Disposition": f"inline; filename={name}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DL] EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@_http.get("/api/login-media/{item_id}/debug")
def login_media_debug(item_id: int, db: Session = Depends(get_db)):
    """Debug de um vídeo específico"""
    try:
        m = db.query(Media).filter(Media.id == int(item_id)).first()
        if not m:
            return {"erro": "Não encontrada", "id": item_id}
        return {
            "id": m.id,
            "tipo": m.tipo,
            "titulo": m.titulo,
            "mime_type": m.mime_type,
            "tamanho_bytes": m.tamanho_bytes,
            "arquivo_blob_size": len(m.arquivo_blob) if m.arquivo_blob else 0,
            "arquivo_blob_type": type(m.arquivo_blob).__name__,
            "status": m.status,
        }
    except Exception as e:
        print(f"[DEBUG_{item_id}] Erro: {e}")
        import traceback
        traceback.print_exc()
        return {"erro": str(e)}


@_http.delete("/api/login-media/{item_id}")
async def delete_login_media(item_id: int, db: Session = Depends(get_db)):
    try:
        m = db.query(Media).filter(Media.id == int(item_id)).first()
        if not m:
            raise HTTPException(status_code=404, detail="Item não encontrado")
        m.status = "inativo"
        db.add(m)
        db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao remover mídia: {e}")

# Primary mount under /api
_http.include_router(auth0_router)
_http.include_router(chamados_router, prefix="/api")
_http.include_router(usuarios_router, prefix="/api")
_http.include_router(unidades_router, prefix="/api")
_http.include_router(problemas_router, prefix="/api")
_http.include_router(notifications_router, prefix="/api")
_http.include_router(notification_settings_router, prefix="/api")
_http.include_router(alerts_router, prefix="/api")
_http.include_router(email_debug_router, prefix="/api")
_http.include_router(sla_router, prefix="/api")
_http.include_router(powerbi_router, prefix="/api")
_http.include_router(metrics_router, prefix="/api")
_http.include_router(dashboard_permissions_router, prefix="")

# Compatibility mount without prefix, in case the server is run without proxy
_http.include_router(auth0_router)
_http.include_router(chamados_router)
_http.include_router(usuarios_router)
_http.include_router(unidades_router)
_http.include_router(problemas_router)
_http.include_router(notifications_router)
_http.include_router(notification_settings_router)
_http.include_router(alerts_router)
_http.include_router(email_debug_router)
_http.include_router(sla_router)
_http.include_router(powerbi_router)
_http.include_router(metrics_router)
_http.include_router(dashboard_permissions_router)

# Wrap with Socket.IO ASGI app (exports as 'app')
app = mount_socketio(_http)


# Register event loop for Socket.IO sync-to-async bridge
import asyncio
from core.realtime import set_event_loop

@_http.on_event("startup")
async def startup_event():
    """Register the event loop for Socket.IO event emission from sync context"""
    try:
        loop = asyncio.get_event_loop()
        set_event_loop(loop)
        print(f"[STARTUP] ✓ Event loop registered for Socket.IO: {loop}")
    except Exception as e:
        print(f"[STARTUP] ⚠️  Failed to register event loop: {e}")
