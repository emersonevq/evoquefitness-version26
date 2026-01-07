#!/usr/bin/env python3
"""
Migration script to rename 'compras' sector to 'Portal Financeiro' for all users.

This fixes the issue where users had permissions for 'compras' but the system
expects 'Portal Financeiro'. Both the single 'setor' field and the '_setores' 
JSON array are updated.

Usage:
  python migrate_compras_to_financeiro.py
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ti.models.user import User
from core.db import SessionLocal, engine

def normalize_for_comparison(s: str) -> str:
    """Normalize string by removing accents and converting to lowercase."""
    if not isinstance(s, str):
        s = str(s)
    try:
        return (
            s.normalize("NFKD")
            .encode("ascii", "ignore")
            .decode("utf-8")
            .lower()
            .strip()
        )
    except Exception:
        return s.lower().strip()


def migrate_compras_to_financeiro() -> tuple[int, int]:
    """
    Migrate all users with 'compras' sector to 'Portal Financeiro'.
    
    Returns:
        (updated_count, total_affected_count)
    """
    db = SessionLocal()
    updated = 0
    total_affected = 0
    
    try:
        # Create table if needed
        User.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass
    
    try:
        users = db.query(User).all()
        
        for u in users:
            changed = False
            
            # Check single 'setor' field
            if u.setor:
                norm_setor = normalize_for_comparison(u.setor)
                if norm_setor == normalize_for_comparison("compras"):
                    print(f"[MIGRATE] User {u.id} ({u.usuario}): Updating setor '{u.setor}' -> 'Portal Financeiro'")
                    u.setor = "Portal Financeiro"
                    changed = True
                    total_affected += 1
            
            # Check '_setores' JSON array
            if u._setores:
                try:
                    arr = json.loads(u._setores)
                    new_arr = []
                    arr_changed = False
                    
                    for setor in arr:
                        norm = normalize_for_comparison(str(setor))
                        if norm == normalize_for_comparison("compras"):
                            new_arr.append("Portal Financeiro")
                            arr_changed = True
                            total_affected += 1
                            print(f"[MIGRATE] User {u.id} ({u.usuario}): Updating _setores '{setor}' -> 'Portal Financeiro'")
                        else:
                            new_arr.append(setor)
                    
                    if arr_changed:
                        u._setores = json.dumps(new_arr, ensure_ascii=False)
                        changed = True
                        
                except Exception as e:
                    # If JSON parsing fails, skip
                    print(f"[WARN] User {u.id}: Could not parse _setores JSON: {e}")
                    pass
            
            if changed:
                db.add(u)
                updated += 1
        
        if updated > 0:
            print(f"\n[MIGRATE] Committing {updated} user(s) with {total_affected} sector reference(s) updated...")
            db.commit()
            print(f"[MIGRATE] ✓ Migration complete!")
        else:
            print(f"[MIGRATE] No users with 'compras' sector found. Nothing to migrate.")
        
        return updated, total_affected
        
    except Exception as e:
        try:
            db.rollback()
        except:
            pass
        print(f"[ERROR] Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Migrating 'compras' sector to 'Portal Financeiro'")
    print("=" * 60)
    
    updated, total = migrate_compras_to_financeiro()
    
    print("=" * 60)
    print(f"Migration Summary:")
    print(f"  Users updated: {updated}")
    print(f"  Sector references updated: {total}")
    print("=" * 60)
