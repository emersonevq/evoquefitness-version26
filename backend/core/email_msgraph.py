from __future__ import annotations
import os
import time
import json
import threading
from typing import List, Optional, Tuple, Dict, Any
from urllib import request, parse, error
import base64

# Try to import backend/env.py as module to support key=value configs
try:
    import env as _env  # type: ignore
except Exception:  # pragma: no cover - best effort import
    _env = None

# Read settings from env module or environment variables
CLIENT_ID = (_env.CLIENT_ID if _env and getattr(_env, "CLIENT_ID", None) else os.getenv("CLIENT_ID"))
CLIENT_SECRET = (_env.CLIENT_SECRET if _env and getattr(_env, "CLIENT_SECRET", None) else os.getenv("CLIENT_SECRET"))
TENANT_ID = (_env.TENANT_ID if _env and getattr(_env, "TENANT_ID", None) else os.getenv("TENANT_ID"))
USER_ID = (_env.USER_ID if _env and getattr(_env, "USER_ID", None) else os.getenv("USER_ID"))

EMAIL_TI = (_env.EMAIL_TI if _env and getattr(_env, "EMAIL_TI", None) else os.getenv("EMAIL_TI"))
EMAIL_SISTEMA = (_env.EMAIL_SISTEMA if _env and getattr(_env, "EMAIL_SISTEMA", None) else os.getenv("EMAIL_SISTEMA"))

_graph_token: Optional[Tuple[str, float]] = None  # (token, expiry_epoch)


def _have_graph_config() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and TENANT_ID and USER_ID)


def _get_graph_token() -> Optional[str]:
    global _graph_token
    if not _have_graph_config():
        return None
    now = time.time()
    if _graph_token and now < _graph_token[1] - 30:
        return _graph_token[0]
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": "https://graph.microsoft.com/.default",
    }).encode("utf-8")
    req = request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            token = payload.get("access_token")
            expires_in = int(payload.get("expires_in", 3600))
            if token:
                _graph_token = (token, now + expires_in)
                return token
    except error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8")
            print(f"[EMAIL] Graph token error: {e.code} {msg}")
        except Exception:
            print(f"[EMAIL] Graph token HTTPError: {e}")
    except Exception as e:
        print(f"[EMAIL] Graph token exception: {e}")
    return None


def _post_graph(path: str, payload: dict) -> bool:
    token = _get_graph_token()
    if not token:
        return False
    url = f"https://graph.microsoft.com/v1.0{path}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8") if resp else ""
            print(f"[EMAIL] Graph sendMail response: status={resp.status} body={body}")
            return 200 <= resp.status < 300 or resp.status == 202
    except error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8")
            print(f"[EMAIL] Graph sendMail error: {e.code} {msg}")
        except Exception:
            print(f"[EMAIL] Graph sendMail HTTPError: {e}")
    except Exception as e:
        print(f"[EMAIL] Graph sendMail exception: {e}")
    return False


def _recipients(addrs: List[str]) -> List[dict]:
    out = []
    for a in addrs:
        addr = (a or "").strip()
        if addr:
            out.append({"emailAddress": {"address": addr}})
    return out


def _format_dt(dt) -> str:
    try:
        from core.utils import now_brazil_naive
        if not dt:
            return ""
        # Ensure iso string nicely
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(dt) if dt else ""


def _escape(s: str) -> str:
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_chamado_table(ch) -> str:
    visita = _escape(ch.data_visita.strftime("%d/%m/%Y") if getattr(ch, "data_visita", None) else "-")
    internet = _escape(getattr(ch, "internet_item", None) or "-")
    descricao = _escape(getattr(ch, "descricao", None) or "").replace("\n", "<br>")
    abertura = _escape(_format_dt(getattr(ch, "data_abertura", None)))

    rows = [
        ("Código", _escape(ch.codigo)),
        ("Protocolo", _escape(ch.protocolo)),
        ("Status", _escape(ch.status)),
        ("Prioridade", _escape(ch.prioridade)),
        ("Solicitante", _escape(ch.solicitante)),
        ("Cargo", _escape(ch.cargo)),
        ("Telefone", _escape(ch.telefone)),
        ("E-mail", _escape(ch.email)),
        ("Unidade", _escape(ch.unidade)),
        ("Problema", _escape(ch.problema)),
        ("Item de Internet", internet),
        ("Data de Visita", visita),
        ("Aberto em", abertura),
    ]

    logo_url = "https://images.totalpass.com/public/1280x720/czM6Ly90cC1pbWFnZS1hZG1pbi1wcm9kL2d5bXMva2g2OHF6OWNuajloN2lkdnhzcHhhdWx4emFhbWEzYnc3MGx5cDRzZ3p5aTlpZGM0OHRvYnk0YW56azRk"
    portal_url = os.getenv("PORTAL_URL", "https://academiaevoque.com.br")

    html = []
    # Preheader (hidden) for Gmail and others
    preheader = f"Seu chamado {ch.codigo} foi registrado — protocolo {ch.protocolo}."
    html.append(f'<span style="display:none!important;visibility:hidden;mso-hide:all;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden">{_escape(preheader)}</span>')

    html.append('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f6fb;padding:24px 0">')
    html.append('<tr><td align="center">')
    html.append('<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="background:#ffffff;border-collapse:collapse">')
    # Header
    html.append('<tr><td style="background:linear-gradient(90deg,#ff7a00,#ff4500);padding:18px 24px;color:#fff;font-family:Arial,Helvetica,sans-serif">')
    html.append('<table role="presentation" width="100%"><tr><td valign="middle" style="width:56px">')
    html.append(f'<img src="{logo_url}" width="48" height="48" alt="Evoque" style="display:block;border:0;outline:none;text-decoration:none;border-radius:6px"/>')
    html.append('</td><td valign="middle" style="padding-left:12px">')
    html.append(f'<div style="font-size:16px;font-weight:700">Evoque Fitness</div>')
    html.append(f'<div style="font-size:13px;opacity:0.95">Chamado {_escape(ch.codigo)}</div>')
    html.append('</td></tr></table>')
    html.append('</td></tr>')
    # Body intro
    html.append('<tr><td style="padding:20px 24px;font-family:Arial,Helvetica,sans-serif;color:#000000;font-size:14px;line-height:20px">')
    html.append(f'<p style="margin:0 0 12px">Olá <strong>{_escape(ch.solicitante)}</strong>,</p>')
    html.append('<p style="margin:0 0 14px;color:#222222">Recebemos seu chamado. Abaixo estão os detalhes registrados:</p>')
    # Details table
    html.append('<table role="presentation" width="100%" cellpadding="8" cellspacing="0" style="border-collapse:separate;border-spacing:8px 8px">')
    for k, v in rows:
        html.append('<tr>')
        html.append(f'<td width="35%" style="background:#f8fafc;border:1px solid #eef2f7;border-radius:6px;font-weight:700;color:#000000;vertical-align:top">{k}</td>')
        html.append(f'<td style="background:#ffffff;border:1px solid #eef2f7;border-radius:6px;color:#222222;vertical-align:top">{v or "-"}</td>')
        html.append('</tr>')
    html.append('</table>')
    if descricao:
        html.append('<div style="margin-top:12px">')
        html.append('<div style="font-weight:700;color:#000000;margin-bottom:6px">Descrição</div>')
        html.append(f'<div style="color:#222222;padding:12px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px">{descricao}</div>')
        html.append('</div>')
    # CTA
    html.append('<div style="margin-top:18px;display:block">')
    html.append(f'<a href="{portal_url}" style="display:inline-block;padding:12px 18px;background:#000000;color:#ffffff;border-radius:6px;text-decoration:none;font-weight:700">Ver chamado</a>')
    html.append('<div style="display:inline-block;margin-left:10px;color:#555555;font-size:13px;vertical-align:middle">Se precisar, responda pelo portal ou contate ti@academiaevoque.com.br</div>')
    html.append('</div>')

    html.append('</td></tr>')
    # Footer
    html.append('<tr><td style="padding:14px 24px;background:#fbfdff;border-top:1px solid #eef3fb;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#94a3b8">')
    html.append('Este é um e‑mail automático enviado pelo sistema de chamados da Evoque Fitness.')
    html.append('</td></tr>')

    html.append('</table>')
    html.append('</td></tr>')
    html.append('</table>')

    return "".join(html)


def build_email_chamado_aberto(ch) -> Tuple[str, str]:
    subject = f"[Evoque TI] Chamado {ch.codigo} aberto (Protocolo {ch.protocolo})"
    body = _build_chamado_table(ch)
    # plain text fallback
    text = f"Seu chamado {ch.codigo} foi criado. Protocolo: {ch.protocolo}. Status: {ch.status}."
    return subject, body


def build_email_status_atualizado(ch, status_anterior: str) -> Tuple[str, str]:
    subject = f"[Evoque TI] Status do chamado {ch.codigo}: {status_anterior} → {ch.status}"
    body = []
    body.append('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f6fb;padding:24px 0">')
    body.append('<tr><td align="center">')
    body.append('<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="background:#ffffff;border-collapse:collapse">')
    body.append('<tr><td style="background:linear-gradient(90deg,#ff7a00,#ff4500);padding:16px;color:#fff;border-radius:8px 8px 0 0;font-weight:700;font-family:Arial,Helvetica,sans-serif">')
    body.append(f'Atualização de status — Chamado {_escape(ch.codigo)}')
    body.append('</td></tr>')
    body.append('<tr><td style="background:#fff;padding:18px;border:1px solid #e6e9ef;border-top:none;color:#102a43;font-family:Arial,Helvetica,sans-serif">')
    body.append(f'<p style="margin:0 0 10px">Olá <strong>{_escape(ch.solicitante)}</strong>,</p>')
    body.append(f'<p style="margin:0 0 12px;color:#222222">O status do seu chamado foi atualizado de <strong>{_escape(status_anterior)}</strong> para <strong>{_escape(ch.status)}</strong>.</p>')
    body.append(_build_chamado_table(ch))
    body.append('<div style="margin-top:14px;color:#555555;font-size:13px">Se desejar mais detalhes, acesse o portal.</div>')
    body.append('</td></tr>')
    body.append('</table>')
    body.append('</td></tr>')
    body.append('</table>')
    return subject, "".join(body)


def send_mail(subject: str, html_body: str, to: List[str], cc: Optional[List[str]] = None, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
    if not _have_graph_config():
        print("[EMAIL] Graph configuration missing; skipping send.")
        return False
    to_list = _recipients(to)
    cc_list = _recipients(cc or [])
    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": to_list,
        },
        "saveToSentItems": True,
    }
    if cc_list:
        message["message"]["ccRecipients"] = cc_list
    # Attachments must be a list of microsoft.graph.fileAttachment objects with base64 content
    if attachments:
        # Ensure structure
        attach_list = []
        for a in attachments:
            # expect dict with name, contentType, contentBytes (base64 string)
            name = a.get("name")
            contentType = a.get("contentType") or a.get("mime") or "application/octet-stream"
            contentBytes = a.get("contentBytes") or a.get("content")
            if not name or not contentBytes:
                continue
            attach_list.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": contentType,
                "contentBytes": contentBytes,
            })
        if attach_list:
            message["message"]["attachments"] = attach_list
    path = f"/users/{USER_ID}/sendMail"
    return _post_graph(path, message)


def send_async(func, *args, **kwargs) -> None:
    def _runner():
        try:
            func(*args, **kwargs)
        except Exception as e:  # pragma: no cover
            print(f"[EMAIL] async error: {e}")
    threading.Thread(target=_runner, daemon=True).start()


def send_chamado_abertura(ch, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
    subject, html = build_email_chamado_aberto(ch)
    cc = []
    if EMAIL_TI:
        cc.append(str(EMAIL_TI))
    return send_mail(subject, html, to=[str(ch.email)], cc=cc, attachments=attachments)


def send_chamado_status(ch, status_anterior: str, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
    subject, html = build_email_status_atualizado(ch, status_anterior)
    cc = []
    if EMAIL_TI:
        cc.append(str(EMAIL_TI))
    return send_mail(subject, html, to=[str(ch.email)], cc=cc, attachments=attachments)
