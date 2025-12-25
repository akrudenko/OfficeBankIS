import tkinter as tk
from tkinter import ttk, messagebox
from db import DB, init_db_check
from ui.login_window import LoginWindow
from ui.main_window import MainWindow

def main():
    try:
        db = DB.connect()
        init_db_check(db)
    except Exception as e:
        messagebox.showerror("Ошибка БД", str(e))
        return

    root = tk.Tk()
    root.title("OfficeBankIS")
    root.geometry("1000x680")
    try:
        ttk.Style(root).theme_use("clam")
    except Exception:
        pass

    container = ttk.Frame(root)
    container.pack(fill="both", expand=True)

    def on_login(user):
        for w in container.winfo_children():
            w.destroy()
        MainWindow(container, db, user).pack(fill="both", expand=True)

    LoginWindow(container, db, on_login).pack(fill="both", expand=True)

    def on_close():
        try:
            db.close()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
