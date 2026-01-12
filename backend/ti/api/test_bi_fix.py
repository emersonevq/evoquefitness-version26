"""
Endpoint de teste/diagnóstico para BI subcategories
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.db import get_db
from ti.models import User
import json

router = APIRouter(prefix="/api/test", tags=["test"])


@router.post("/bi-fix/{user_id}")
def test_bi_fix(user_id: int, dashboard_ids: list[str], db: Session = Depends(get_db)):
    """
    Teste de VERDADE - salva as permissões e verifica se foram salvos
    """
    print(f"\n\n{'='*80}")
    print(f"[TEST-BI-FIX] INICIANDO TESTE DE VERDADE")
    print(f"[TEST-BI-FIX] User ID: {user_id}")
    print(f"[TEST-BI-FIX] Dashboard IDs a salvar: {dashboard_ids}")
    print(f"{'='*80}\n")
    
    try:
        # 1. Buscar usuário
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": f"User {user_id} not found"}
        
        print(f"[TEST-BI-FIX] 1️⃣  Usuário encontrado: {user.usuario}")
        
        # 2. Ver o que há atualmente
        print(f"[TEST-BI-FIX] 2️⃣  Estado ANTES de salvar:")
        print(f"[TEST-BI-FIX]     _bi_subcategories = {repr(user._bi_subcategories)}")
        
        # 3. Converter para JSON e DIRETO NO USUARIO
        json_str = json.dumps(dashboard_ids)
        print(f"[TEST-BI-FIX] 3️⃣  JSON a salvar: {json_str}")
        print(f"[TEST-BI-FIX]     Tipo: {type(json_str)}")
        
        # 4. Setar DIRETO
        user._bi_subcategories = json_str
        print(f"[TEST-BI-FIX] 4️⃣  Setado na memória: {repr(user._bi_subcategories)}")
        
        # 5. Commit
        print(f"[TEST-BI-FIX] 5️⃣  Commitando...")
        db.commit()
        print(f"[TEST-BI-FIX]     ✅ Commit feito")
        
        # 6. Refresh
        print(f"[TEST-BI-FIX] 6️⃣  Refetch do banco...")
        db.refresh(user)
        print(f"[TEST-BI-FIX]     ✅ Refetch feito")
        
        # 7. Ver o que tem no banco agora
        print(f"[TEST-BI-FIX] 7️⃣  Estado DEPOIS de salvar:")
        print(f"[TEST-BI-FIX]     _bi_subcategories = {repr(user._bi_subcategories)}")
        
        # 8. Tentar parsear
        parsed = None
        if user._bi_subcategories:
            try:
                parsed = json.loads(user._bi_subcategories)
                print(f"[TEST-BI-FIX] 8️⃣  Parseado com sucesso: {parsed}")
            except Exception as e:
                print(f"[TEST-BI-FIX] 8️⃣  ❌ ERRO ao parsear: {e}")
        
        # 9. Agora fazer uma requisição GET para verificar
        print(f"[TEST-BI-FIX] 9️⃣  Fazendo GET /api/usuarios/{user_id}...")
        # Não conseguimos fazer requisição aqui, mas direto consultando o banco
        user_check = db.query(User).filter(User.id == user_id).first()
        print(f"[TEST-BI-FIX]     _bi_subcategories no banco: {repr(user_check._bi_subcategories)}")
        
        print(f"\n[TEST-BI-FIX] ✅ TESTE COMPLETO")
        print(f"{'='*80}\n")
        
        return {
            "status": "ok",
            "user_id": user_id,
            "saved_to_db": repr(user._bi_subcategories),
            "parsed": parsed,
            "message": "Salvo com sucesso. Agora faça login e verifique se as permissões aparecem."
        }
        
    except Exception as e:
        print(f"[TEST-BI-FIX] ❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/bi-check/{user_id}")
def test_bi_check(user_id: int, db: Session = Depends(get_db)):
    """
    Simples verificação do estado atual no banco
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": f"User {user_id} not found"}
        
        parsed = None
        if user._bi_subcategories:
            try:
                parsed = json.loads(user._bi_subcategories)
            except:
                parsed = "ERROR_PARSING"
        
        return {
            "user_id": user.id,
            "usuario": user.usuario,
            "email": user.email,
            "_bi_subcategories_raw": user._bi_subcategories,
            "_bi_subcategories_parsed": parsed,
        }
    except Exception as e:
        return {"error": str(e)}
