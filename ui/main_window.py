import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from services.resource_service import list_resources
from services.booking_service import (
    create_booking, list_bookings_for_period, cancel_booking,
    list_pending_approvals, decide_approval
)
from services.common import is_facility_or_admin
from services.analytics_service import bookings_df, utilization_by_day, top_resources
from reports.report_service import save_csv, save_util_chart, save_docx_summary

class MainWindow(ttk.Frame):
    def __init__(self, master, db, user):
        super().__init__(master, padding=8)
        self.db = db
        self.user = user
        ttk.Label(self, text=f"{user.full_name} ({user.login}) роли: {', '.join(sorted(user.roles))}",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0,6))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.util_df = pd.DataFrame()
        self.top_df = pd.DataFrame()

        self._tab_resources()
        self._tab_booking()
        self._tab_approvals()
        self._tab_analytics()

    def _tab_resources(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Ресурсы")
        cols=("id","kind","name","zone","floor","status","cap","hot")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings", height=14)
        heads=[("id","ID",60),("kind","Тип",90),("name","Название",220),("zone","Зона",180),
               ("floor","Этаж",60),("status","Статус",90),("cap","Вмест.",70),("hot","HotDesk",80)]
        for c,t,w in heads:
            self.tree.heading(c,text=t); self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both", expand=True)
        ttk.Button(tab, text="Обновить", command=self._refresh_resources).pack(anchor="w", pady=6)
        self._refresh_resources()

    def _refresh_resources(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in list_resources(self.db):
            kind = "Переговорная" if r.kind=="R" else "Раб. место"
            self.tree.insert("", "end", values=(r.resource_id, kind, r.display_name, r.zone_name,
                                                r.floor_no or "", r.status_code, r.capacity or "",
                                                ("да" if r.is_hotdesk else "нет") if r.is_hotdesk is not None else ""))

    def _tab_booking(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Бронирование")

        form = ttk.LabelFrame(tab, text="Создать бронь", padding=8)
        form.pack(fill="x")

        self.v_rid=tk.StringVar()
        self.v_s=tk.StringVar()
        self.v_e=tk.StringVar()
        self.v_title=tk.StringVar()
        self.v_notes=tk.StringVar()
        self.v_part=tk.StringVar()

        row1=ttk.Frame(form); row1.pack(fill="x", pady=3)
        ttk.Label(row1,text="ResourceID").pack(side="left")
        ttk.Entry(row1,textvariable=self.v_rid,width=10).pack(side="left", padx=6)
        ttk.Label(row1,text="Start YYYY-MM-DD HH:MM").pack(side="left")
        ttk.Entry(row1,textvariable=self.v_s,width=18).pack(side="left", padx=6)
        ttk.Label(row1,text="End").pack(side="left")
        ttk.Entry(row1,textvariable=self.v_e,width=18).pack(side="left", padx=6)

        row2=ttk.Frame(form); row2.pack(fill="x", pady=3)
        ttk.Label(row2,text="Тема").pack(side="left")
        ttk.Entry(row2,textvariable=self.v_title,width=40).pack(side="left", padx=6)
        ttk.Label(row2,text="Участников").pack(side="left")
        ttk.Entry(row2,textvariable=self.v_part,width=6).pack(side="left", padx=6)

        row3=ttk.Frame(form); row3.pack(fill="x", pady=3)
        ttk.Label(row3,text="Комментарий").pack(side="left")
        ttk.Entry(row3,textvariable=self.v_notes,width=60).pack(side="left", padx=6)

        ttk.Button(form, text="Создать", command=self._create_booking).pack(pady=6)

        lf = ttk.LabelFrame(tab, text="Брони (следующие дни)", padding=8)
        lf.pack(fill="both", expand=True, pady=8)
        top=ttk.Frame(lf); top.pack(fill="x")
        self.v_days=tk.StringVar(value="7")
        ttk.Label(top,text="Дней").pack(side="left")
        ttk.Entry(top,textvariable=self.v_days,width=6).pack(side="left", padx=6)
        ttk.Button(top,text="Показать", command=self._refresh_bookings).pack(side="left", padx=6)
        ttk.Button(top,text="Отменить выбранную", command=self._cancel_booking).pack(side="left", padx=6)

        cols=("id","res","kind","start","end","status","by")
        self.tree_b = ttk.Treeview(lf, columns=cols, show="headings", height=10)
        for c,t,w in [("id","BookingID",80),("res","Ресурс",220),("kind","Тип",90),
                      ("start","Начало",140),("end","Оконч.",140),("status","Статус",90),("by","Кто",90)]:
            self.tree_b.heading(c,text=t); self.tree_b.column(c,width=w,anchor="w")
        self.tree_b.pack(fill="both", expand=True)

        now=datetime.now().replace(second=0, microsecond=0)
        self.v_s.set(now.strftime("%Y-%m-%d %H:%M"))
        self.v_e.set((now+timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
        self._refresh_bookings()

    def _parse_dt(self, s): return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")

    def _create_booking(self):
        try:
            rid=int(self.v_rid.get())
            s=self._parse_dt(self.v_s.get())
            e=self._parse_dt(self.v_e.get())
            title=self.v_title.get().strip()
            notes=self.v_notes.get().strip()
            part=self.v_part.get().strip()
            participants=int(part) if part else None
            res=create_booking(self.db, rid, self.user.user_id, s, e, title, notes, participants)
            (messagebox.showinfo if res.ok else messagebox.showwarning)("Бронирование", res.message)
            if res.ok: self._refresh_bookings()
        except Exception as ex:
            messagebox.showerror("Ошибка", str(ex))

    def _refresh_bookings(self):
        for i in self.tree_b.get_children(): self.tree_b.delete(i)
        days=int(self.v_days.get())
        start=datetime.now()
        end=start+timedelta(days=days)
        for r in list_bookings_for_period(self.db, start, end):
            kind="Переговорная" if str(r.ResourceKind)=="R" else "Раб. место"
            self.tree_b.insert("", "end", values=(int(r.BookingID), str(r.DisplayName), kind,
                                                 str(r.StartAt)[:16], str(r.EndAt)[:16], str(r.StatusCode), str(r.RequestedBy)))

    def _cancel_booking(self):
        sel=self.tree_b.selection()
        if not sel:
            messagebox.showwarning("Отмена","Выберите бронь.")
            return
        bid=int(self.tree_b.item(sel[0],"values")[0])
        if messagebox.askyesno("Отмена", f"Отменить бронь #{bid}?"):
            cancel_booking(self.db, bid)
            self._refresh_bookings()

    def _tab_approvals(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Согласования")
        ttk.Label(tab, text="Только FAC/ADM").pack(anchor="w")

        cols=("aid","bid","res","start","end","by","status")
        self.tree_a = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c,t,w in [("aid","ApprovalID",90),("bid","BookingID",90),("res","Ресурс",240),
                      ("start","Начало",140),("end","Оконч.",140),("by","Кто",90),("status","Статус",90)]:
            self.tree_a.heading(c,text=t); self.tree_a.column(c,width=w,anchor="w")
        self.tree_a.pack(fill="both", expand=True, pady=6)

        btn=ttk.Frame(tab); btn.pack(fill="x")
        ttk.Button(btn,text="Обновить", command=self._refresh_approvals).pack(side="left")
        ttk.Button(btn,text="Одобрить", command=lambda: self._decide(True)).pack(side="left", padx=6)
        ttk.Button(btn,text="Отклонить", command=lambda: self._decide(False)).pack(side="left")

        self._refresh_approvals()

    def _refresh_approvals(self):
        for i in self.tree_a.get_children(): self.tree_a.delete(i)
        if not is_facility_or_admin(self.user.roles):
            return
        for r in list_pending_approvals(self.db, self.user.user_id):
            self.tree_a.insert("", "end", values=(int(r.ApprovalID), int(r.BookingID), str(r.DisplayName),
                                                 str(r.StartAt)[:16], str(r.EndAt)[:16], str(r.RequestedBy), str(r.ApprovalStatus)))

    def _decide(self, approve: bool):
        if not is_facility_or_admin(self.user.roles):
            messagebox.showwarning("Согласования","Нет прав.")
            return
        sel=self.tree_a.selection()
        if not sel:
            messagebox.showwarning("Согласования","Выберите заявку.")
            return
        aid=int(self.tree_a.item(sel[0],"values")[0])
        decide_approval(self.db, aid, approve)
        self._refresh_approvals()
        self._refresh_bookings()

    def _tab_analytics(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Аналитика/Отчёты")

        self.va_s=tk.StringVar()
        self.va_e=tk.StringVar()
        now=datetime.now().replace(second=0, microsecond=0)
        self.va_s.set((now-timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))
        self.va_e.set(now.strftime("%Y-%m-%d %H:%M"))

        frm=ttk.LabelFrame(tab, text="Период", padding=8); frm.pack(fill="x")
        row=ttk.Frame(frm); row.pack(fill="x", pady=3)
        ttk.Label(row,text="Start").pack(side="left")
        ttk.Entry(row,textvariable=self.va_s,width=18).pack(side="left", padx=6)
        ttk.Label(row,text="End").pack(side="left")
        ttk.Entry(row,textvariable=self.va_e,width=18).pack(side="left", padx=6)
        ttk.Button(row,text="Рассчитать", command=self._calc).pack(side="left", padx=10)

        row2=ttk.Frame(frm); row2.pack(fill="x", pady=3)
        ttk.Button(row2,text="Экспорт CSV", command=self._export_csv).pack(side="left")
        ttk.Button(row2,text="Отчёт DOCX", command=self._export_docx).pack(side="left", padx=6)

        self.txt=tk.Text(tab, height=14); self.txt.pack(fill="both", expand=True, pady=8)

    def _calc(self):
        s=self._parse_dt(self.va_s.get()); e=self._parse_dt(self.va_e.get())
        df=bookings_df(self.db, s, e)
        self.util_df=utilization_by_day(df, s, e)
        self.top_df=top_resources(df, 10)
        self.txt.delete("1.0","end")
        self.txt.insert("end", f"Броней (APPROVED/PENDING): {len(df)}\n\n")
        self.txt.insert("end", self.util_df.to_string(index=False)+"\n\n")
        self.txt.insert("end", self.top_df.to_string(index=False))

    def _export_csv(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        save_csv(self.util_df, Path(path))
        messagebox.showinfo("Экспорт","CSV сохранён.")

    def _export_docx(self):
        out=filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("DOCX","*.docx")])
        if not out: return
        s=self._parse_dt(self.va_s.get()); e=self._parse_dt(self.va_e.get())
        outp=Path(out)
        png=outp.with_suffix(".png")
        save_util_chart(self.util_df, png)
        save_docx_summary(s, e, self.util_df, self.top_df, png, outp)
        messagebox.showinfo("Отчёт","DOCX сформирован.")
