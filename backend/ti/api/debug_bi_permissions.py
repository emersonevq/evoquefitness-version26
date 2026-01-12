"""
Debug endpoints for BI permissions and subcategories.
Helps trace issues with permission persistence and loading.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.db import get_db
from ti.models import User
import json

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/bi-permissions/{user_id}")
def debug_bi_permissions_for_user(user_id: int, db: Session = Depends(get_db)):
    """
    DEBUG ENDPOINT: Check BI permissions for a specific user
    Shows:
    - Raw database value of _bi_subcategories
    - Parsed JSON value
    - What will be returned to frontend
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": f"User {user_id} not found"}

        # Get raw value from database
        raw_value = getattr(user, "_bi_subcategories", None)
        
        # Try to parse it
        parsed_value = None
        parse_error = None
        if raw_value:
            try:
                parsed_value = json.loads(raw_value)
            except Exception as e:
                parse_error = str(e)

        return {
            "user_id": user.id,
            "usuario": user.usuario,
            "email": user.email,
            "name": f"{user.nome} {user.sobrenome}",
            "_bi_subcategories_raw_from_db": raw_value,
            "_bi_subcategories_raw_type": type(raw_value).__name__,
            "_bi_subcategories_raw_is_null": raw_value is None,
            "_bi_subcategories_raw_is_empty": raw_value == "",
            "_bi_subcategories_parsed": parsed_value,
            "parse_error": parse_error,
            "note": "Check the _bi_subcategories_raw_from_db field - it should be a JSON string like '[\"dash1\", \"dash2\"]'"
        }
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/all-users-bi-permissions")
def debug_all_users_bi_permissions(db: Session = Depends(get_db)):
    """
    DEBUG ENDPOINT: Check BI permissions for ALL users
    Useful for identifying pattern of issues
    """
    try:
        users = db.query(User).all()
        
        result = {
            "total_users": len(users),
            "users": []
        }
        
        for user in users:
            raw_value = getattr(user, "_bi_subcategories", None)
            parsed_value = None
            parse_error = None
            
            if raw_value:
                try:
                    parsed_value = json.loads(raw_value)
                except Exception as e:
                    parse_error = str(e)
            
            result["users"].append({
                "user_id": user.id,
                "usuario": user.usuario,
                "email": user.email,
                "_bi_subcategories_raw": raw_value,
                "_bi_subcategories_parsed": parsed_value,
                "parse_error": parse_error
            })
        
        return result
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.post("/set-bi-permissions/{user_id}")
def debug_set_bi_permissions(user_id: int, dashboard_ids: list[str], db: Session = Depends(get_db)):
    """
    DEBUG ENDPOINT: Manually set BI permissions for a user
    Used for testing the save/load flow
    """
    try:
        from ti.services.users import _set_bi_subcategories
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        print(f"\n[DEBUG] Setting BI permissions for user {user_id}")
        print(f"[DEBUG] Dashboard IDs to set: {dashboard_ids}")
        
        # Call the same function that the API uses
        _set_bi_subcategories(user, dashboard_ids)
        
        # Commit the changes
        db.commit()
        db.refresh(user)
        
        # Verify what was saved
        raw_value = getattr(user, "_bi_subcategories", None)
        parsed_value = None
        if raw_value:
            try:
                parsed_value = json.loads(raw_value)
            except Exception as e:
                parsed_value = f"ERROR PARSING: {e}"
        
        return {
            "success": True,
            "user_id": user.id,
            "dashboard_ids_requested": dashboard_ids,
            "_bi_subcategories_raw_after_save": raw_value,
            "_bi_subcategories_parsed_after_save": parsed_value,
            "note": "After this, you should call /api/usuarios/{user_id} and verify it returns the same value"
        }
    except Exception as e:
        db.rollback()
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.post("/refresh-user/{user_id}")
def debug_refresh_user(user_id: int, db: Session = Depends(get_db)):
    """
    DEBUG ENDPOINT: Trigger a permission refresh for a user
    Simulates what happens when admin updates permissions
    """
    try:
        from core.realtime import emit_refresh_sync
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": f"User {user_id} not found"}
        
        print(f"\n[DEBUG] Emitting refresh sync for user {user_id}")
        try:
            emit_refresh_sync(user_id)
            return {
                "success": True,
                "user_id": user_id,
                "message": "Refresh event sent via Socket.IO"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "note": "Socket.IO emit failed - but user should refresh on next API call"
            }
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }
