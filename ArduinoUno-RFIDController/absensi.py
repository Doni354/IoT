"""
Absensi RFID RC522 – Aplikasi GUI Python (Tkinter)
Fitur:
- Baca UID dari Arduino (via pyserial) dalam thread terpisah (Queue -> UI)
- Tampilkan UID terakhir terdeteksi
- Auto-absen jika UID terdaftar (log ke absensi.csv)
- Jika UID belum terdaftar: isikan ke form agar bisa didaftarkan
- CRUD data pengguna (users.csv): Tambah, Edit, Hapus
- Assign UID dari "UID Terdeteksi" ke user yang dipilih/form
- Tabel pengguna & tabel log absensi (Treeview)
- Pilih COM port dari dropdown, Connect/Disconnect
- Simpan data di CSV (users.csv, absensi.csv)

Cara pakai singkat:
1) Install: pip install pyserial
2) Jalankan: python absensi_gui.py
3) Build EXE (Windows): pyinstaller --noconsole --onefile --name "AbsensiRFID" absensi_gui.py
"""

import os
import csv
import threading
import queue
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Serial ops: pyserial ops diimpor saat runtime agar app tetap jalan meski belum terpasang
try:
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover
    serial = None
    list_ports = None

USERS_CSV = "users.csv"
LOG_CSV = "absensi.csv"

BAUDRATE = 9600

class CsvStore:
    @staticmethod
    def ensure_files():
        if not os.path.exists(USERS_CSV):
            with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["uid", "nama", "umur"])
                writer.writeheader()
        if not os.path.exists(LOG_CSV):
            with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["uid", "nama", "waktu"])
                writer.writeheader()

    @staticmethod
    def load_users():
        users = []
        with open(USERS_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                users.append({"uid": row["uid"].strip().upper(),
                              "nama": row["nama"],
                              "umur": row.get("umur", "")})
        return users

    @staticmethod
    def save_users(users):
        with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["uid", "nama", "umur"])
            writer.writeheader()
            for u in users:
                writer.writerow({"uid": u["uid"].upper(), "nama": u["nama"], "umur": u.get("umur", "")})

    @staticmethod
    def append_log(uid, nama):
        with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["uid", "nama", "waktu"])
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow({
                "uid": uid.upper(),
                "nama": nama,
                "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    @staticmethod
    def load_logs(limit=None):
        logs = []
        with open(LOG_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                logs.append(row)
        if limit:
            return logs[-limit:]
        return logs


def normalize_uid(text: str) -> str:
    t = ''.join(c for c in text if c.isalnum())  # buang spasi/char lain
    return t.upper()


class SerialReader(threading.Thread):
    def __init__(self, port: str, baud: int, out_queue: queue.Queue, on_error):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.out_queue = out_queue
        self.on_error = on_error
        self._stop = threading.Event()
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
        except Exception as e:
            self.on_error(f"Gagal open port {self.port}: {e}")
            return
        while not self._stop.is_set():
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line:
                    uid = normalize_uid(line)
                    if uid:
                        self.out_queue.put(uid)
            except Exception as e:
                self.on_error(f"Serial error: {e}")
                break
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def stop(self):
        self._stop.set()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Absensi RFID RC522 – Python GUI")
        self.geometry("1000x640")
        self.minsize(900, 580)

        CsvStore.ensure_files()
        self.users = CsvStore.load_users()
        self.logs = CsvStore.load_logs()

        self.serial_queue = queue.Queue()
        self.reader = None

        self._build_ui()
        self.refresh_tables()
        self.after(100, self._poll_serial)

    # UI BUILDING
    def _build_ui(self):
        # === Top Controls ===
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Port:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, width=20, state="readonly")
        self._refresh_ports()
        self.port_combo.pack(side="left", padx=5)
        ttk.Button(top, text="Refresh Port", command=self._refresh_ports).pack(side="left")
        ttk.Button(top, text="Connect", command=self.connect).pack(side="left", padx=(10, 3))
        ttk.Button(top, text="Disconnect", command=self.disconnect).pack(side="left")

        ttk.Separator(self).pack(fill="x", pady=4)

        # === UID Detected ===
        uid_frame = ttk.Frame(self, padding=8)
        uid_frame.pack(fill="x")
        ttk.Label(uid_frame, text="UID Terdeteksi:", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.uid_detected_var = tk.StringVar(value="-")
        self.uid_detected_lbl = ttk.Label(uid_frame, textvariable=self.uid_detected_var, font=("Consolas", 12))
        self.uid_detected_lbl.pack(side="left", padx=8)
        ttk.Button(uid_frame, text="Assign UID ke Form", command=self.assign_uid_to_form).pack(side="left")
        ttk.Button(uid_frame, text="Absen UID Terdeteksi", command=self.absen_uid_terdeteksi).pack(side="left", padx=4)

        ttk.Separator(self).pack(fill="x", pady=4)

        # === Main Split ===
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(main)
        right.pack(side="left", fill="y", padx=8)

        # Users table
        ttk.Label(left, text="Data Pengguna (users.csv)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.users_tree = ttk.Treeview(left, columns=("uid", "nama", "umur"), show="headings", height=10)
        for col, w in (("uid", 180), ("nama", 220), ("umur", 80)):
            self.users_tree.heading(col, text=col.upper())
            self.users_tree.column(col, width=w)
        self.users_tree.pack(fill="both", expand=True)
        self.users_tree.bind("<<TreeviewSelect>>", self.on_user_select)

        user_btns = ttk.Frame(left)
        user_btns.pack(fill="x", pady=4)
        ttk.Button(user_btns, text="Tambah Baru", command=self.form_new).pack(side="left")
        ttk.Button(user_btns, text="Simpan/Update", command=self.form_save).pack(side="left", padx=4)
        ttk.Button(user_btns, text="Hapus", command=self.delete_user).pack(side="left")
        ttk.Button(user_btns, text="Assign UID dari Deteksi", command=self.assign_uid_to_form).pack(side="left", padx=4)
        ttk.Button(user_btns, text="Reload", command=self.refresh_tables).pack(side="left")

        # Form kanan
        ttk.Label(right, text="Form Pengguna", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        frm = ttk.Frame(right)
        frm.pack(fill="x", pady=4)

        ttk.Label(frm, text="UID:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.uid_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.uid_var).grid(row=0, column=1, sticky="we", padx=4, pady=4)

        ttk.Label(frm, text="Nama:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.nama_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.nama_var).grid(row=1, column=1, sticky="we", padx=4, pady=4)

        ttk.Label(frm, text="Umur:").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.umur_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.umur_var).grid(row=2, column=1, sticky="we", padx=4, pady=4)

        frm.columnconfigure(1, weight=1)

        ttk.Button(right, text="Absen user pada Form", command=self.absen_user_on_form).pack(anchor="w", pady=(6,0))

        ttk.Separator(self).pack(fill="x", pady=4)

        # Logs table
        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="both", expand=True)

        ttk.Label(bottom, text="Log Absensi (absensi.csv)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.logs_tree = ttk.Treeview(bottom, columns=("waktu", "uid", "nama"), show="headings", height=8)
        for col, w in (("waktu", 170), ("uid", 180), ("nama", 220)):
            self.logs_tree.heading(col, text=col.upper())
            self.logs_tree.column(col, width=w)
        self.logs_tree.pack(fill="both", expand=True)

        log_btns = ttk.Frame(bottom)
        log_btns.pack(fill="x", pady=4)
        ttk.Button(log_btns, text="Export Log...", command=self.export_logs).pack(side="left")

    # Helpers
    def _refresh_ports(self):
        ports = []
        if list_ports is not None:
            try:
                ports = [p.device for p in list_ports.comports()]
            except Exception:
                ports = []
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def refresh_tables(self):
        self.users = CsvStore.load_users()
        self.logs = CsvStore.load_logs()
        # users table
        for i in self.users_tree.get_children():
            self.users_tree.delete(i)
        for u in self.users:
            self.users_tree.insert("", "end", values=(u["uid"], u["nama"], u.get("umur", "")))
        # logs table (show last 200)
        for i in self.logs_tree.get_children():
            self.logs_tree.delete(i)
        for row in self.logs[-200:]:
            self.logs_tree.insert("", "end", values=(row["waktu"], row["uid"], row["nama"]))

    # Serial controls
    def connect(self):
        if self.reader is not None:
            messagebox.showinfo("Info", "Sudah terhubung.")
            return
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Pilih COM port terlebih dahulu.")
            return
        if serial is None:
            messagebox.showerror("Error", "pyserial belum terpasang. Jalankan: pip install pyserial")
            return
        self.reader = SerialReader(port, BAUDRATE, self.serial_queue, self._on_serial_error)
        self.reader.start()
        messagebox.showinfo("Serial", f"Terhubung ke {port}")

    def disconnect(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
            messagebox.showinfo("Serial", "Terputus")

    def _on_serial_error(self, msg):
        self.after(0, lambda: messagebox.showerror("Serial", msg))

    def _poll_serial(self):
        try:
            while True:
                uid = self.serial_queue.get_nowait()
                if uid:
                    self.on_uid_received(uid)
        except queue.Empty:
            pass
        self.after(100, self._poll_serial)

    def flash_uid_label(self):
        # simple flash effect
        orig = self.uid_detected_lbl.cget("foreground")
        def toggle(i=0):
            if i >= 6:
                self.uid_detected_lbl.configure(foreground=orig)
                return
            self.uid_detected_lbl.configure(foreground=("#0078D7" if i % 2 == 0 else "#000000"))
            self.after(150, lambda: toggle(i+1))
        toggle()

    def on_uid_received(self, uid):
        self.uid_detected_var.set(uid)
        self.flash_uid_label()
        # auto-absen jika terdaftar; jika tidak, masukkan ke form
        user = self.find_user_by_uid(uid)
        if user:
            CsvStore.append_log(uid, user["nama"])
            self.refresh_tables()
        else:
            # isi ke form supaya bisa didaftarkan
            self.uid_var.set(uid)
            # opsi: tampilkan notifikasi ringan
            self.bell()

    # User ops
    def find_user_by_uid(self, uid):
        uid = normalize_uid(uid)
        for u in self.users:
            if normalize_uid(u["uid"]) == uid:
                return u
        return None

    def on_user_select(self, event=None):
        sel = self.users_tree.selection()
        if not sel:
            return
        vals = self.users_tree.item(sel[0], "values")
        self.uid_var.set(vals[0])
        self.nama_var.set(vals[1])
        self.umur_var.set(vals[2])

    def form_new(self):
        self.uid_var.set("")
        self.nama_var.set("")
        self.umur_var.set("")

    def form_save(self):
        uid = normalize_uid(self.uid_var.get())
        nama = self.nama_var.get().strip()
        umur = self.umur_var.get().strip()
        if not uid or not nama:
            messagebox.showerror("Error", "UID dan Nama wajib diisi.")
            return
        existing = self.find_user_by_uid(uid)
        if existing:
            # update
            for u in self.users:
                if normalize_uid(u["uid"]) == uid:
                    u["nama"] = nama
                    u["umur"] = umur
            CsvStore.save_users(self.users)
            messagebox.showinfo("Sukses", "Data pengguna diperbarui.")
        else:
            # add
            self.users.append({"uid": uid, "nama": nama, "umur": umur})
            CsvStore.save_users(self.users)
            messagebox.showinfo("Sukses", "Pengguna baru ditambahkan.")
        self.refresh_tables()

    def delete_user(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showerror("Error", "Pilih data yang akan dihapus.")
            return
        vals = self.users_tree.item(sel[0], "values")
        uid = normalize_uid(vals[0])
        if messagebox.askyesno("Konfirmasi", f"Hapus pengguna UID {uid}?"):
            self.users = [u for u in self.users if normalize_uid(u["uid"]) != uid]
            CsvStore.save_users(self.users)
            self.refresh_tables()

    def assign_uid_to_form(self):
        uid = self.uid_detected_var.get()
        if not uid or uid == "-":
            messagebox.showinfo("Info", "Belum ada UID terdeteksi.")
            return
        self.uid_var.set(uid)

    def absen_uid_terdeteksi(self):
        uid = self.uid_detected_var.get()
        if not uid or uid == "-":
            messagebox.showinfo("Info", "Belum ada UID terdeteksi.")
            return
        user = self.find_user_by_uid(uid)
        if not user:
            messagebox.showwarning("Tidak Terdaftar", "UID belum terdaftar. Daftarkan dulu di form pengguna.")
            self.uid_var.set(uid)
            return
        CsvStore.append_log(uid, user["nama"])
        self.refresh_tables()
        messagebox.showinfo("Absen", f"Absensi tercatat untuk {user['nama']}")

    def absen_user_on_form(self):
        uid = normalize_uid(self.uid_var.get())
        if not uid:
            messagebox.showerror("Error", "Form belum berisi UID.")
            return
        user = self.find_user_by_uid(uid)
        if not user:
            if not self.nama_var.get().strip():
                messagebox.showwarning("Tidak Terdaftar", "Isi nama & simpan terlebih dahulu, lalu absen.")
                return
            # auto-simpan jika belum ada dan nama terisi
            self.form_save()
            user = self.find_user_by_uid(uid)
        CsvStore.append_log(uid, user["nama"])
        self.refresh_tables()
        messagebox.showinfo("Absen", f"Absensi tercatat untuk {user['nama']}")

    def export_logs(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="absensi_export.csv")
        if not path:
            return
        try:
            with open(LOG_CSV, "r", encoding="utf-8") as src, open(path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            messagebox.showinfo("Export", f"Log diekspor ke\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Gagal export: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
