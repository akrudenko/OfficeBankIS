from dataclasses import dataclass
from typing import Optional
from db import DB
from security import verify_password
from services.common import get_user_roles

@dataclass
class AuthUser:
    user_id: int
    employee_id: int
    login: str
    full_name: str
    roles: set[str]

def login(db: DB, login_text: str, password: str) -> Optional[AuthUser]:
    row = db.fetchone("""
        SELECT u.UserID, u.EmployeeID, u.Login, u.PasswordHash, e.FullName
        FROM dbo.UserAccounts u
        JOIN dbo.Employees e ON e.EmployeeID = u.EmployeeID
        WHERE u.Login = ? AND u.IsLocked = 0
    """, (login_text,))
    if not row:
        return None
    if not verify_password(password, row.PasswordHash):
        return None
    roles = get_user_roles(db, int(row.UserID))
    return AuthUser(int(row.UserID), int(row.EmployeeID), str(row.Login), str(row.FullName), roles)
