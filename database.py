import sqlite3
from datetime import date
from pathlib import Path

import bcrypt

DB_PATH = Path(__file__).with_name("absensi.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS siswa (
    id_siswa INTEGER PRIMARY KEY AUTOINCREMENT,
    nis TEXT NOT NULL UNIQUE,
    nama_lengkap TEXT NOT NULL,
    kelas TEXT NOT NULL,
    status_siswa TEXT NOT NULL DEFAULT 'Aktif'
);

CREATE TABLE IF NOT EXISTS kartu_rfid (
    id_kartu INTEGER PRIMARY KEY AUTOINCREMENT,
    id_siswa INTEGER NOT NULL,
    uid_kartu TEXT NOT NULL UNIQUE,
    status_kartu TEXT NOT NULL DEFAULT 'Aktif',
    FOREIGN KEY (id_siswa) REFERENCES siswa(id_siswa) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS data_wajah (
    id_wajah INTEGER PRIMARY KEY AUTOINCREMENT,
    id_siswa INTEGER NOT NULL,
    face_template BLOB NOT NULL,
    tanggal_daftar DATE NOT NULL DEFAULT (DATE('now', 'localtime')),
    FOREIGN KEY (id_siswa) REFERENCES siswa(id_siswa) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_petugas (
    id_petugas INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_petugas TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'petugas'
);

CREATE TABLE IF NOT EXISTS absensi (
    id_absensi INTEGER PRIMARY KEY AUTOINCREMENT,
    id_siswa INTEGER NOT NULL,
    tanggal DATE NOT NULL,
    jam_masuk TIME NOT NULL,
    metode TEXT NOT NULL CHECK (metode IN ('RFID', 'Alternatif')),
    status_kehadiran TEXT NOT NULL DEFAULT 'Hadir',
    id_petugas INTEGER,
    FOREIGN KEY (id_siswa) REFERENCES siswa(id_siswa),
    FOREIGN KEY (id_petugas) REFERENCES admin_petugas(id_petugas),
    UNIQUE (id_siswa, tanggal)
);
CREATE INDEX IF NOT EXISTS idx_absensi_tanggal ON absensi(tanggal);
CREATE INDEX IF NOT EXISTS idx_kartu_uid ON kartu_rfid(uid_kartu);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def _row_to_dict(row):
    return dict(row) if row is not None else None


def add_siswa(nis, nama_lengkap, kelas):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO siswa (nis, nama_lengkap, kelas) VALUES (?, ?, ?)",
            (nis, nama_lengkap, kelas),
        )
        return cur.lastrowid


def get_siswa_by_id(id_siswa):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM siswa WHERE id_siswa = ?", (id_siswa,)).fetchone()
    return _row_to_dict(row)


def list_siswa():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM siswa ORDER BY nama_lengkap").fetchall()
    return [dict(r) for r in rows]


def get_siswa_by_uid(uid_kartu):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT s.* FROM siswa s
               JOIN kartu_rfid k ON k.id_siswa = s.id_siswa
               WHERE k.uid_kartu = ? AND s.status_siswa = 'Aktif'
                 AND k.status_kartu = 'Aktif'""",
            (uid_kartu,),
        ).fetchone()
    return _row_to_dict(row)


def add_kartu(id_siswa, uid_kartu):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO kartu_rfid (id_siswa, uid_kartu) VALUES (?, ?)",
            (id_siswa, uid_kartu),
        )
        return cur.lastrowid


def save_face_template(id_siswa, face_template_bytes):
    with get_connection() as conn:
        conn.execute("DELETE FROM data_wajah WHERE id_siswa = ?", (id_siswa,))
        cur = conn.execute(
            "INSERT INTO data_wajah (id_siswa, face_template) VALUES (?, ?)",
            (id_siswa, face_template_bytes),
        )
        return cur.lastrowid


def get_face_template_by_siswa(id_siswa):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT face_template FROM data_wajah WHERE id_siswa = ? ORDER BY id_wajah DESC LIMIT 1",
            (id_siswa,),
        ).fetchone()
    return row["face_template"] if row else None


def get_all_face_templates():
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT dw.id_siswa, dw.face_template FROM data_wajah dw
               JOIN siswa s ON s.id_siswa = dw.id_siswa
               WHERE s.status_siswa = 'Aktif'"""
        ).fetchall()
    return [(r["id_siswa"], r["face_template"]) for r in rows]


def sudah_absen(id_siswa, tanggal=None):
    tanggal = tanggal or date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM absensi WHERE id_siswa = ? AND tanggal = ? LIMIT 1",
            (id_siswa, tanggal),
        ).fetchone()
    return row is not None


def catat_absensi(id_siswa, metode, id_petugas=None, status_kehadiran="Hadir"):
    if sudah_absen(id_siswa):
        return None
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO absensi (id_siswa, tanggal, jam_masuk, metode, status_kehadiran, id_petugas)
                   VALUES (?, DATE('now', 'localtime'), TIME('now', 'localtime'), ?, ?, ?)""",
                (id_siswa, metode, status_kehadiran, id_petugas),
            )
        except sqlite3.IntegrityError:
            return None
        return cur.lastrowid


def get_absensi_hari_ini():
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.*, s.nis, s.nama_lengkap, s.kelas
               FROM absensi a JOIN siswa s ON s.id_siswa = a.id_siswa
               WHERE a.tanggal = DATE('now', 'localtime')
               ORDER BY a.jam_masuk DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def create_admin(nama_petugas, username, password, role="petugas"):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO admin_petugas (nama_petugas, username, password_hash, role) VALUES (?, ?, ?, ?)",
            (nama_petugas, username, password_hash, role),
        )
        return cur.lastrowid


def count_admin():
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM admin_petugas").fetchone()["c"]


def verify_admin(username, password):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admin_petugas WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        return None
    if bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return dict(row)
    return None
