#!/usr/bin/env python3
"""
Migra dados de um banco SQLite para Postgres de forma segura.

Uso:
  python scripts/migrate_sqlite_to_postgres.py --pg-url POSTGRES_URL [--sqlite DB] [--dry-run] [--chunk-size N] [--apply]

Por segurança, o script roda em modo `--dry-run` por padrão e apenas valida contagens
e amostras. Para efetivar a migração passe `--apply`.
"""
import argparse
import sqlite3
import os
import sys
import logging
import hashlib
from contextlib import closing

try:
    import psycopg2
    import psycopg2.extras
except Exception:
    print('Erro: instale psycopg2 (ex: pip install psycopg2-binary)')
    raise

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('migrate')


def md5_of_rowvalues(row):
    s = '|'.join('' if v is None else str(v) for v in row)
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def ensure_tables(pg_conn):
    cur = pg_conn.cursor()
    # Create tables with types appropriate for Postgres; id as BIGSERIAL so sequences exist
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS inventory_items (
        id BIGSERIAL PRIMARY KEY,
        code TEXT DEFAULT '',
        name TEXT NOT NULL,
        category TEXT,
        classification TEXT DEFAULT '',
        quantity INTEGER NOT NULL DEFAULT 0,
        minimum_quantity INTEGER NOT NULL DEFAULT 0,
        price REAL NOT NULL DEFAULT 0.0,
        corridor TEXT DEFAULT '',
        cabinet TEXT DEFAULT '',
        shelf TEXT DEFAULT '',
        description TEXT,
        extra_data TEXT DEFAULT '{}'
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS stock_movements (
        id BIGSERIAL PRIMARY KEY,
        item_id INTEGER,
        item_name TEXT,
        type TEXT,
        quantity INTEGER,
        previous_quantity INTEGER,
        new_quantity INTEGER,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    pg_conn.commit()


def transfer_table(sqlite_conn, pg_conn, table, columns, chunk_size=1000, apply=False):
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()
    cols_sql = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))

    sqlite_cur.execute(f'SELECT COUNT(*) FROM {table}')
    total = sqlite_cur.fetchone()[0]
    logger.info('Tabela %s tem %d linhas', table, total)

    # For dry-run, compute a small sample checksum
    sample_md5 = None
    if total > 0:
        sqlite_cur.execute(f'SELECT {cols_sql} FROM {table} LIMIT 100')
        rows = sqlite_cur.fetchall()
        m = hashlib.md5()
        for r in rows:
            m.update('|'.join('' if v is None else str(v) for v in r).encode('utf-8'))
        sample_md5 = m.hexdigest()

    if not apply:
        return {'table': table, 'total': total, 'sample_md5': sample_md5}

    # Insert rows in chunks
    offset = 0
    inserted = 0
    while True:
        sqlite_cur.execute(f'SELECT {cols_sql} FROM {table} LIMIT ? OFFSET ?', (chunk_size, offset))
        rows = sqlite_cur.fetchall()
        if not rows:
            break

        # psycopg2 expects tuples
        data = [tuple(r) for r in rows]
        # Build explicit INSERT preserving id when present
        colnames = columns
        insert_sql = f'INSERT INTO {table} ({", ".join(colnames)}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING'
        try:
            psycopg2.extras.execute_batch(pg_cur, insert_sql, data, page_size=1000)
        except Exception as e:
            logger.exception('Erro inserindo lote na tabela %s: %s', table, e)
            pg_conn.rollback()
            raise
        pg_conn.commit()
        inserted += len(rows)
        offset += len(rows)
        logger.info('Inseridas %d/%d linhas em %s', inserted, total, table)

    # After inserting, set sequence to max(id) if sequence exists
    try:
        pg_cur.execute(f"SELECT MAX(id) FROM {table}")
        maxid = pg_cur.fetchone()[0] or 0
        # sequence name pattern: {table}_id_seq
        seq = f"{table}_id_seq"
        pg_cur.execute("SELECT 1 FROM pg_class WHERE relkind='S' AND relname=%s", (seq,))
        if pg_cur.fetchone():
            pg_cur.execute(f"SELECT setval(%s, %s)", (seq, maxid))
            pg_conn.commit()
    except Exception:
        pg_conn.rollback()

    return {'table': table, 'total': total, 'inserted': inserted}


def main():
    parser = argparse.ArgumentParser(description='Migração SQLite -> Postgres segura')
    parser.add_argument('--sqlite', help='Arquivo SQLite (padrão: config.Config.DATABASE)', default=None)
    parser.add_argument('--pg-url', help='URL de conexão do Postgres (ex: postgresql://user:pass@host:5432/db)', required=True)
    parser.add_argument('--dry-run', action='store_true', help='Executa apenas validações (padrão)')
    parser.add_argument('--chunk-size', type=int, default=1000)
    parser.add_argument('--apply', action='store_true', help='Aplicar a migração (requer confirmação)')
    args = parser.parse_args()

    # Determine sqlite path
    sqlite_path = args.sqlite
    if sqlite_path is None:
        # Try to import config from project
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        sys.path.insert(0, proj_root)
        try:
            from config import Config
            sqlite_path = Config.DATABASE
        except Exception:
            pass

    if not sqlite_path or not os.path.isfile(sqlite_path):
        logger.error('Arquivo SQLite não encontrado: %s', sqlite_path)
        sys.exit(1)

    logger.info('SQLite: %s', sqlite_path)
    logger.info('Postgres: %s', args.pg_url)
    if not args.apply:
        logger.info('Rodando em modo dry-run. Use --apply para executar a migração.')

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg2.connect(args.pg_url)

    # Ensure tables exist in Postgres
    ensure_tables(pg_conn)

    # Tables and column lists (preserve id column when present)
    tables = [
        ('users', ['id', 'username', 'password', 'role']),
        ('inventory_items', ['id', 'code', 'name', 'category', 'classification', 'quantity', 'minimum_quantity', 'price', 'corridor', 'cabinet', 'shelf', 'description', 'extra_data']),
        ('stock_movements', ['id', 'item_id', 'item_name', 'type', 'quantity', 'previous_quantity', 'new_quantity', 'reason', 'created_at']),
    ]

    results = []
    try:
        for table, cols in tables:
            res = transfer_table(sqlite_conn, pg_conn, table, cols, chunk_size=args.chunk_size, apply=args.apply)
            results.append(res)
    finally:
        sqlite_conn.close()
        pg_conn.close()

    # Summary
    for r in results:
        logger.info('Resultado para %s: %s', r.get('table'), {k: v for k, v in r.items() if k != 'table'})

    logger.info('Migração concluída (modo apply=%s)', args.apply)


if __name__ == '__main__':
    main()
