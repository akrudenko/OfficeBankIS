import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from db import DB
from security import hash_password

USERS = [
    ("ivanov", "Iv@nov123"),
    ("petrov", "Petr0v123"),
    ("sidorov", "S1d0r0v123"),
]

def main():
    db = DB.connect()
    try:
        for login, pw in USERS:
            db.execute("UPDATE dbo.UserAccounts SET PasswordHash=? WHERE Login=?", (hash_password(pw), login))
        db.commit()
        print("OK. Пароли обновлены:")
        for login, pw in USERS:
            print(f" - {login} / {pw}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
