import os
import sqlite3

# Configurações do Banco de Dados via variáveis de ambiente
DB_TYPE = os.environ.get("DB_TYPE", "sqlite").lower()
DB_PATH = os.path.join(os.path.dirname(__file__), "logs_analysis.db")

# PostgreSQL Configs
PG_HOST = os.environ.get("POSTGRESQL_HOST", os.environ.get("DB_HOST", "postgres"))
PG_PORT = os.environ.get("POSTGRESQL_PORT", os.environ.get("DB_PORT", "5432"))
PG_USER = os.environ.get("POSTGRESQL_USER", os.environ.get("DB_USER", "downdetector"))
PG_PASS = os.environ.get("POSTGRESQL_PASSWORD", os.environ.get("DB_PASSWORD", "down@2024"))
PG_DB = os.environ.get("POSTGRESQL_DATABASE", os.environ.get("DB_NAME", "loganalizer"))

if os.environ.get("POSTGRESQL_HOST") or os.environ.get("DB_TYPE") == "postgres":
    DB_TYPE = "postgres"

def get_connection():
    if DB_TYPE == "postgres":
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASS,
            dbname=PG_DB
        )
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def _ensure_pg_database():
    """Garante a criação do banco se estiver conectando como postgres inicial"""
    if DB_TYPE != "postgres":
        return
    import psycopg2
    try:
        # Testa conexão direta
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
        conn.close()
    except psycopg2.OperationalError:
        # Se banco não existe, conecta no default 'postgres' para criá-lo
        try:
            conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname="postgres")
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(f"CREATE DATABASE {PG_DB};")
            cur.close()
            conn.close()
        except Exception:
            pass

def init_db(drop_existing=False):
    if DB_TYPE == "postgres":
        _ensure_pg_database()
        conn = get_connection()
        cursor = conn.cursor()
        if drop_existing:
            cursor.execute("DROP TABLE IF EXISTS iis_logs CASCADE")
            cursor.execute("DROP TABLE IF EXISTS analysis_meta CASCADE")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_batches (
                id BIGSERIAL PRIMARY KEY,
                batch_uuid VARCHAR(64) UNIQUE,
                filename VARCHAR(255),
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_persistent BOOLEAN DEFAULT FALSE,
                expires_at TIMESTAMP NULL,
                total_lines BIGINT DEFAULT 0,
                elapsed_seconds REAL DEFAULT 0,
                cores_used INT DEFAULT 1,
                lines_per_second INT DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS iis_logs (
                id BIGSERIAL PRIMARY KEY,
                batch_id BIGINT,
                timestamp VARCHAR(64),
                log_date VARCHAR(32),
                log_time VARCHAR(32),
                client_ip VARCHAR(64),
                method VARCHAR(32),
                uri_stem TEXT,
                uri_query TEXT,
                status INT,
                substatus BIGINT,
                win32_status BIGINT,
                time_taken BIGINT,
                user_agent TEXT,
                referer TEXT,
                server_ip VARCHAR(64),
                server_port BIGINT,
                username VARCHAR(128),
                x_forwarded_for VARCHAR(128),
                raw_log TEXT
            )
        """)

        # Garantir migração de colunas caso a tabela já tenha sido criada anteriormente
        try:
            cursor.execute("""
                ALTER TABLE iis_logs 
                    ALTER COLUMN id TYPE BIGINT,
                    ALTER COLUMN substatus TYPE BIGINT,
                    ALTER COLUMN win32_status TYPE BIGINT,
                    ALTER COLUMN time_taken TYPE BIGINT,
                    ALTER COLUMN server_port TYPE BIGINT,
                    ADD COLUMN IF NOT EXISTS batch_id BIGINT,
                    ADD COLUMN IF NOT EXISTS x_forwarded_for VARCHAR(128),
                    ADD COLUMN IF NOT EXISTS raw_log TEXT;
            """)
        except Exception:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_meta (
                key VARCHAR(64) PRIMARY KEY,
                value TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON iis_logs(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON iis_logs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_method ON iis_logs(method)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_ip ON iis_logs(client_ip)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uri_stem ON iis_logs(uri_stem)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_taken ON iis_logs(time_taken)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON iis_logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_xff ON iis_logs(x_forwarded_for)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_server_port ON iis_logs(server_port)")

        conn.commit()
        cursor.close()
        conn.close()
    else:
        conn = get_connection()
        cursor = conn.cursor()
        if drop_existing:
            cursor.execute("DROP TABLE IF EXISTS iis_logs")
            cursor.execute("DROP TABLE IF EXISTS analysis_batches")
            cursor.execute("DROP TABLE IF EXISTS analysis_meta")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_uuid TEXT UNIQUE,
                filename TEXT,
                uploaded_at TEXT,
                is_persistent INTEGER DEFAULT 0,
                expires_at TEXT,
                total_lines INTEGER DEFAULT 0,
                elapsed_seconds REAL DEFAULT 0,
                cores_used INTEGER DEFAULT 1,
                lines_per_second INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS iis_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                timestamp TEXT,
                log_date TEXT,
                log_time TEXT,
                client_ip TEXT,
                method TEXT,
                uri_stem TEXT,
                uri_query TEXT,
                status INTEGER,
                substatus INTEGER,
                win32_status INTEGER,
                time_taken INTEGER,
                user_agent TEXT,
                referer TEXT,
                server_ip TEXT,
                server_port INTEGER,
                username TEXT,
                x_forwarded_for TEXT,
                raw_log TEXT
            )
        """)

        # Migração defensiva para SQLite caso a tabela já exista de uma execução anterior
        cursor.execute("PRAGMA table_info(iis_logs)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "batch_id" not in existing_cols:
            cursor.execute("ALTER TABLE iis_logs ADD COLUMN batch_id INTEGER")
        if "x_forwarded_for" not in existing_cols:
            cursor.execute("ALTER TABLE iis_logs ADD COLUMN x_forwarded_for TEXT")
        if "raw_log" not in existing_cols:
            cursor.execute("ALTER TABLE iis_logs ADD COLUMN raw_log TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON iis_logs(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON iis_logs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_method ON iis_logs(method)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_ip ON iis_logs(client_ip)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uri_stem ON iis_logs(uri_stem)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_taken ON iis_logs(time_taken)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON iis_logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_xff ON iis_logs(x_forwarded_for)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_server_port ON iis_logs(server_port)")

        conn.commit()
        cursor.close()
        conn.close()

def cleanup_expired_batches():
    """Remove lotes de log com mais de 24h que não estejam marcados como persistentes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if DB_TYPE == "postgres":
            # Busca IDs expirados
            cursor.execute("""
                SELECT id FROM analysis_batches 
                WHERE is_persistent = FALSE 
                  AND expires_at IS NOT NULL 
                  AND expires_at <= NOW()
            """)
            expired_ids = [r[0] for r in cursor.fetchall()]
            if expired_ids:
                cursor.execute("DELETE FROM iis_logs WHERE batch_id = ANY(%s)", (expired_ids,))
                cursor.execute("DELETE FROM analysis_batches WHERE id = ANY(%s)", (expired_ids,))
                conn.commit()
        else:
            cursor.execute("""
                SELECT id FROM analysis_batches 
                WHERE (is_persistent = 0 OR is_persistent IS NULL)
                  AND expires_at IS NOT NULL 
                  AND expires_at <= ?
            """, (now_iso,))
            expired_ids = [r[0] for r in cursor.fetchall()]
            if expired_ids:
                ph = ','.join(['?'] * len(expired_ids))
                cursor.execute(f"DELETE FROM iis_logs WHERE batch_id IN ({ph})", expired_ids)
                cursor.execute(f"DELETE FROM analysis_batches WHERE id IN ({ph})", expired_ids)
                conn.commit()
        return len(expired_ids)
    except Exception as e:
        print(f"Erro ao limpar lotes expirados: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()

def create_batch(filename, stats, is_persistent=False):
    """Cria um novo registro de lote de análise com expiração em 24h ou infinito se persistente."""
    import uuid
    from datetime import datetime, timedelta, timezone

    conn = get_connection()
    cursor = conn.cursor()
    batch_uuid = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")

    expires_at_str = None
    if not is_persistent:
        expires_at_dt = now_utc + timedelta(hours=24)
        expires_at_str = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")

    total_lines = stats.get('total_lines', 0)
    elapsed_seconds = stats.get('elapsed_seconds', 0.0)
    cores_used = stats.get('cores_used', 1)
    lines_per_second = stats.get('lines_per_second', 0)

    try:
        if DB_TYPE == "postgres":
            cursor.execute("""
                INSERT INTO analysis_batches (
                    batch_uuid, filename, uploaded_at, is_persistent, expires_at,
                    total_lines, elapsed_seconds, cores_used, lines_per_second
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                batch_uuid, filename, now_str, is_persistent, expires_at_str,
                total_lines, elapsed_seconds, cores_used, lines_per_second
            ))
            batch_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO analysis_batches (
                    batch_uuid, filename, uploaded_at, is_persistent, expires_at,
                    total_lines, elapsed_seconds, cores_used, lines_per_second
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                batch_uuid, filename, now_str, 1 if is_persistent else 0, expires_at_str,
                total_lines, elapsed_seconds, cores_used, lines_per_second
            ))
            batch_id = cursor.lastrowid

        conn.commit()
        return batch_id
    finally:
        cursor.close()
        conn.close()

def list_batches():
    """Lista todos os lotes de logs em ordem decrescente de envio com cálculo de tempo restante."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)

        cursor.execute("""
            SELECT id, batch_uuid, filename, uploaded_at, is_persistent, expires_at,
                   total_lines, elapsed_seconds, cores_used, lines_per_second
            FROM analysis_batches
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        batches = []
        for r in rows:
            b_id = r[0]
            b_uuid = r[1]
            b_file = r[2]
            b_uploaded = str(r[3])
            b_persist = bool(r[4])
            b_expires = str(r[5]) if r[5] else None
            b_lines = r[6]
            b_elapsed = r[7]
            b_cores = r[8]
            b_lps = r[9]

            remaining_str = "Permanente"
            expired = False

            if not b_persist and b_expires:
                try:
                    # Limpa microssegundos ou timezone se vierem em strings
                    clean_exp = b_expires.split('+')[0].split('.')[0]
                    exp_dt = datetime.strptime(clean_exp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    delta = exp_dt - now_utc
                    if delta.total_seconds() <= 0:
                        remaining_str = "Expirado"
                        expired = True
                    else:
                        hours = int(delta.total_seconds() // 3600)
                        minutes = int((delta.total_seconds() % 3600) // 60)
                        remaining_str = f"Expira em {hours}h {minutes:02d}m"
                except Exception:
                    remaining_str = "24 horas"

            batches.append({
                "id": b_id,
                "batch_uuid": b_uuid,
                "filename": b_file,
                "uploaded_at": b_uploaded,
                "is_persistent": b_persist,
                "expires_at": b_expires,
                "remaining_time": remaining_str,
                "is_expired": expired,
                "total_lines": b_lines,
                "elapsed_seconds": b_elapsed,
                "cores_used": b_cores,
                "lines_per_second": b_lps
            })
        return batches
    finally:
        cursor.close()
        conn.close()

def get_batch(batch_id):
    """Retorna detalhes de um lote específico."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        ph = "%s" if DB_TYPE == "postgres" else "?"
        cursor.execute(f"""
            SELECT id, batch_uuid, filename, uploaded_at, is_persistent, expires_at,
                   total_lines, elapsed_seconds, cores_used, lines_per_second
            FROM analysis_batches
            WHERE id = {ph}
        """, (batch_id,))
        r = cursor.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "batch_uuid": r[1],
            "filename": r[2],
            "uploaded_at": str(r[3]),
            "is_persistent": bool(r[4]),
            "expires_at": str(r[5]) if r[5] else None,
            "total_lines": r[6],
            "elapsed_seconds": r[7],
            "cores_used": r[8],
            "lines_per_second": r[9]
        }
    finally:
        cursor.close()
        conn.close()

def delete_batch(batch_id):
    """Exclui permanentemente um lote e todos os seus registros de log."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        ph = "%s" if DB_TYPE == "postgres" else "?"
        cursor.execute(f"DELETE FROM iis_logs WHERE batch_id = {ph}", (batch_id,))
        cursor.execute(f"DELETE FROM analysis_batches WHERE id = {ph}", (batch_id,))
        conn.commit()
        return True
    finally:
        cursor.close()
        conn.close()

def toggle_batch_persistence(batch_id):
    """Alterna a persistência de um lote: se persistente, define 24h a partir de agora; se temporário, torna persistente."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        from datetime import datetime, timedelta, timezone
        now_utc = datetime.now(timezone.utc)
        ph = "%s" if DB_TYPE == "postgres" else "?"

        cursor.execute(f"SELECT is_persistent FROM analysis_batches WHERE id = {ph}", (batch_id,))
        row = cursor.fetchone()
        if not row:
            return False

        current_persistent = bool(row[0])
        new_persistent = not current_persistent

        if new_persistent:
            new_expires = None
        else:
            new_expires = (now_utc + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        if DB_TYPE == "postgres":
            cursor.execute("""
                UPDATE analysis_batches 
                SET is_persistent = %s, expires_at = %s 
                WHERE id = %s
            """, (new_persistent, new_expires, batch_id))
        else:
            cursor.execute("""
                UPDATE analysis_batches 
                SET is_persistent = ?, expires_at = ? 
                WHERE id = ?
            """, (1 if new_persistent else 0, new_expires, batch_id))

        conn.commit()
        return {"is_persistent": new_persistent, "expires_at": new_expires}
    finally:
        cursor.close()
        conn.close()

def get_latest_batch_id():
    """Retorna o ID do lote mais recente ou None se não houver lotes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM analysis_batches ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()
        conn.close()

def save_records(records, stats, filename="iis_log.log", is_persistent=False):
    """Salva lote e associa os logs com o batch_id."""
    init_db(drop_existing=False)
    batch_id = create_batch(filename, stats, is_persistent=is_persistent)

    conn = get_connection()
    cursor = conn.cursor()

    # Incorporar batch_id em cada tupla de registro
    # records contém: (timestamp, log_date, log_time, client_ip, method, uri_stem, uri_query, status, substatus, win32_status, time_taken, user_agent, referer, server_ip, server_port, username, x_forwarded_for, raw_log)
    batch_records = [(batch_id,) + tuple(r) for r in records]

    if DB_TYPE == "postgres":
        import psycopg2.extras
        insert_sql = """
            INSERT INTO iis_logs (
                batch_id, timestamp, log_date, log_time, client_ip, method, uri_stem,
                uri_query, status, substatus, win32_status, time_taken,
                user_agent, referer, server_ip, server_port, username,
                x_forwarded_for, raw_log
            ) VALUES %s
        """
        psycopg2.extras.execute_values(cursor, insert_sql, batch_records, page_size=2000)

        for k, v in stats.items():
            cursor.execute("""
                INSERT INTO analysis_meta (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (k, str(v)))
    else:
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA journal_mode = MEMORY")
        insert_sql = """
            INSERT INTO iis_logs (
                batch_id, timestamp, log_date, log_time, client_ip, method, uri_stem,
                uri_query, status, substatus, win32_status, time_taken,
                user_agent, referer, server_ip, server_port, username,
                x_forwarded_for, raw_log
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.executemany(insert_sql, batch_records)

        for k, v in stats.items():
            cursor.execute("INSERT OR REPLACE INTO analysis_meta (key, value) VALUES (?, ?)", (k, str(v)))

    conn.commit()
    cursor.close()
    conn.close()
    return batch_id

def get_stats_meta(batch_id=None):
    if batch_id:
        b = get_batch(batch_id)
        if b:
            return {
                "total_lines": b["total_lines"],
                "elapsed_seconds": b["elapsed_seconds"],
                "cores_used": b["cores_used"],
                "lines_per_second": b["lines_per_second"],
                "filename": b["filename"],
                "uploaded_at": b["uploaded_at"],
                "is_persistent": b["is_persistent"],
                "expires_at": b["expires_at"]
            }
    
    # Fallback para o lote mais recente se não passado batch_id
    latest_id = get_latest_batch_id()
    if latest_id:
        b = get_batch(latest_id)
        if b:
            return {
                "total_lines": b["total_lines"],
                "elapsed_seconds": b["elapsed_seconds"],
                "cores_used": b["cores_used"],
                "lines_per_second": b["lines_per_second"],
                "filename": b["filename"],
                "uploaded_at": b["uploaded_at"],
                "is_persistent": b["is_persistent"],
                "expires_at": b["expires_at"]
            }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM analysis_meta")
        rows = cursor.fetchall()
        if DB_TYPE == "postgres":
            return {r[0]: r[1] for r in rows}
        else:
            return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}
    finally:
        cursor.close()
        conn.close()

def get_dashboard_data(batch_id=None, include_port=True):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Se batch_id não foi informado, utiliza o lote mais recente
        if not batch_id:
            batch_id = get_latest_batch_id()
        if not batch_id:
            return None

        ph = "%s" if DB_TYPE == "postgres" else "?"

        cursor.execute(f"SELECT COUNT(*) FROM iis_logs WHERE batch_id = {ph}", (batch_id,))
        row = cursor.fetchone()
        total_requests = row[0] if row else 0
        if total_requests == 0:
            return None

        cursor.execute(f"""
            SELECT 
                AVG(time_taken) as avg_time,
                MAX(time_taken) as max_time,
                MIN(time_taken) as min_time
            FROM iis_logs
            WHERE batch_id = {ph}
        """, (batch_id,))
        t_row = cursor.fetchone()
        avg_time = round(float(t_row[0] or 0), 1)
        max_time = t_row[1] or 0
        min_time = t_row[2] or 0

        cursor.execute(f"""
            SELECT 
                CASE 
                    WHEN status >= 200 AND status < 300 THEN '2xx Success'
                    WHEN status >= 300 AND status < 400 THEN '3xx Redirect'
                    WHEN status >= 400 AND status < 500 THEN '4xx Client Error'
                    WHEN status >= 500 THEN '5xx Server Error'
                    ELSE 'Other'
                END as status_group,
                COUNT(*) as count
            FROM iis_logs
            WHERE batch_id = {ph}
            GROUP BY status_group
            ORDER BY count DESC
        """, (batch_id,))
        status_groups = [{"status_group": r[0], "count": r[1]} for r in cursor.fetchall()]

        cursor.execute(f"""
            SELECT status, COUNT(*) as count 
            FROM iis_logs 
            WHERE batch_id = {ph}
            GROUP BY status 
            ORDER BY count DESC 
            LIMIT 10
        """, (batch_id,))
        top_statuses = [{"status": r[0], "count": r[1]} for r in cursor.fetchall()]

        cursor.execute(f"""
            SELECT method, COUNT(*) as count 
            FROM iis_logs 
            WHERE batch_id = {ph}
            GROUP BY method 
            ORDER BY count DESC
        """, (batch_id,))
        methods = [{"method": r[0], "count": r[1]} for r in cursor.fetchall()]

        cursor.execute(f"""
            SELECT uri_stem, COUNT(*) as count, ROUND(AVG(time_taken), 1) as avg_time
            FROM iis_logs 
            WHERE batch_id = {ph}
            GROUP BY uri_stem 
            ORDER BY count DESC 
            LIMIT 10
        """, (batch_id,))
        top_uris = [{"uri_stem": r[0], "count": r[1], "avg_time": float(r[2] or 0)} for r in cursor.fetchall()]

        # Expressão SQL para tratar X-Forwarded-For e Client-IP (com ou sem porta)
        if include_port:
            xff_expr = "x_forwarded_for"
            ip_calc_expr = """
                CASE 
                    WHEN x_forwarded_for IS NOT NULL AND x_forwarded_for != '-' AND x_forwarded_for != ''
                    THEN x_forwarded_for
                    ELSE client_ip
                END
            """
        else:
            if DB_TYPE == "postgres":
                xff_expr = """
                    CASE 
                        WHEN x_forwarded_for IS NOT NULL AND x_forwarded_for != '-' AND x_forwarded_for != ''
                        THEN SPLIT_PART(x_forwarded_for, ':', 1)
                        ELSE '-'
                    END
                """
                ip_calc_expr = """
                    CASE 
                        WHEN x_forwarded_for IS NOT NULL AND x_forwarded_for != '-' AND x_forwarded_for != ''
                        THEN SPLIT_PART(x_forwarded_for, ':', 1)
                        ELSE SPLIT_PART(client_ip, ':', 1)
                    END
                """
            else:
                xff_expr = """
                    CASE 
                        WHEN x_forwarded_for IS NOT NULL AND x_forwarded_for != '-' AND x_forwarded_for != ''
                        THEN CASE WHEN INSTR(x_forwarded_for, ':') > 0 THEN SUBSTR(x_forwarded_for, 1, INSTR(x_forwarded_for, ':') - 1) ELSE x_forwarded_for END
                        ELSE '-'
                    END
                """
                ip_calc_expr = """
                    CASE 
                        WHEN x_forwarded_for IS NOT NULL AND x_forwarded_for != '-' AND x_forwarded_for != ''
                        THEN CASE WHEN INSTR(x_forwarded_for, ':') > 0 THEN SUBSTR(x_forwarded_for, 1, INSTR(x_forwarded_for, ':') - 1) ELSE x_forwarded_for END
                        ELSE CASE WHEN INSTR(client_ip, ':') > 0 THEN SUBSTR(client_ip, 1, INSTR(client_ip, ':') - 1) ELSE client_ip END
                    END
                """

        cursor.execute(f"""
            SELECT MIN(client_ip) as client_ip, {xff_expr} as xff_display, COUNT(*) as count 
            FROM iis_logs 
            WHERE batch_id = {ph}
            GROUP BY xff_display 
            ORDER BY count DESC 
            LIMIT 10
        """, (batch_id,))
        top_ips = [{"client_ip": r[0], "x_forwarded_for": r[1] or '-', "count": r[2]} for r in cursor.fetchall()]

        cursor.execute(f"""
            SELECT uri_stem, ROUND(AVG(time_taken), 1) as avg_time, MAX(time_taken) as max_time, COUNT(*) as count
            FROM iis_logs
            WHERE batch_id = {ph}
            GROUP BY uri_stem
            ORDER BY avg_time DESC
            LIMIT 10
        """, (batch_id,))
        slowest_uris = [{"uri_stem": r[0], "avg_time": float(r[1] or 0), "max_time": r[2], "count": r[3]} for r in cursor.fetchall()]

        cursor.execute(f"SELECT COUNT(DISTINCT SUBSTR(timestamp, 1, 13)) FROM iis_logs WHERE batch_id = {ph}", (batch_id,))
        hours_count = cursor.fetchone()[0]
        
        if hours_count <= 2:
            cursor.execute(f"""
                SELECT SUBSTR(timestamp, 1, 16) as time_slot, COUNT(*) as count,
                       SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
                FROM iis_logs
                WHERE batch_id = {ph} AND timestamp != ''
                GROUP BY time_slot
                ORDER BY time_slot ASC
                LIMIT 60
            """, (batch_id,))
        else:
            if DB_TYPE == "postgres":
                cursor.execute(f"""
                    SELECT CONCAT(SUBSTR(timestamp, 1, 13), ':00') as time_slot, COUNT(*) as count,
                           SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
                    FROM iis_logs
                    WHERE batch_id = %s AND timestamp != ''
                    GROUP BY time_slot
                    ORDER BY time_slot ASC
                    LIMIT 48
                """, (batch_id,))
            else:
                cursor.execute(f"""
                    SELECT SUBSTR(timestamp, 1, 13) || ':00' as time_slot, COUNT(*) as count,
                           SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
                    FROM iis_logs
                    WHERE batch_id = ? AND timestamp != ''
                    GROUP BY time_slot
                    ORDER BY time_slot ASC
                    LIMIT 48
                """, (batch_id,))
        timeline = [{"time_slot": r[0], "count": r[1], "errors": int(r[2] or 0)} for r in cursor.fetchall()]

        cursor.execute(f"SELECT COUNT(*) FROM iis_logs WHERE batch_id = {ph} AND status >= 400", (batch_id,))
        total_errors = cursor.fetchone()[0]
        error_rate = round((total_errors / total_requests * 100), 2) if total_requests > 0 else 0

        cursor.execute(f"""
            SELECT COUNT(DISTINCT {ip_calc_expr}) 
            FROM iis_logs 
            WHERE batch_id = {ph} 
              AND (
                  (client_ip IS NOT NULL AND client_ip != '-' AND client_ip != '')
                  OR 
                  (x_forwarded_for IS NOT NULL AND x_forwarded_for != '-' AND x_forwarded_for != '')
              )
        """, (batch_id,))
        unique_ips = cursor.fetchone()[0] or 0

        # === CONTADORES POR MINUTO ===
        cursor.execute(f"""
            SELECT 
                SUBSTR(timestamp, 1, 16) as minute_slot,
                uri_stem,
                COUNT(*) as count,
                ROUND(AVG(time_taken), 1) as avg_time,
                SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
            FROM iis_logs
            WHERE batch_id = {ph} AND timestamp != '' AND uri_stem != '-'
            GROUP BY minute_slot, uri_stem
            ORDER BY count DESC
            LIMIT 50
        """, (batch_id,))
        minute_by_uri = [
            {"minute_slot": r[0], "uri_stem": r[1], "count": r[2], "avg_time": float(r[3] or 0), "errors": int(r[4] or 0)}
            for r in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT 
                SUBSTR(timestamp, 1, 16) as minute_slot,
                MIN(client_ip) as client_ip,
                {xff_expr} as xff_display,
                COUNT(*) as count,
                ROUND(AVG(time_taken), 1) as avg_time,
                SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
            FROM iis_logs
            WHERE batch_id = {ph} AND timestamp != '' AND (client_ip != '-' OR x_forwarded_for != '-')
            GROUP BY minute_slot, xff_display
            ORDER BY count DESC
            LIMIT 50
        """, (batch_id,))
        minute_by_ip = [
            {
                "minute_slot": r[0],
                "client_ip": r[1],
                "x_forwarded_for": r[2] or '-',
                "count": r[3],
                "avg_time": float(r[4] or 0),
                "errors": int(r[5] or 0)
            }
            for r in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT 
                SUBSTR(timestamp, 1, 16) as minute_slot,
                method,
                COUNT(*) as count,
                ROUND(AVG(time_taken), 1) as avg_time,
                SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
            FROM iis_logs
            WHERE batch_id = {ph} AND timestamp != '' AND method != '-'
            GROUP BY minute_slot, method
            ORDER BY minute_slot DESC, count DESC
            LIMIT 50
        """, (batch_id,))
        minute_by_method = [
            {"minute_slot": r[0], "method": r[1], "count": r[2], "avg_time": float(r[3] or 0), "errors": int(r[4] or 0)}
            for r in cursor.fetchall()
        ]

        # === CONTAGEM CONSOLIDADA GERAL POR IP (SEM REPETIÇÃO DE MINUTOS) ===
        cursor.execute(f"""
            SELECT 
                MIN(client_ip) as client_ip,
                {xff_expr} as xff_display,
                COUNT(*) as count,
                ROUND(AVG(time_taken), 1) as avg_time,
                SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
            FROM iis_logs
            WHERE batch_id = {ph} AND timestamp != '' AND (client_ip != '-' OR x_forwarded_for != '-')
            GROUP BY xff_display
            ORDER BY count DESC
            LIMIT 50
        """, (batch_id,))
        total_by_ip = [
            {
                "client_ip": r[0],
                "x_forwarded_for": r[1] or '-',
                "count": r[2],
                "avg_time": float(r[3] or 0),
                "errors": int(r[4] or 0)
            }
            for r in cursor.fetchall()
        ]

        return {
            "batch_id": batch_id,
            "total_requests": total_requests,
            "unique_ips": unique_ips,
            "total_errors": total_errors,
            "error_rate": error_rate,
            "avg_time": avg_time,
            "max_time": max_time,
            "min_time": min_time,
            "status_groups": status_groups,
            "top_statuses": top_statuses,
            "methods": methods,
            "top_uris": top_uris,
            "top_ips": top_ips,
            "slowest_uris": slowest_uris,
            "timeline": timeline,
            "minute_by_uri": minute_by_uri,
            "minute_by_ip": minute_by_ip,
            "total_by_ip": total_by_ip,
            "minute_by_method": minute_by_method
        }
    finally:
        cursor.close()
        conn.close()

def query_logs(batch_id=None, page=1, per_page=50, status=None, method=None, ip=None, uri=None, min_time=None, xff=None, query_param=None, port=None, sort_by='id', sort_dir='desc'):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if not batch_id:
            batch_id = get_latest_batch_id()

        where_clauses = []
        params = []
        ph = "%s" if DB_TYPE == "postgres" else "?"
        
        if batch_id:
            where_clauses.append(f"batch_id = {ph}")
            params.append(batch_id)

        if status:
            if '-' in str(status):
                parts = status.split('-')
                where_clauses.append(f"status >= {ph} AND status <= {ph}")
                params.extend([int(parts[0]), int(parts[1])])
            elif status.endswith('xx'):
                base = int(status[0]) * 100
                where_clauses.append(f"status >= {ph} AND status < {ph}")
                params.extend([base, base + 100])
            else:
                where_clauses.append(f"status = {ph}")
                params.append(int(status))

        if method:
            where_clauses.append(f"method = {ph}")
            params.append(method.upper())
            
        if ip:
            if DB_TYPE == "postgres":
                where_clauses.append(f"(client_ip ILIKE {ph} OR x_forwarded_for ILIKE {ph})")
            else:
                where_clauses.append(f"(client_ip LIKE {ph} OR x_forwarded_for LIKE {ph})")
            params.extend([f"%{ip}%", f"%{ip}%"])

        if xff:
            if DB_TYPE == "postgres":
                where_clauses.append(f"x_forwarded_for ILIKE {ph}")
            else:
                where_clauses.append(f"x_forwarded_for LIKE {ph}")
            params.append(f"%{xff}%")
            
        if uri:
            if DB_TYPE == "postgres":
                where_clauses.append(f"uri_stem ILIKE {ph}")
            else:
                where_clauses.append(f"uri_stem LIKE {ph}")
            params.append(f"%{uri}%")

        if query_param:
            if DB_TYPE == "postgres":
                where_clauses.append(f"uri_query ILIKE {ph}")
            else:
                where_clauses.append(f"uri_query LIKE {ph}")
            params.append(f"%{query_param}%")

        if port:
            where_clauses.append(f"server_port = {ph}")
            params.append(int(port))
            
        if min_time:
            where_clauses.append(f"time_taken >= {ph}")
            params.append(int(min_time))

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        
        count_query = f"SELECT COUNT(*) FROM iis_logs{where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        
        valid_cols = {'id', 'timestamp', 'client_ip', 'method', 'uri_stem', 'status', 'time_taken', 'server_port', 'x_forwarded_for'}
        if sort_by not in valid_cols:
            sort_by = 'id'
        sort_dir = 'ASC' if sort_dir.lower() == 'asc' else 'DESC'
        
        offset = (page - 1) * per_page
        
        data_query = f"""
            SELECT id, timestamp, client_ip, method, uri_stem, uri_query, status, substatus, 
                   win32_status, time_taken, user_agent, referer, server_ip, server_port, username,
                   x_forwarded_for, raw_log
            FROM iis_logs
            {where_sql}
            ORDER BY {sort_by} {sort_dir}
            LIMIT {ph} OFFSET {ph}
        """
        cursor.execute(data_query, params + [per_page, offset])
        raw_rows = cursor.fetchall()
        
        cols = ['id', 'timestamp', 'client_ip', 'method', 'uri_stem', 'uri_query', 'status', 'substatus', 
                'win32_status', 'time_taken', 'user_agent', 'referer', 'server_ip', 'server_port', 'username',
                'x_forwarded_for', 'raw_log']
        
        rows = [dict(zip(cols, r)) for r in raw_rows]
        total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1
        
        return {
            "records": rows,
            "total": total_records,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "batch_id": batch_id
        }
    finally:
        cursor.close()
        conn.close()

def get_distinct_filter_values(batch_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if not batch_id:
            batch_id = get_latest_batch_id()
        ph = "%s" if DB_TYPE == "postgres" else "?"
        where_batch = f"WHERE batch_id = {ph} AND " if batch_id else "WHERE "

        cursor.execute(f"SELECT DISTINCT method FROM iis_logs {where_batch} method != '-' ORDER BY method", (batch_id,) if batch_id else ())
        methods = [r[0] for r in cursor.fetchall()]
        
        cursor.execute(f"SELECT DISTINCT status FROM iis_logs {where_batch} status != 0 ORDER BY status", (batch_id,) if batch_id else ())
        statuses = [r[0] for r in cursor.fetchall()]

        cursor.execute(f"SELECT DISTINCT server_port FROM iis_logs {where_batch} server_port != 0 ORDER BY server_port", (batch_id,) if batch_id else ())
        ports = [r[0] for r in cursor.fetchall()]
        
        return {
            "methods": methods,
            "statuses": statuses,
            "ports": ports
        }
    except Exception:
        return {"methods": [], "statuses": [], "ports": []}
    finally:
        cursor.close()
        conn.close()
