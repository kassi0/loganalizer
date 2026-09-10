import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "logs_analysis.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(drop_existing=False):
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
    
    # Criar índices para consultas ultra rápidas
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON iis_logs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_method ON iis_logs(method)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_ip ON iis_logs(client_ip)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_uri_stem ON iis_logs(uri_stem)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_taken ON iis_logs(time_taken)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON iis_logs(timestamp)")
    
    conn.commit()
    conn.close()

def save_records(records, stats):
    init_db(drop_existing=True)
    conn = get_connection()
    cursor = conn.cursor()
    
    # Inserção em lote otimizada
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
    
    # Salvar metadados
    for k, v in stats.items():
        cursor.execute("INSERT OR REPLACE INTO analysis_meta (key, value) VALUES (?, ?)", (k, str(v)))
        
    conn.commit()
    conn.close()

def get_stats_meta():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM analysis_meta")
        rows = cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}
    finally:
        conn.close()

def get_dashboard_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Total de requisições
        cursor.execute("SELECT COUNT(*) as total FROM iis_logs")
        row = cursor.fetchone()
        total_requests = row["total"] if row else 0
        if total_requests == 0:
            return None

        # Estatísticas de tempo de resposta (time-taken em ms)
        cursor.execute("""
            SELECT 
                AVG(time_taken) as avg_time,
                MAX(time_taken) as max_time,
                MIN(time_taken) as min_time
            FROM iis_logs
        """)
        t_row = cursor.fetchone()
        avg_time = round(t_row["avg_time"] or 0, 1)
        max_time = t_row["max_time"] or 0
        min_time = t_row["min_time"] or 0

        # Distribuição de códigos HTTP por categoria
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
        status_groups = [dict(r) for r in cursor.fetchall()]

        # Top 10 Status Codes exatos
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM iis_logs 
            GROUP BY status 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_statuses = [dict(r) for r in cursor.fetchall()]

        # Distribuição de Métodos HTTP
        cursor.execute("""
            SELECT method, COUNT(*) as count 
            FROM iis_logs 
            GROUP BY method 
            ORDER BY count DESC
        """)
        methods = [dict(r) for r in cursor.fetchall()]

        # Top 10 URLs mais requisitadas
        cursor.execute("""
            SELECT uri_stem, COUNT(*) as count, ROUND(AVG(time_taken), 1) as avg_time
            FROM iis_logs 
            GROUP BY uri_stem 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_uris = [dict(r) for r in cursor.fetchall()]

        # Top 10 IPs de clientes com mais requisições
        cursor.execute("""
            SELECT client_ip, COUNT(*) as count 
            FROM iis_logs 
            GROUP BY client_ip 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_ips = [dict(r) for r in cursor.fetchall()]

        # Top 10 URLs Mais Lentas (Maior latência média com pelo menos 2 hits)
        cursor.execute("""
            SELECT uri_stem, ROUND(AVG(time_taken), 1) as avg_time, MAX(time_taken) as max_time, COUNT(*) as count
            FROM iis_logs
            GROUP BY uri_stem
            ORDER BY avg_time DESC
            LIMIT 10
        """)
        slowest_uris = [dict(r) for r in cursor.fetchall()]

        # Requisições ao longo do tempo (agrupado por hora ou por minuto)
        # Identificar se a granularidade deve ser por hora ou minuto
        cursor.execute("SELECT COUNT(DISTINCT SUBSTR(timestamp, 1, 13)) as hours_count FROM iis_logs")
        hours_count = cursor.fetchone()["hours_count"]
        
        # Se poucos intervalos de hora, agrupa por intervalo de 5 minutos, senão por hora
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
            cursor.execute("""
                SELECT SUBSTR(timestamp, 1, 13) || ':00' as time_slot, COUNT(*) as count,
                       SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) as errors
                FROM iis_logs
                WHERE timestamp != ''
                GROUP BY time_slot
                ORDER BY time_slot ASC
                LIMIT 48
            """)
        timeline = [dict(r) for r in cursor.fetchall()]

        # Total de erros (4xx + 5xx)
        cursor.execute("SELECT COUNT(*) as errors FROM iis_logs WHERE status >= 400")
        total_errors = cursor.fetchone()["errors"]
        error_rate = round((total_errors / total_requests * 100), 2) if total_requests > 0 else 0

        # Total de IPs únicos
        cursor.execute("SELECT COUNT(DISTINCT client_ip) as unique_ips FROM iis_logs")
        unique_ips = cursor.fetchone()["unique_ips"]

        # === CONTADORES POR MINUTO (URI PATH, IP, MÉTODO) ===
        # 1. Contadores por Minuto + URI Path (Top combinações minuto e URI)
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
        minute_by_uri = [dict(r) for r in cursor.fetchall()]

        # 2. Contadores por Minuto + IP de Cliente (Top combinações minuto e IP)
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
        minute_by_ip = [dict(r) for r in cursor.fetchall()]

        # 3. Contadores por Minuto + Método HTTP
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
        minute_by_method = [dict(r) for r in cursor.fetchall()]

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
        conn.close()

def query_logs(page=1, per_page=50, status=None, method=None, ip=None, uri=None, min_time=None, sort_by='id', sort_dir='desc'):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        where_clauses = []
        params = []
        
        if status:
            if '-' in str(status):
                # Suporte a range de status, ex: 400-499
                parts = status.split('-')
                where_clauses.append("status >= ? AND status <= ?")
                params.extend([int(parts[0]), int(parts[1])])
            elif status.endswith('xx'):
                base = int(status[0]) * 100
                where_clauses.append("status >= ? AND status < ?")
                params.extend([base, base + 100])
            else:
                where_clauses.append("status = ?")
                params.append(int(status))

        if method:
            where_clauses.append("method = ?")
            params.append(method.upper())
            
        if ip:
            where_clauses.append("client_ip LIKE ?")
            params.append(f"%{ip}%")
            
        if uri:
            where_clauses.append("uri_stem LIKE ?")
            params.append(f"%{uri}%")
            
        if min_time:
            where_clauses.append("time_taken >= ?")
            params.append(int(min_time))

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        
        # Obter contagem total com filtros
        count_query = f"SELECT COUNT(*) as total FROM iis_logs{where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()["total"]
        
        # Validar ordenação
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
            LIMIT ? OFFSET ?
        """
        cursor.execute(data_query, params + [per_page, offset])
        rows = [dict(r) for r in cursor.fetchall()]
        
        total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1
        
        return {
            "records": rows,
            "total": total_records,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }
    finally:
        conn.close()

def get_distinct_filter_values():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT method FROM iis_logs WHERE method != '-' ORDER BY method")
        methods = [r["method"] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT status FROM iis_logs WHERE status != 0 ORDER BY status")
        statuses = [r["status"] for r in cursor.fetchall()]
        
        return {
            "methods": methods,
            "statuses": statuses
        }
    except Exception:
        return {"methods": [], "statuses": []}
    finally:
        conn.close()
