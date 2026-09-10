import os
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

def _find_fields_header(filepath):
    """
    Localiza a linha #Fields: no arquivo de log do IIS.
    Retorna a lista de nomes de campos em minúsculas e a posição de início das linhas de dados.
    """
    fields = []
    header_end_pos = 0
    with open(filepath, 'rb') as f:
        while True:
            line_pos = f.tell()
            line = f.readline()
            if not line:
                break
            try:
                decoded = line.decode('utf-8', errors='ignore').strip()
            except Exception:
                continue
            if decoded.startswith('#Fields:'):
                fields = decoded[len('#Fields:'):].strip().split()
                fields = [f.lower() for f in fields]
                header_end_pos = f.tell()
                break
            elif decoded.startswith('#'):
                header_end_pos = f.tell()
                continue
            else:
                # Se começou dados sem encontrar #Fields, rebobina
                header_end_pos = line_pos
                break
    return fields, header_end_pos

def _get_file_chunks(filepath, start_pos, num_chunks):
    """
    Calcula offsets de início e fim alinhados por quebra de linha para processamento paralelo.
    """
    filesize = os.path.getsize(filepath)
    if filesize <= start_pos:
        return []

    chunk_size = (filesize - start_pos) // num_chunks
    if chunk_size == 0:
        return [(start_pos, filesize)]

    chunks = []
    with open(filepath, 'rb') as f:
        current_pos = start_pos
        for i in range(num_chunks):
            if current_pos >= filesize:
                break
            target_pos = current_pos + chunk_size
            if i == num_chunks - 1 or target_pos >= filesize:
                chunks.append((current_pos, filesize))
                break
            
            f.seek(target_pos)
            # Avança até o próximo final de linha para garantir linha completa
            f.readline()
            end_pos = f.tell()
            chunks.append((current_pos, end_pos))
            current_pos = end_pos
            
    return chunks

def _parse_chunk(filepath, start_pos, end_pos, field_indices):
    """
    Worker que processa uma fatia (chunk) do arquivo de log.
    Retorna uma lista de tuplas prontas para inserção rápida no banco.
    """
    records = []
    
    date_idx = field_indices.get('date', -1)
    time_idx = field_indices.get('time', -1)
    s_ip_idx = field_indices.get('s-ip', -1)
    cs_method_idx = field_indices.get('cs-method', -1)
    cs_uri_stem_idx = field_indices.get('cs-uri-stem', -1)
    cs_uri_query_idx = field_indices.get('cs-uri-query', -1)
    s_port_idx = field_indices.get('s-port', -1)
    cs_username_idx = field_indices.get('cs-username', -1)
    c_ip_idx = field_indices.get('c-ip', -1)
    cs_user_agent_idx = field_indices.get('cs(user-agent)', -1)
    cs_referer_idx = field_indices.get('cs(referer)', -1)
    sc_status_idx = field_indices.get('sc-status', -1)
    sc_substatus_idx = field_indices.get('sc-substatus', -1)
    sc_win32_status_idx = field_indices.get('sc-win32-status', -1)
    time_taken_idx = field_indices.get('time-taken', -1)
    # Suporte a variações de x-forwarded-for
    xff_idx = field_indices.get('x-forwarded-for', -1)
    if xff_idx == -1:
        xff_idx = field_indices.get('cs(x-forwarded-for)', -1)

    with open(filepath, 'rb') as f:
        f.seek(start_pos)
        while f.tell() < end_pos:
            line_bytes = f.readline()
            if not line_bytes:
                break
            
            # Pular linhas de comentário do IIS W3C
            if line_bytes.startswith(b'#'):
                continue
                
            line = line_bytes.decode('utf-8', errors='replace').rstrip('\r\n')
            if not line:
                continue

            parts = line.split(' ')
            n_parts = len(parts)

            def get_val(idx, default='-'):
                if 0 <= idx < n_parts:
                    val = parts[idx]
                    return val if val != '-' else default
                return default

            def get_int(idx, default=0):
                if 0 <= idx < n_parts:
                    val = parts[idx]
                    if val.isdigit() or (val.startswith('-') and val[1:].isdigit()):
                        return int(val)
                return default

            log_date = get_val(date_idx, '')
            log_time = get_val(time_idx, '')
            timestamp = f"{log_date} {log_time}".strip()

            c_ip = get_val(c_ip_idx, '-')
            cs_method = get_val(cs_method_idx, '-').upper()
            cs_uri_stem = get_val(cs_uri_stem_idx, '-')
            cs_uri_query = get_val(cs_uri_query_idx, '-')
            sc_status = get_int(sc_status_idx, 0)
            sc_substatus = get_int(sc_substatus_idx, 0)
            sc_win32_status = get_int(sc_win32_status_idx, 0)
            time_taken = get_int(time_taken_idx, 0)
            cs_user_agent = get_val(cs_user_agent_idx, '-')
            cs_referer = get_val(cs_referer_idx, '-')
            s_ip = get_val(s_ip_idx, '-')
            s_port = get_int(s_port_idx, 80)
            cs_username = get_val(cs_username_idx, '-')
            
            # Se x-forwarded-for estiver explícito nos headers ou na última coluna
            x_forwarded_for = '-'
            if xff_idx != -1:
                x_forwarded_for = get_val(xff_idx, '-')
            elif n_parts > len(field_indices) and n_parts >= 15:
                # Caso o log tenha uma coluna extra ao final (comum para XFF em IIS atrás de load balancer)
                x_forwarded_for = parts[-1] if parts[-1] != '-' else '-'

            records.append((
                timestamp,
                log_date,
                log_time,
                c_ip,
                cs_method,
                cs_uri_stem,
                cs_uri_query,
                sc_status,
                sc_substatus,
                sc_win32_status,
                time_taken,
                cs_user_agent,
                cs_referer,
                s_ip,
                s_port,
                cs_username,
                x_forwarded_for,
                line
            ))

    return records

def parse_iis_log_multicore(filepath, max_workers=None):
    """
    Coordena o parsing do arquivo de log do IIS aproveitando múltiplos núcleos da CPU.
    Retorna: (records, stats)
    """
    start_time = time.time()
    
    if max_workers is None:
        max_workers = os.cpu_count() or 4
    
    # 1. Encontra campos no header
    fields, header_end_pos = _find_fields_header(filepath)
    if not fields:
        # Fallback para campos comuns W3C do IIS
        fields = [
            'date', 'time', 's-ip', 'cs-method', 'cs-uri-stem', 'cs-uri-query',
            's-port', 'cs-username', 'c-ip', 'cs(user-agent)', 'cs(referer)',
            'sc-status', 'sc-substatus', 'sc-win32-status', 'time-taken'
        ]
        
    field_indices = {field: idx for idx, field in enumerate(fields)}
    
    # 2. Divide em fatias baseadas no número de workers
    chunks = _get_file_chunks(filepath, header_end_pos, max_workers)
    
    if not chunks:
        return [], {
            "cores_used": max_workers,
            "total_lines": 0,
            "elapsed_seconds": 0.0,
            "fields": fields
        }

    # 3. Execução em paralelo
    all_records = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_parse_chunk, filepath, c_start, c_end, field_indices)
            for (c_start, c_end) in chunks
        ]
        for f in futures:
            all_records.extend(f.result())

    elapsed = round(time.time() - start_time, 3)
    stats = {
        "cores_used": max_workers,
        "total_lines": len(all_records),
        "elapsed_seconds": elapsed,
        "lines_per_second": int(len(all_records) / elapsed) if elapsed > 0 else len(all_records),
        "fields": fields
    }
    
    return all_records, stats
