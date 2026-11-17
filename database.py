"""Banco de dados da Escala Santa Terezinha: SQLite local ou PostgreSQL/Neon."""
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from werkzeug.security import generate_password_hash

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE / "instance")))
DB_FILE = DATA_DIR / "escala.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip().strip("'\"")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL and not DATABASE_URL.startswith("postgresql://"):
    raise RuntimeError("DATABASE_URL deve começar com postgresql://")
POSTGRES = bool(DATABASE_URL)
if os.environ.get("PRODUCAO") and not POSTGRES and not os.environ.get("DATA_DIR"):
    raise RuntimeError("Produção exige DATABASE_URL do Neon ou DATA_DIR persistente")

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 nome TEXT NOT NULL,
 usuario TEXT NOT NULL UNIQUE,
 senha_hash TEXT NOT NULL,
 perfil TEXT NOT NULL CHECK (perfil IN ('padre','coordenador','servidor')),
 ativo INTEGER NOT NULL DEFAULT 1,
 criado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
 grupo TEXT NOT NULL DEFAULT 'altar'
);
CREATE TABLE IF NOT EXISTS missas (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 nome TEXT NOT NULL,
 data TEXT NOT NULL,
 hora TEXT NOT NULL,
 quantidade INTEGER NOT NULL,
 funcoes TEXT NOT NULL DEFAULT '[]',
 publicada INTEGER NOT NULL DEFAULT 0,
 recado TEXT NOT NULL DEFAULT '',
 criado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
 grupo TEXT NOT NULL DEFAULT 'altar'
);
CREATE TABLE IF NOT EXISTS avisos (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 titulo TEXT NOT NULL,
 mensagem TEXT NOT NULL,
 criado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
 grupo TEXT NOT NULL DEFAULT 'altar'
);
CREATE TABLE IF NOT EXISTS missa_disponiveis (
 missa_id INTEGER NOT NULL REFERENCES missas(id) ON DELETE CASCADE,
 servidor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
 PRIMARY KEY(missa_id,servidor_id)
);
CREATE TABLE IF NOT EXISTS escala (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 missa_id INTEGER NOT NULL REFERENCES missas(id) ON DELETE CASCADE,
 servidor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 funcao TEXT NOT NULL,
 ordem INTEGER NOT NULL DEFAULT 0,
 UNIQUE(missa_id, servidor_id)
);
CREATE INDEX IF NOT EXISTS idx_missas_data ON missas(data,hora);
CREATE INDEX IF NOT EXISTS idx_escala_missa ON escala(missa_id);
CREATE INDEX IF NOT EXISTS idx_escala_servidor ON escala(servidor_id);
"""

class PGConn:
    """Interface pequena compatível com SQLite, usando dicionários."""
    def __init__(self, connection):
        self.conn = connection

    def execute(self, sql, params=()):
        return self.conn.execute(sql.replace("?", "%s"), tuple(params))

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

def conectar():
    if POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        return PGConn(psycopg.connect(
            DATABASE_URL, row_factory=dict_row, connect_timeout=15,
            prepare_threshold=None
        ))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_FILE, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = conectar()
    try:
        if POSTGRES:
            schema = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            for statement in schema.split(";"):
                if statement.strip():
                    c.execute(statement)
        else:
            c.executescript(SCHEMA)

        for tabela in ("usuarios", "missas", "avisos"):
            if POSTGRES:
                c.execute(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS grupo TEXT NOT NULL DEFAULT 'altar'")
            else:
                cols = [r["name"] for r in c.execute(f"PRAGMA table_info({tabela})").fetchall()]
                if "grupo" not in cols:
                    c.execute(f"ALTER TABLE {tabela} ADD COLUMN grupo TEXT NOT NULL DEFAULT 'altar'")
        padre = c.execute("SELECT id FROM usuarios WHERE perfil='padre' LIMIT 1").fetchone()
        if padre is None:
            user = os.environ.get("PADRE_USER", "").strip()
            password = os.environ.get("PADRE_PASSWORD", "")
            if user and len(password) >= 12:
                c.execute(
                    "INSERT INTO usuarios (nome, usuario, senha_hash, perfil) VALUES (?, ?, ?, 'padre')",
                    ("Padre", user, generate_password_hash(password)),
                )
            else:
                print("[CONFIGURACAO] Cadastre PADRE_USER e PADRE_PASSWORD (min. 12 caracteres) para criar o primeiro acesso.", flush=True)
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
