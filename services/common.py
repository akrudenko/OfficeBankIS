from db import DB

def get_id_by_code(db: DB, table: str, code_col: str, id_col: str, code: str) -> int:
    row = db.fetchone(f"SELECT {id_col} AS id FROM dbo.{table} WHERE {code_col} = ?", (code,))
    if not row:
        raise ValueError(f"Не найдено {code} в {table}.{code_col}")
    return int(row.id)

def get_user_roles(db: DB, user_id: int) -> set[str]:
    rows = db.fetchall("""
        SELECT r.RoleCode
        FROM dbo.UserRoles ur
        JOIN dbo.Roles r ON r.RoleID = ur.RoleID
        WHERE ur.UserID = ?
    """, (user_id,))
    return {str(r.RoleCode) for r in rows}

def is_facility_or_admin(roles: set[str]) -> bool:
    return ("FAC" in roles) or ("ADM" in roles)
