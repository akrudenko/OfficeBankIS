import tkinter as tk
from tkinter import ttk, messagebox
from services.auth_service import login

class LoginWindow(ttk.Frame):
    def __init__(self, master, db, on_login):
        super().__init__(master, padding=12)
        self.db = db
        self.on_login = on_login

        ttk.Label(self, text="OfficeBankIS", font=("Segoe UI", 16, "bold")).pack(pady=(0, 10))

        self.var_login = tk.StringVar()
        self.var_pass = tk.StringVar()

        ttk.Label(self, text="Логин").pack(anchor="w")
        ttk.Entry(self, textvariable=self.var_login, width=30).pack(fill="x", pady=(0,6))

        ttk.Label(self, text="Пароль").pack(anchor="w")
        ttk.Entry(self, textvariable=self.var_pass, width=30, show="*").pack(fill="x", pady=(0,10))

        ttk.Button(self, text="Войти", command=self._do_login).pack()

    def _do_login(self):
        lg = self.var_login.get().strip()
        pw = self.var_pass.get()
        if not lg or not pw:
            messagebox.showwarning("Вход", "Введите логин и пароль.")
            return
        user = login(self.db, lg, pw)
        if not user:
            messagebox.showerror("Вход", "Неверный логин или пароль.")
            return
        self.on_login(user)
