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
            CREATE TABLE IF NOT EXISTS iis_logs (
                id SERIAL PRIMARY KEY,
                timestamp VARCHAR(64),
                log_date VARCHAR(32),
                log_time VARCHAR(32),
                client_ip VARCHAR(64),
                method VARCHAR(16),
                uri_stem TEXT,
                uri_query TEXT,
                status INT,
                substatus INT,
                win32_status INT,
                time_taken INT,
                user_agent TEXT,
                referer TEXT,
                server_ip VARCHAR(64),
                server_port INT,
                username VARCHAR(128)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_meta (
                key VARCHAR(64) PRIMARY KEY,
                value TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON iis_logs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_method ON iis_logs(method)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_ip ON iis_logs(client_ip)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uri_stem ON iis_logs(uri_stem)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_taken ON iis_logs(time_taken)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON iis_logs(timestamp)")

        conn.commit()
        cursor.close()
        conn.close()
    else:
        conn = get_connection()
        cursor = conn.cursor()
        if drop_existing:
            cursor.execute("DROP TABLE IF EXISTS iis_logs")
            cursor.execute("DROP TABLE IF EXISTS analysis_meta")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS iis_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                username TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON iis_logs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_method ON iis_logs(method)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_ip ON iis_logs(client_ip)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uri_stem ON iis_logs(uri_stem)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_taken ON iis_logs(time_taken)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON iis_logs(timestamp)")

        conn.commit()
        cursor.close()
        conn.close()

def save_records(records, stats):
    init_db(drop_existing=True)
    conn = get_connection()
    cursor = conn.cursor()

    if DB_TYPE == "postgres":
        import psycopg2.extras
        insert_sql = """
            INSERT INTO iis_logs (
                timestamp, log_date, log_time, client_ip, method, uri_stem,
                uri_query, status, substatus, win32_status, time_taken,
                user_agent, referer, server_ip, server_port, username
            ) VALUES %s
        """
        psycopg2.extras.execute_values(cursor, insert_sql, records, page_size=2000)

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
                timestamp, log_date, log_time, client_ip, method, uri_stem,
                uri_query, status, substatus, win32_status, time_taken,
                user_agent, referer, server_ip, server_port, username
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.executemany(insert_sql, records)

        for k, v in stats.items():
            cursor.execute("INSERT OR REPLACE INTO analysis_meta (key, value) VALUES (?, ?)", (k, str(v)))

    conn.commit()
    cursor.close()
    conn.close()

def get_stats_meta():
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

def get_dashboard_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM iis_logs")
        row = cursor.fetchone()
        total_requests = row[0] if row else 0
        if total_requests == 0:
            return None

        cursor.execute("""
            SELECT 
                AVG(time_taken) as avg_time,
                MAX(time_taken) as max_time,
                MIN(time_taken) as min_time
            FROM iis_logs
        """)
        t_row = cursor.fetchone()
        avg_time = round(float(t_row[0] or 0), 1)
        max_time = t_row[1] or 0
        min_time = t_row[2] or 0

        cursor.execute("""
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
            GROUP BY status_group
            ORDER BY count DESC
        """)
        status_groups = [{"status_group": r[0], "count": r[1]} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM iis_logs 
            GROUP BY status 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_statuses = [{"status": r[0], "count": r[1]} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT method, COUNT(*) as count 
            FROM iis_logs 
            GROUP BY method 
            ORDER BY count DESC
        """)
        methods = [{"method": r[0], "count": r[1]} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT uri_stem, COUNT(*) as count, ROUND(AVG(time_taken), 1) as avg_time
            FROM iis_logs 
            GROUP BY uri_stem 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_uris = [{"uri_stem": r[0], "count": r[1], "avg_time": float(r[2] or 0)} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT client_ip, COUNT(*) as count 
            FROM iis_logs 
            GROUP BY client_ip 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_ips = [{"client_ip": r[0], "count": r[1]} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT uri_stem, ROUND(AVG(time_taken), 1) as avg_time, MAX(time_taken) as max_time, COUNT(*) as count
            FROM iis_logs
            GROUP BY uri_stem
            ORDER BY avg_time DESC
            LIMIT 10
        """)
        slowest_uris = [{"uri_stem": r[0], "avg_time": float(r[1] or 0), "max_time": r[2], "count": r[3]} for r in cursor.fetchall()]

        cursor.execute("SELECT COUNT(DISTINCT SUBSTR(timestamp, 1, 13)) FROM iis_logs")
        hours_count = cursor.fetchone()[0]
        
        if hours_count <= 2:
            cursor.execute("""
                SELECT SUBSTR(timestamp, 1, 16) as time_slot, COUNT(*) as count,
                       SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
                FROM iis_logs
                WHERE timestamp != ''
                GROUP BY time_slot
                ORDER BY time_slot ASC
                LIMIT 60
            """)
        else:
            if DB_TYPE == "postgres":
                cursor.execute("""
                    SELECT CONCAT(SUBSTR(timestamp, 1, 13), ':00') as time_slot, COUNT(*) as count,
                           SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
                    FROM iis_logs
                    WHERE timestamp != ''
                    GROUP BY time_slot
                    ORDER BY time_slot ASC
                    LIMIT 48
                """)
            else:
                cursor.execute("""
                    SELECT SUBSTR(timestamp, 1, 13) || ':00' as time_slot, COUNT(*) as count,
                           SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
                    FROM iis_logs
                    WHERE timestamp != ''
                    GROUP BY time_slot
                    ORDER BY time_slot ASC
                    LIMIT 48
                """)
        timeline = [{"time_slot": r[0], "count": r[1], "errors": int(r[2] or 0)} for r in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM iis_logs WHERE status >= 400")
        total_errors = cursor.fetchone()[0]
        error_rate = round((total_errors / total_requests * 100), 2) if total_requests > 0 else 0

        cursor.execute("SELECT COUNT(DISTINCT client_ip) FROM iis_logs")
        unique_ips = cursor.fetchone()[0]

        # === CONTADORES POR MINUTO ===
        cursor.execute("""
            SELECT 
                SUBSTR(timestamp, 1, 16) as minute_slot,
                uri_stem,
                COUNT(*) as count,
                ROUND(AVG(time_taken), 1) as avg_time,
                SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
            FROM iis_logs
            WHERE timestamp != '' AND uri_stem != '-'
            GROUP BY minute_slot, uri_stem
            ORDER BY count DESC
            LIMIT 50
        """)
        minute_by_uri = [
            {"minute_slot": r[0], "uri_stem": r[1], "count": r[2], "avg_time": float(r[3] or 0), "errors": int(r[4] or 0)}
            for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT 
                SUBSTR(timestamp, 1, 16) as minute_slot,
                client_ip,
                COUNT(*) as count,
                ROUND(AVG(time_taken), 1) as avg_time,
                SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
            FROM iis_logs
            WHERE timestamp != '' AND client_ip != '-'
            GROUP BY minute_slot, client_ip
            ORDER BY count DESC
            LIMIT 50
        """)
        minute_by_ip = [
            {"minute_slot": r[0], "client_ip": r[1], "count": r[2], "avg_time": float(r[3] or 0), "errors": int(r[4] or 0)}
            for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT 
                SUBSTR(timestamp, 1, 16) as minute_slot,
                method,
                COUNT(*) as count,
                ROUND(AVG(time_taken), 1) as avg_time,
                SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
            FROM iis_logs
            WHERE timestamp != '' AND method != '-'
            GROUP BY minute_slot, method
            ORDER BY minute_slot DESC, count DESC
            LIMIT 50
        """)
        minute_by_method = [
            {"minute_slot": r[0], "method": r[1], "count": r[2], "avg_time": float(r[3] or 0), "errors": int(r[4] or 0)}
            for r in cursor.fetchall()
        ]

        return {
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
            "minute_by_method": minute_by_method
        }
    finally:
        cursor.close()
        conn.close()

def query_logs(page=1, per_page=50, status=None, method=None, ip=None, uri=None, min_time=None, sort_by='id', sort_dir='desc'):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        where_clauses = []
        params = []
        ph = "%s" if DB_TYPE == "postgres" else "?"
        
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
                where_clauses.append(f"client_ip ILIKE {ph}")
            else:
                where_clauses.append(f"client_ip LIKE {ph}")
            params.append(f"%{ip}%")
            
        if uri:
            if DB_TYPE == "postgres":
                where_clauses.append(f"uri_stem ILIKE {ph}")
            else:
                where_clauses.append(f"uri_stem LIKE {ph}")
            params.append(f"%{uri}%")
            
        if min_time:
            where_clauses.append(f"time_taken >= {ph}")
            params.append(int(min_time))

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        
        count_query = f"SELECT COUNT(*) FROM iis_logs{where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        
        valid_cols = {'id', 'timestamp', 'client_ip', 'method', 'uri_stem', 'status', 'time_taken'}
        if sort_by not in valid_cols:
            sort_by = 'id'
        sort_dir = 'ASC' if sort_dir.lower() == 'asc' else 'DESC'
        
        offset = (page - 1) * per_page
        
        data_query = f"""
            SELECT id, timestamp, client_ip, method, uri_stem, uri_query, status, substatus, 
                   win32_status, time_taken, user_agent, referer, server_ip, server_port, username
            FROM iis_logs
            {where_sql}
            ORDER BY {sort_by} {sort_dir}
            LIMIT {ph} OFFSET {ph}
        """
        cursor.execute(data_query, params + [per_page, offset])
        raw_rows = cursor.fetchall()
        
        cols = ['id', 'timestamp', 'client_ip', 'method', 'uri_stem', 'uri_query', 'status', 'substatus', 
                'win32_status', 'time_taken', 'user_agent', 'referer', 'server_ip', 'server_port', 'username']
        
        rows = [dict(zip(cols, r)) for r in raw_rows]
        total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1
        
        return {
            "records": rows,
            "total": total_records,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }
    finally:
        cursor.close()
        conn.close()

def get_distinct_filter_values():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT method FROM iis_logs WHERE method != '-' ORDER BY method")
        methods = [r[0] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT status FROM iis_logs WHERE status != 0 ORDER BY status")
        statuses = [r[0] for r in cursor.fetchall()]
        
        return {
            "methods": methods,
            "statuses": statuses
        }
    except Exception:
        return {"methods": [], "statuses": []}
    finally:
        cursor.close()
        conn.close()
