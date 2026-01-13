from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_
from core.db import get_db, engine
from ti.schemas.chamado import (
    ChamadoCreate,
    ChamadoOut,
    ChamadoStatusUpdate,
    ChamadoDeleteRequest,
    ALLOWED_STATUSES,
)
from ti.services.chamados import criar_chamado as service_criar
from ti.services.sla import SLACalculator
from ti.services.sla_cache import SLACacheManager
from ti.models.sla_config import HistoricoSLA
from core.realtime import sio
from werkzeug.security import check_password_hash
from ..models.notification import Notification
import json
from core.utils import now_brazil_naive
from ..models import Chamado, User, TicketAnexo, ChamadoAnexo, HistoricoTicket, HistoricoStatus, HistoricoAnexo
from ti.schemas.attachment import AnexoOut
from ti.schemas.ticket import HistoricoItem, HistoricoResponse
from sqlalchemy import inspect, text
from core.email_msgraph import send_async, send_chamado_abertura, send_chamado_status

from fastapi.responses import Response

router = APIRouter(prefix="/chamados", tags=["TI - Chamados"])


def _sincronizar_sla(db: Session, chamado: Chamado, status_anterior: str | None = None) -> None:
    """
    Função auxiliar para sincronizar um chamado com a tabela de histórico de SLA.
    Deve ser chamada sempre que um chamado é criado ou atualizado.
    TAMBÉM invalida o cache automaticamente e atualiza métricas incrementalmente.
    """
    try:
        try:
            HistoricoSLA.__table__.create(bind=engine, checkfirst=True)
        except Exception:
            pass

        sla_status = SLACalculator.get_sla_status(db, chamado)

        # Extrai métricas de resposta e resolução
        resposta_metric = sla_status.get("resposta_metric")
        resolucao_metric = sla_status.get("resolucao_metric")

        tempo_resposta_horas = resposta_metric.get("tempo_decorrido_horas") if resposta_metric else None
        limite_sla_resposta_horas = resposta_metric.get("tempo_limite_horas") if resposta_metric else None
        tempo_resolucao_horas = resolucao_metric.get("tempo_decorrido_horas") if resolucao_metric else None
        limite_sla_horas = resolucao_metric.get("tempo_limite_horas") if resolucao_metric else None

        # Procura por histórico existente
        existing = db.query(HistoricoSLA).filter(
            HistoricoSLA.chamado_id == chamado.id
        ).order_by(HistoricoSLA.criado_em.desc()).first()

        if existing:
            # Atualiza o último histórico com novos cálculos
            existing.status_novo = chamado.status
            existing.status_anterior = status_anterior or existing.status_anterior
            existing.tempo_resposta_horas = tempo_resposta_horas
            existing.limite_sla_resposta_horas = limite_sla_resposta_horas
            existing.tempo_resolucao_horas = tempo_resolucao_horas
            existing.limite_sla_horas = limite_sla_horas
            existing.status_sla = sla_status.get("status_geral")
            db.add(existing)
        else:
            # Cria novo histórico
            historico = HistoricoSLA(
                chamado_id=chamado.id,
                usuario_id=None,
                acao="criacao" if not status_anterior else "atualizacao",
                status_anterior=status_anterior,
                status_novo=chamado.status,
                tempo_resposta_horas=tempo_resposta_horas,
                limite_sla_resposta_horas=limite_sla_resposta_horas,
                tempo_resolucao_horas=tempo_resolucao_horas,
                limite_sla_horas=limite_sla_horas,
                status_sla=sla_status.get("status_geral"),
                criado_em=chamado.data_abertura or now_brazil_naive(),
            )
            db.add(historico)

        db.commit()

        # INVALIDA��ÃO DE CACHE: Quando um chamado é atualizado, invalida caches relacionados
        SLACacheManager.invalidate_by_chamado(db, chamado.id)

        # ATUALIZAÇÃO INCREMENTAL DE MÉTRICAS: Recalcula apenas o chamado afetado
        from ti.services.cache_manager_incremental import IncrementalMetricsCache
        IncrementalMetricsCache.update_for_chamado(db, chamado.id)

    except Exception as e:
        db.rollback()
        print(f"[SLA SYNC] Erro ao sincronizar SLA do chamado {chamado.id}: {e}")
        pass


def _normalize_status(s: str) -> str:
    """
    Normaliza o status para o formato padrão.
    Formatos aceitos: Aberto, Em andamento, Em análise, Concluído, Cancelado
    """
    if not s:
        return "Aberto"
    
    # Remove espaços extras e converte para lowercase para comparação
    s_lower = s.strip().lower()
    
    # Mapeamento direto baseado em lowercase
    mapping_lower = {
        "aberto": "Aberto",
        "em andamento": "Em andamento",
        "emandamento": "Em andamento",
        "em_andamento": "Em andamento",
        "aguardando": "Em andamento",
        "em análise": "Em análise",
        "em analise": "Em análise",
        "emanalise": "Em análise",
        "em_analise": "Em análise",
        "em_análise": "Em análise",
        "analise": "Em análise",
        "análise": "Em análise",
        "concluído": "Concluído",
        "concluido": "Concluído",
        "finalizado": "Concluído",
        "cancelado": "Cancelado",
    }
    
    if s_lower in mapping_lower:
        return mapping_lower[s_lower]
    
    # Se não encontrou, verifica se já está no formato correto
    if s in ALLOWED_STATUSES:
        return s
    
    # Caso padrão
    print(f"[NORMALIZE] Status não reconhecido: '{s}' - retornando 'Aberto'")
    return "Aberto" 


def _table_exists(table_name: str) -> bool:
    """Verifica se uma tabela existe no banco de dados"""
    try:
        from sqlalchemy import inspect as sa_inspect
        insp = sa_inspect(engine)
        return insp.has_table(table_name)
    except Exception:
        return False


@router.get("", response_model=list[ChamadoOut])
def listar_chamados(db: Session = Depends(get_db)):
    try:
        try:
            Chamado.__table__.create(bind=engine, checkfirst=True)
        except Exception:
            pass
        try:
            return db.query(Chamado).filter(Chamado.deletado_em.is_(None)).order_by(Chamado.id.desc()).all()
        except Exception:
            return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar chamados: {e}")


@router.post("", response_model=ChamadoOut)
def criar_chamado(payload: ChamadoCreate, db: Session = Depends(get_db)):
    try:
        try:
            Chamado.__table__.create(bind=engine, checkfirst=True)
        except Exception:
            pass
        ch = service_criar(db, payload)

        # Sincroniza o chamado com a tabela de SLA
        _sincronizar_sla(db, ch)

        # ATUALIZAÇÃO REAL-TIME: Incrementa contador de "chamados hoje"
        from ti.services.cache_manager_incremental import ChamadosTodayCounter
        chamados_hoje = ChamadosTodayCounter.increment(db)

        try:
            Notification.__table__.create(bind=engine, checkfirst=True)
            dados = json.dumps({
                "id": ch.id,
                "codigo": ch.codigo,
                "protocolo": ch.protocolo,
                "status": ch.status,
            }, ensure_ascii=False)
            n = Notification(
                tipo="chamado",
                titulo=f"Novo chamado {ch.codigo}",
                mensagem=f"{ch.solicitante} abriu um chamado de {ch.problema} na unidade {ch.unidade}",
                recurso="chamado",
                recurso_id=ch.id,
                acao="criado",
                dados=dados,
            )
            db.add(n)
            db.commit()
            db.refresh(n)
            import anyio
            anyio.from_thread.run(sio.emit, "chamado:created", {"id": ch.id})
            anyio.from_thread.run(sio.emit, "notification:new", {
                "id": n.id,
                "tipo": n.tipo,
                "titulo": n.titulo,
                "mensagem": n.mensagem,
                "recurso": n.recurso,
                "recurso_id": n.recurso_id,
                "acao": n.acao,
                "dados": n.dados,
                "lido": n.lido,
                "criado_em": n.criado_em.isoformat() if n.criado_em else None,
            })
            # EMITE ATUALIZAÇÃO DE MÉTRICAS EM TEMPO REAL
            from ti.services.cache_manager_incremental import IncrementalMetricsCache
            metricas = IncrementalMetricsCache.get_metrics(db)
            anyio.from_thread.run(sio.emit, "metrics:updated", {
                "chamados_hoje": chamados_hoje,
                "sla_metrics": metricas,
                "timestamp": now_brazil_naive().isoformat(),
            })
        except Exception as e:
            print(f"[WebSocket] Erro ao emitir eventos: {e}")
            pass
        try:
            print(f"[CHAMADOS] 📧 Chamado {ch.codigo} criado. Disparando envio de email de abertura...")
            send_async(send_chamado_abertura, ch)
            print(f"[CHAMADOS] ✅ send_async() foi chamado com sucesso para send_chamado_abertura")
        except Exception as e:
            print(f"[CHAMADOS] ❌ ERRO ao chamar send_async para send_chamado_abertura: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        db.refresh(ch)
        db.expunge(ch)
        return ch
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar chamado: {e}")


def _cols(table: str) -> set[str]:
    try:
        insp = inspect(engine)
        return {c.get("name") for c in insp.get_columns(table)}
    except Exception:
        return set()


def _ensure_column(table: str, column: str, ddl: str) -> None:
    try:
        if column not in _cols(table):
            with engine.connect() as conn:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    except Exception:
        pass


def _insert_attachment(db: Session, table: str, values: dict) -> int:
    cols = _cols(table)
    # Map aliases to support legacy schemas
    if "arquivo_nome" in cols and "arquivo_nome" not in values and "nome_arquivo" in values:
        values["arquivo_nome"] = values["nome_arquivo"]
    if "arquivo_caminho" in cols and "arquivo_caminho" not in values and "caminho_arquivo" in values:
        values["arquivo_caminho"] = values["caminho_arquivo"]
    if "criado_em" in cols and "criado_em" not in values and "data_upload" in values:
        values["criado_em"] = values["data_upload"]
    data = {k: v for k, v in values.items() if k in cols}
    if not data:
        raise HTTPException(status_code=500, detail="Estrutura da tabela de anexo inválida")
    cols_sql = ", ".join(data.keys())
    params_sql = ", ".join(f":{k}" for k in data.keys())
    res = db.execute(text(f"INSERT INTO {table} ({cols_sql}) VALUES ({params_sql})"), data)
    rid = res.lastrowid  # type: ignore[attr-defined]
    db.flush()
    return int(rid or 0)


def _update_path(db: Session, table: str, rid: int, path: str) -> None:
    cols = _cols(table)
    if "caminho_arquivo" in cols:
        db.execute(text(f"UPDATE {table} SET caminho_arquivo=:p WHERE id=:i"), {"p": path, "i": rid})
    if "arquivo_caminho" in cols:
        db.execute(text(f"UPDATE {table} SET arquivo_caminho=:p WHERE id=:i"), {"p": path, "i": rid})


def _select_anexo_query(table: str) -> str:
    cols = _cols(table)
    name_expr = ("nome_original" if "nome_original" in cols else ("arquivo_nome" if "arquivo_nome" in cols else "NULL")) + " AS nome_original"
    path_expr = ("caminho_arquivo" if "caminho_arquivo" in cols else ("arquivo_caminho" if "arquivo_caminho" in cols else "NULL")) + " AS caminho_arquivo"
    mime_expr = ("tipo_mime" if "tipo_mime" in cols else ("mime_type" if "mime_type" in cols else "NULL")) + " AS tipo_mime"
    size_expr = ("tamanho_bytes" if "tamanho_bytes" in cols else "NULL") + " AS tamanho_bytes"
    date_expr = ("data_upload" if "data_upload" in cols else ("criado_em" if "criado_em" in cols else "NULL")) + " AS data_upload"
    return f"SELECT id, {name_expr}, {path_expr}, {mime_expr}, {size_expr}, {date_expr} FROM {table}"


def _select_download_query(table: str) -> str:
    cols = _cols(table)
    nome_arq = ("nome_arquivo" if "nome_arquivo" in cols else ("arquivo_nome" if "arquivo_nome" in cols else "NULL")) + " AS nome_arquivo"
    nome_orig = ("nome_original" if "nome_original" in cols else ("arquivo_nome" if "arquivo_nome" in cols else "NULL")) + " AS nome_original"
    mime_expr = ("tipo_mime" if "tipo_mime" in cols else ("mime_type" if "mime_type" in cols else "NULL")) + " AS tipo_mime"
    conteudo = ("conteudo" if "conteudo" in cols else "NULL") + " AS conteudo"
    return f"SELECT id, {nome_arq}, {nome_orig}, {mime_expr}, {conteudo} FROM {table} WHERE id=:i"


@router.post("/with-attachments", response_model=ChamadoOut)
def criar_chamado_com_anexos(
    solicitante: str = Form(...),
    cargo: str = Form(...),
    email: str = Form(...),
    telefone: str = Form(...),
    unidade: str = Form(...),
    problema: str = Form(...),
    internetItem: str | None = Form(None),
    visita: str | None = Form(None),
    descricao: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    autor_email: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        try:
            Chamado.__table__.create(bind=engine, checkfirst=True)
            ChamadoAnexo.__table__.create(bind=engine, checkfirst=True)
            _ensure_column("chamado_anexo", "conteudo", "MEDIUMBLOB NULL")
        except Exception:
            pass
        payload = ChamadoCreate(
            solicitante=solicitante,
            cargo=cargo,
            email=email,
            telefone=telefone,
            unidade=unidade,
            problema=problema,
            internetItem=internetItem,
            visita=visita,
            descricao=descricao,
        )
        ch = service_criar(db, payload)

        # Sincroniza o chamado com a tabela de SLA
        _sincronizar_sla(db, ch)

        if files:
            user_id = None
            if autor_email:
                try:
                    user = db.query(User).filter(User.email == autor_email).first()
                    user_id = user.id if user else None
                except Exception:
                    user_id = None
            import hashlib
            saved = 0
            for f in files:
                try:
                    safe_name = (f.filename or "arquivo")
                    content = f.file.read()
                    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else None
                    sha = hashlib.sha256(content).hexdigest()
                    now = now_brazil_naive()
                    rid = _insert_attachment(db, "chamado_anexo", {
                        "chamado_id": ch.id,
                        "nome_original": safe_name,
                        "nome_arquivo": safe_name,
                        "arquivo_nome": safe_name,
                        "caminho_arquivo": "pending",
                        "arquivo_caminho": "pending",
                        "tamanho_bytes": len(content),
                        "tipo_mime": f.content_type or None,
                        "extensao": ext or None,
                        "hash_arquivo": sha,
                        "data_upload": now,
                        "criado_em": now,
                        "usuario_upload_id": user_id,
                        "descricao": None,
                        "ativo": True,
                        "conteudo": content,
                    })
                    if rid:
                        _update_path(db, "chamado_anexo", rid, f"api/chamados/anexos/chamado/{rid}")
                        saved += 1
                except Exception:
                    continue
            db.commit()
            if files and saved == 0:
                raise HTTPException(status_code=500, detail="Falha ao salvar anexos da abertura")
            # Try to gather saved attachments and send them with the opening email
            try:
                attach_rows = db.execute(text("SELECT id, nome_original, tipo_mime FROM chamado_anexo WHERE chamado_id=:i"), {"i": ch.id}).fetchall()
                attachments_payload = []
                import base64
                for ar in attach_rows:
                    try:
                        aid = int(ar[0])
                        nome = ar[1] or f"anexo_{aid}"
                        mime = ar[2] or "application/octet-stream"
                        res = db.execute(text(_select_download_query("chamado_anexo")), {"i": aid}).fetchone()
                        if res and res[4]:
                            content = res[4]
                            b64 = base64.b64encode(content).decode("ascii")
                            attachments_payload.append({
                                "name": nome,
                                "contentType": mime,
                                "contentBytes": b64,
                            })
                    except Exception:
                        continue
                # send async email with attachments
                try:
                    print(f"[CHAMADOS] 📧 Chamado {ch.codigo} criado com anexos. Disparando envio de email...")
                    if attachments_payload:
                        send_async(send_chamado_abertura, ch, attachments_payload)
                        print(f"[CHAMADOS] ✅ send_async() chamado com {len(attachments_payload)} anexo(s)")
                    else:
                        send_async(send_chamado_abertura, ch)
                        print(f"[CHAMADOS] ✅ send_async() chamado sem anexos")
                except Exception as e:
                    print(f"[CHAMADOS] ❌ ERRO ao chamar send_async: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
            except Exception:
                pass
        else:
            # No files: still send the opening email
            try:
                print(f"[CHAMADOS] 📧 Chamado {ch.codigo} criado sem anexos. Disparando envio de email...")
                send_async(send_chamado_abertura, ch)
                print(f"[CHAMADOS] ✅ send_async() foi chamado com sucesso")
            except Exception as e:
                print(f"[CHAMADOS] ❌ ERRO ao chamar send_async: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

        # REFRESH e EXPUNGE ANTES de qualquer operação async para evitar estado transitório
        try:
            db.refresh(ch)
            db.expunge(ch)
        except Exception as e:
            print(f"[REFRESH] Erro ao refresh chamado: {e}")
            # Mesmo com erro, continue com o resto da operação
            pass

        # EMITE ATUALIZAÇÃO DE MÉTRICAS EM TEMPO REAL (sem dependência de db após refresh)
        try:
            from ti.services.cache_manager_incremental import IncrementalMetricsCache
            metricas = IncrementalMetricsCache.get_metrics(db)
            import anyio
            anyio.from_thread.run(sio.emit, "metrics:updated", {
                "chamados_hoje": 1,
                "sla_metrics": metricas,
                "timestamp": now_brazil_naive().isoformat(),
            })
        except Exception as e:
            print(f"[WebSocket] Erro ao emitir eventos de métricas: {e}")
            pass

        return ch
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar chamado com anexos: {e}")


@router.post("/{chamado_id}/ticket")
def enviar_ticket(
    chamado_id: int,
    assunto: str = Form(...),
    mensagem: str = Form(...),
    destinatarios: str = Form(...),
    autor_email: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    try:
        # Verificar se o chamado existe e não foi deletado
        chamado = db.query(Chamado).filter(
            (Chamado.id == chamado_id) & (Chamado.deletado_em.is_(None))
        ).first()
        if not chamado:
            raise HTTPException(status_code=404, detail="Chamado não encontrado")

        # garantir tabelas necessárias para anexos de ticket
        TicketAnexo.__table__.create(bind=engine, checkfirst=True)
        _ensure_column("ticket_anexos", "conteudo", "MEDIUMBLOB NULL")
        user_id = None
        if autor_email:
            try:
                user = db.query(User).filter(User.email == autor_email).first()
                user_id = user.id if user else None
            except Exception:
                user_id = None
        # registrar histórico via ORM
        h = HistoricoTicket(
            chamado_id=chamado_id,
            usuario_id=user_id or None,
            assunto=assunto,
            mensagem=mensagem,
            destinatarios=destinatarios,
            data_envio=now_brazil_naive(),
        )
        db.add(h)
        db.commit()
        db.refresh(h)
        h_id = h.id
        # salvar anexos em tickets_anexos com metadados e caminho
        if files:
            import hashlib
            saved = 0
            for f in files:
                try:
                    safe_name = (f.filename or "arquivo")
                    content = f.file.read()
                    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else None
                    sha = hashlib.sha256(content).hexdigest()
                    now = now_brazil_naive()
                    rid = _insert_attachment(db, "ticket_anexos", {
                        "chamado_id": chamado_id,
                        "nome_original": safe_name,
                        "nome_arquivo": safe_name,
                        "arquivo_nome": safe_name,
                        "caminho_arquivo": "pending",
                        "arquivo_caminho": "pending",
                        "tamanho_bytes": len(content),
                        "tipo_mime": f.content_type or None,
                        "extensao": ext or None,
                        "hash_arquivo": sha,
                        "data_upload": now,
                        "criado_em": now,
                        "usuario_upload_id": user_id,
                        "descricao": None,
                        "ativo": True,
                        "origem": "ticket",
                        "conteudo": content,
                    })
                    if rid:
                        _update_path(db, "ticket_anexos", rid, f"api/chamados/anexos/ticket/{rid}")
                        saved += 1
                except Exception:
                    continue
            db.commit()
            if files and saved == 0:
                raise HTTPException(status_code=500, detail="Falha ao salvar anexos do ticket")
        # Enviar email de ticket enviado
        try:
            print(f"[CHAMADOS] 📧 Ticket #{h_id} enviado para chamado {chamado_id}. Disparando email...")
            # Construir e-mail de ticket enviado
            from core.email_msgraph import send_mail
            subject = f"[Evoque TI] Novo ticket - Chamado {chamado.codigo}"
            html_body = f"""
            <p>Olá,</p>
            <p>Um novo ticket foi enviado no chamado <strong>{chamado.codigo}</strong>:</p>
            <p><strong>Assunto:</strong> {assunto}</p>
            <p><strong>Mensagem:</strong></p>
            <p>{mensagem.replace(chr(10), '<br>')}</p>
            <p>Acesse o portal para ver mais detalhes.</p>
            """
            # Enviamos para os destinatários especificados e CC para TI
            to_emails = [e.strip() for e in destinatarios.split(';') if e.strip()] if destinatarios else []
            if to_emails:
                send_async(send_mail, subject, html_body, to=to_emails)
                print(f"[CHAMADOS] ✅ Email de ticket enviado para {len(to_emails)} destinatário(s)")
        except Exception as e:
            print(f"[CHAMADOS] ❌ ERRO ao enviar email de ticket: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        return {"ok": True, "historico_id": h_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar ticket: {e}")


@router.get("/anexos/chamado/{anexo_id}")
def baixar_anexo_chamado(anexo_id: int, db: Session = Depends(get_db)):
    sql = _select_download_query("chamado_anexo")
    res = db.execute(text(sql), {"i": anexo_id}).fetchone()
    if not res or not res[4]:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    nome = res[1] or res[2] or f"anexo_{anexo_id}"
    mime = res[3] or "application/octet-stream"
    headers = {"Content-Disposition": f"inline; filename={nome}"}
    return Response(content=res[4], media_type=mime, headers=headers)


@router.get("/anexos/ticket/{anexo_id}")
def baixar_anexo_ticket(anexo_id: int, db: Session = Depends(get_db)):
    sql = _select_download_query("ticket_anexos")
    res = db.execute(text(sql), {"i": anexo_id}).fetchone()
    if not res or not res[4]:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    nome = res[1] or res[2] or f"anexo_{anexo_id}"
    mime = res[3] or "application/octet-stream"
    headers = {"Content-Disposition": f"inline; filename={nome}"}
    return Response(content=res[4], media_type=mime, headers=headers)


@router.get("/{chamado_id}/historico", response_model=HistoricoResponse)
def obter_historico(chamado_id: int, db: Session = Depends(get_db)):
    try:
        items: list[HistoricoItem] = []
        ch = db.query(Chamado).filter(
            (Chamado.id == chamado_id) & (Chamado.deletado_em.is_(None))
        ).first()
        if not ch:
            raise HTTPException(status_code=404, detail="Chamado não encontrado")
        # anexos enviados na abertura (chamado_anexo) e descrição do chamado
        sql_an = _select_anexo_query("chamado_anexo") + " WHERE chamado_id=:i ORDER BY data_upload ASC"
        rows = db.execute(text(sql_an), {"i": chamado_id}).fetchall()
        anexos_abertura = None
        first_dt = ch.data_abertura or now_brazil_naive()
        if rows:
            first_dt = rows[0][5] or first_dt
            class _CA:
                def __init__(self, r):
                    self.id, self.nome_original, self.caminho_arquivo, self.mime_type, self.tamanho_bytes, self.data_upload = r
            anexos_abertura = [AnexoOut.model_validate(_CA(r)) for r in rows]
        # Item 1: Aberto em
        items.append(HistoricoItem(
            t=first_dt,
            tipo="abertura",
            label="Aberto em",
            anexos=anexos_abertura,
            usuario_nome="Sistema",
            usuario_email=None,
        ))
        # Item 2: Descrição (se houver)
        if ch.descricao:
            items.append(HistoricoItem(
                t=first_dt,
                tipo="abertura",
                label=f"Descrição: \n{ch.descricao}",
                anexos=None,
                usuario_nome="Sistema",
                usuario_email=None,
            ))
        try:
            Notification.__table__.create(bind=engine, checkfirst=True)
            HistoricoStatus.__table__.create(bind=engine, checkfirst=True)
            # Priorize historico_status for status events
            hs_rows = db.query(HistoricoStatus).filter(HistoricoStatus.chamado_id == chamado_id).order_by(HistoricoStatus.criado_em.asc()).all()
            for r in hs_rows:
                usuario = None
                if r.usuario_id:
                    usuario = db.query(User).filter(User.id == r.usuario_id).first()
                items.append(HistoricoItem(
                    t=r.criado_em or now_brazil_naive(),
                    tipo="status",
                    label=f"{r.status_anterior or 'Aberto'} → {r.status_novo}",
                    anexos=None,
                    usuario_id=r.usuario_id,
                    usuario_nome=f"{usuario.nome} {usuario.sobrenome}" if usuario else None,
                    usuario_email=usuario.email if usuario else None,
                ))
            # Fallback somente se não houver historico_status
            if not hs_rows:
                notas = db.query(Notification).filter(
                    Notification.recurso == "chamado",
                    Notification.recurso_id == chamado_id,
                ).order_by(Notification.criado_em.asc()).all()
                for n in notas:
                    if n.acao == "status":
                        usuario = None
                        if n.usuario_id:
                            usuario = db.query(User).filter(User.id == n.usuario_id).first()
                        items.append(HistoricoItem(
                            t=n.criado_em or now_brazil_naive(),
                            tipo="status",
                            label=n.mensagem or "Status atualizado",
                            anexos=None,
                            usuario_id=n.usuario_id,
                            usuario_nome=f"{usuario.nome} {usuario.sobrenome}" if usuario else None,
                            usuario_email=usuario.email if usuario else None,
                        ))
        except Exception:
            pass
        # histórico (historico_tickets via ORM) - ignora se tabela não existir
        try:
            hs = db.query(HistoricoTicket).filter(HistoricoTicket.chamado_id == chamado_id).order_by(HistoricoTicket.data_envio.asc()).all()
        except Exception:
            hs = []
        for h in hs:
            anexos_ticket = []
            try:
                from datetime import timedelta
                start = (h.data_envio or now_brazil_naive()) - timedelta(minutes=3)
                end = (h.data_envio or now_brazil_naive()) + timedelta(minutes=3)
                sql_ta = _select_anexo_query("ticket_anexos") + " WHERE chamado_id=:i"
                tas = db.execute(text(sql_ta), {"i": chamado_id}).fetchall()
                for ta in tas:
                    dt = ta[5]
                    if dt and start <= dt <= end:
                        class _A:
                            id, nome_original, caminho_arquivo, mime_type, tamanho_bytes, data_upload = ta
                        anexos_ticket.append(_A())
            except Exception:
                pass
            usuario = None
            if h.usuario_id:
                usuario = db.query(User).filter(User.id == h.usuario_id).first()
            items.append(HistoricoItem(
                t=h.data_envio or now_brazil_naive(),
                tipo="ticket",
                label=f"{h.assunto}",
                anexos=[AnexoOut.model_validate(a) for a in anexos_ticket] if anexos_ticket else None,
                usuario_id=h.usuario_id,
                usuario_nome=f"{usuario.nome} {usuario.sobrenome}" if usuario else None,
                usuario_email=usuario.email if usuario else None,
            ))
        items_sorted = sorted(items, key=lambda x: x.t)
        return HistoricoResponse(items=items_sorted)
    except HTTPException:
        raise
    except Exception:
        # Retorna o que foi possível montar para não quebrar o painel
        try:
            items_sorted = sorted(items, key=lambda x: x.t)
            return HistoricoResponse(items=items_sorted)
        except Exception:
            return HistoricoResponse(items=[])


@router.patch("/{chamado_id}/status", response_model=ChamadoOut)
def atualizar_status(chamado_id: int, payload: ChamadoStatusUpdate, db: Session = Depends(get_db)):
    try:
        novo = _normalize_status(payload.status)
        if novo not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Status inválido")
        ch = db.query(Chamado).filter(
            (Chamado.id == chamado_id) & (Chamado.deletado_em.is_(None))
        ).first()
        if not ch:
            raise HTTPException(status_code=404, detail="Chamado não encontrado")
        prev = ch.status or "Aberto"
        ch.status = novo
        if prev == "Aberto" and novo != "Aberto" and ch.data_primeira_resposta is None:
            ch.data_primeira_resposta = now_brazil_naive()
        if novo == "Concluído":
            ch.data_conclusao = now_brazil_naive()
        db.add(ch)
        db.commit()  # garante persistência do status antes dos logs
        db.refresh(ch)

        # DECREMENTAR CONTADOR DE HOJE SE CANCELADO
        if novo == "Cancelado" and prev != "Cancelado":
            from ti.services.cache_manager_incremental import ChamadosTodayCounter
            ChamadosTodayCounter.decrement(db, 1)

        try:
            # Sincroniza automaticamente com tabela de SLA
            _sincronizar_sla(db, ch, status_anterior=prev)
        except Exception as e:
            print(f"[SYNC SLA ERROR] {e}")
            db.rollback()

        try:
            Notification.__table__.create(bind=engine, checkfirst=True)
            HistoricoTicket.__table__.create(bind=engine, checkfirst=True)
            HistoricoStatus.__table__.create(bind=engine, checkfirst=True)

            # FECHAR HISTÓRICO ANTERIOR: Se o último status não tem data_fim, preencher
            agora = now_brazil_naive()
            try:
                ultimo_historico = db.query(HistoricoStatus).filter(
                    HistoricoStatus.chamado_id == ch.id
                ).order_by(HistoricoStatus.data_inicio.desc()).first()

                if ultimo_historico and not ultimo_historico.data_fim:
                    ultimo_historico.data_fim = agora
                    db.add(ultimo_historico)
                    db.commit()
            except Exception as e:
                print(f"[HISTORICO - Fechar anterior ERROR] {e}")
                import traceback
                traceback.print_exc()
                db.rollback()

            dados = json.dumps({
                "id": ch.id,
                "codigo": ch.codigo,
                "protocolo": ch.protocolo,
                "status": ch.status,
                "status_anterior": prev,
            }, ensure_ascii=False)
            n = Notification(
                tipo="chamado",
                titulo=f"Status atualizado: {ch.codigo}",
                mensagem=f"{prev} → {ch.status}",
                recurso="chamado",
                recurso_id=ch.id,
                acao="status",
                dados=dados,
            )
            db.add(n)
            # registrar em historico_status (única fonte de verdade)
            try:
                hs = HistoricoStatus(
                    chamado_id=ch.id,
                    usuario_id=None,
                    status=ch.status,
                    data_inicio=agora,
                    descricao=f"Migrado: {prev} → {ch.status}",
                    created_at=agora,
                    updated_at=agora,
                )
                print(f"[HISTORICO STATUS] Criando novo: chamado_id={ch.id}, status={ch.status}, data_inicio={agora}")
                db.add(hs)
                db.commit()
                print(f"[HISTORICO STATUS] Sucesso ao salvar registro")
            except Exception as e:
                print(f"[HISTORICO STATUS - Novo registro ERROR] {e}")
                import traceback
                traceback.print_exc()
                db.rollback()
            db.refresh(n)

            import anyio
            anyio.from_thread.run(sio.emit, "chamado:status", {"id": ch.id, "status": ch.status})
            anyio.from_thread.run(sio.emit, "notification:new", {
                "id": n.id,
                "tipo": n.tipo,
                "titulo": n.titulo,
                "mensagem": n.mensagem,
                "recurso": n.recurso,
                "recurso_id": n.recurso_id,
                "acao": n.acao,
                "dados": n.dados,
                "lido": n.lido,
                "criado_em": n.criado_em.isoformat() if n.criado_em else None,
            })

            # EMITE ATUALIZAÇÃO DE MÉTRICAS EM TEMPO REAL (quando status muda)
            from ti.services.cache_manager_incremental import IncrementalMetricsCache
            metricas = IncrementalMetricsCache.get_metrics(db)
            anyio.from_thread.run(sio.emit, "metrics:updated", {
                "sla_metrics": metricas,
                "timestamp": now_brazil_naive().isoformat(),
            })
        except Exception:
            db.rollback()
            pass

        # Enviar email de notificação de status atualizado
        try:
            print(f"[CHAMADOS] 📧 Status do chamado {ch.codigo} atualizado ({prev} → {ch.status}). Disparando email...")
            send_async(send_chamado_status, ch, prev)
            print(f"[CHAMADOS] ✅ send_async() chamado para send_chamado_status")
        except Exception as e:
            print(f"[CHAMADOS] ❌ ERRO ao enviar email: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

        db.refresh(ch)
        db.expunge(ch)
        return ch
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar status: {e}")


@router.post("/{chamado_id}/assign", response_model=ChamadoOut)
def atribuir_chamado(chamado_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        agent_id = payload.get("agent_id")
        if not agent_id:
            raise HTTPException(status_code=400, detail="agent_id é obrigatório")

        # Buscar o agente (usuário)
        agent = db.query(User).filter(User.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")

        # Buscar o chamado
        ch = db.query(Chamado).filter(
            (Chamado.id == chamado_id) & (Chamado.deletado_em.is_(None))
        ).first()
        if not ch:
            raise HTTPException(status_code=404, detail="Chamado não encontrado")

        # Atualizar a atribuição
        ch.status_assumido_por_id = agent_id
        ch.status_assumido_em = now_brazil_naive()
        db.add(ch)
        db.commit()
        db.refresh(ch)

        # Criar notificação
        try:
            Notification.__table__.create(bind=engine, checkfirst=True)
            dados = json.dumps({
                "id": ch.id,
                "codigo": ch.codigo,
                "agente_id": agent_id,
                "agente_nome": agent.nome,
            }, ensure_ascii=False)

            n = Notification(
                tipo="chamado",
                titulo=f"Chamado atribuído: {ch.codigo}",
                mensagem=f"Chamado {ch.protocolo} foi atribuído para {agent.nome}",
                recurso="chamado",
                recurso_id=chamado_id,
                acao="atribuido",
                dados=dados,
            )
            db.add(n)
            db.commit()
            db.refresh(n)
        except Exception as e:
            print(f"[ASSIGN] Erro ao criar notificação: {e}")

        return ch
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atribuir chamado: {e}")


@router.delete("/{chamado_id}")
def deletar_chamado(chamado_id: int, payload: ChamadoDeleteRequest = Body(...), db: Session = Depends(get_db)):
    try:
        # Validar usuário e senha
        user = db.query(User).filter(User.email == payload.email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        from werkzeug.security import check_password_hash as _chk
        if not _chk(user.senha_hash, payload.senha):
            raise HTTPException(status_code=401, detail="Senha inválida")

        # Buscar o chamado
        ch = db.query(Chamado).filter(
            (Chamado.id == chamado_id) & (Chamado.deletado_em.is_(None))
        ).first()
        if not ch:
            raise HTTPException(status_code=404, detail="Chamado não encontrado")

        print(f"[SOFT DELETE] Iniciando soft delete do chamado {chamado_id}")

        # Guardar informações do chamado
        chamado_info = {
            'id': ch.id,
            'codigo': ch.codigo,
            'protocolo': ch.protocolo,
            'status': ch.status,
        }

        # Soft delete: marcar como deletado
        agora = now_brazil_naive()
        ch.deletado_em = agora
        db.add(ch)
        db.commit()
        db.refresh(ch)

        print(f"[SOFT DELETE] Chamado {chamado_id} marcado como deletado")

        # Decrementar contador se o chamado não estava cancelado
        if chamado_info['status'] != "Cancelado":
            try:
                from ti.services.cache_manager_incremental import ChamadosTodayCounter
                ChamadosTodayCounter.decrement(db, 1)
                print(f"[SOFT DELETE] Contador decrementado")
            except Exception as e:
                print(f"[SOFT DELETE] Erro ao decrementar contador: {e}")

        # Invalidar cache de SLA relacionado ao chamado
        try:
            from ti.services.sla_cache import SLACacheManager
            SLACacheManager.invalidate_by_chamado(db, chamado_id)
            print(f"[SOFT DELETE] Cache de SLA invalidado")
        except Exception as e:
            print(f"[SOFT DELETE] Erro ao invalidar cache: {e}")

        # Criar notificação de exclusão
        try:
            Notification.__table__.create(bind=engine, checkfirst=True)
            dados = json.dumps({
                "id": chamado_info['id'],
                "codigo": chamado_info['codigo'],
                "protocolo": chamado_info['protocolo'],
            }, ensure_ascii=False)

            n = Notification(
                tipo="chamado",
                titulo=f"Chamado excluído: {chamado_info['codigo']}",
                mensagem=f"Chamado {chamado_info['protocolo']} foi removido da visualização",
                recurso="chamado",
                recurso_id=chamado_id,
                acao="excluido",
                dados=dados,
            )
            db.add(n)
            db.commit()
            db.refresh(n)

            # Emitir eventos WebSocket
            import anyio
            anyio.from_thread.run(sio.emit, "chamado:deleted", {
                "id": chamado_id,
                "codigo": chamado_info['codigo'],
                "protocolo": chamado_info['protocolo'],
            })
            anyio.from_thread.run(sio.emit, "notification:new", {
                "id": n.id,
                "tipo": n.tipo,
                "titulo": n.titulo,
                "mensagem": n.mensagem,
                "recurso": n.recurso,
                "recurso_id": n.recurso_id,
                "acao": n.acao,
                "dados": n.dados,
                "lido": n.lido,
                "criado_em": n.criado_em.isoformat() if n.criado_em else None,
            })

            # Emitir atualização de métricas
            from ti.services.cache_manager_incremental import IncrementalMetricsCache
            metricas = IncrementalMetricsCache.get_metrics(db)
            anyio.from_thread.run(sio.emit, "metrics:updated", {
                "sla_metrics": metricas,
                "timestamp": now_brazil_naive().isoformat(),
            })

            print(f"[SOFT DELETE] Notificação e eventos WebSocket emitidos")
        except Exception as e:
            print(f"[SOFT DELETE] Erro ao criar notificação/WebSocket: {e}")
            # Não falhar a operação por causa disso

        return {
            "ok": True,
            "message": f"Chamado {chamado_info['codigo']} excluído com sucesso",
            "detalhes": {
                "chamado_id": chamado_id,
                "codigo": chamado_info['codigo'],
                "protocolo": chamado_info['protocolo'],
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[SOFT DELETE] ERRO GERAL: {e}")
        print(f"[SOFT DELETE] TRACEBACK: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir chamado: {e}")
