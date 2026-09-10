let currentPage = 1;
let currentPerPage = 50;
let currentSortBy = 'id';
let currentSortDir = 'desc';
let logsCache = [];

document.addEventListener('DOMContentLoaded', () => {
    // Pré-preencher filtro de IP se vier da query string
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('ip')) {
        document.getElementById('filter-ip').value = urlParams.get('ip');
    }

    fetchLogs();

    // Eventos de clique nas colunas ordenáveis
    document.querySelectorAll('.sortable-th').forEach(th => {
        th.addEventListener('click', () => {
            const sortBy = th.getAttribute('data-sort');
            if (currentSortBy === sortBy) {
                // Alterna entre asc e desc
                currentSortDir = (currentSortDir === 'asc') ? 'desc' : 'asc';
            } else {
                currentSortBy = sortBy;
                currentSortDir = (sortBy === 'time_taken') ? 'desc' : 'desc';
            }
            currentPage = 1;
            updateSortIcons();
            fetchLogs();
        });
    });

    document.getElementById('btn-apply-filters').addEventListener('click', () => {
        currentPage = 1;
        fetchLogs();
    });

    document.getElementById('btn-reset-filters').addEventListener('click', () => {
        document.getElementById('filter-status').value = '';
        document.getElementById('filter-method').value = '';
        document.getElementById('filter-ip').value = '';
        document.getElementById('filter-uri').value = '';
        document.getElementById('filter-min-time').value = '';
        currentSortBy = 'id';
        currentSortDir = 'desc';
        currentPage = 1;
        updateSortIcons();
        fetchLogs();
    });

    document.getElementById('per-page-select').addEventListener('change', (e) => {
        currentPerPage = parseInt(e.target.value);
        currentPage = 1;
        fetchLogs();
    });

    document.getElementById('btn-prev-page').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            fetchLogs();
        }
    });

    document.getElementById('btn-next-page').addEventListener('click', () => {
        currentPage++;
        fetchLogs();
    });

    // Fechar modal
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('log-modal').addEventListener('click', (e) => {
        if (e.target.id === 'log-modal') closeModal();
    });
});

function updateSortIcons() {
    document.querySelectorAll('.sortable-th').forEach(th => {
        const field = th.getAttribute('data-sort');
        const icon = document.getElementById(`sort-icon-${field}`);
        if (!icon) return;

        if (currentSortBy === field) {
            th.classList.add('active-sort');
            icon.textContent = (currentSortDir === 'asc') ? '▲' : '▼';
        } else {
            th.classList.remove('active-sort');
            icon.textContent = '↕';
        }
    });
}

async function fetchLogs() {
    const status = document.getElementById('filter-status').value;
    const method = document.getElementById('filter-method').value;
    const ip = document.getElementById('filter-ip').value.trim();
    const uri = document.getElementById('filter-uri').value.trim();
    const minTime = document.getElementById('filter-min-time').value.trim();

    const params = new URLSearchParams({
        page: currentPage,
        per_page: currentPerPage,
        sort_by: currentSortBy,
        sort_dir: currentSortDir
    });

    if (status) params.append('status', status);
    if (method) params.append('method', method);
    if (ip) params.append('ip', ip);
    if (uri) params.append('uri', uri);
    if (minTime) params.append('min_time', minTime);

    const tbody = document.getElementById('logs-tbody');
    tbody.innerHTML = `
        <tr>
            <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                Carregando registros...
            </td>
        </tr>
    `;

    try {
        const res = await fetch(`/api/logs?${params.toString()}`);
        if (!res.ok) throw new Error('Erro na requisição');
        const data = await res.json();
        
        logsCache = data.records;
        renderLogsTable(data);
    } catch (err) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px; color: var(--status-5xx);">
                    Erro ao carregar logs: ${err.message}
                </td>
            </tr>
        `;
    }
}

function renderLogsTable(data) {
    const tbody = document.getElementById('logs-tbody');
    document.getElementById('table-total-count').textContent = data.total.toLocaleString();
    document.getElementById('current-page-num').textContent = data.page;
    document.getElementById('total-pages-num').textContent = data.total_pages;

    document.getElementById('btn-prev-page').disabled = (data.page <= 1);
    document.getElementById('btn-next-page').disabled = (data.page >= data.total_pages);

    if (!data.records || data.records.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    Nenhum registro encontrado para os filtros selecionados.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = data.records.map((r, idx) => {
        const statusClass = getStatusClass(r.status);
        const methodClass = `method-${r.method || 'GET'}`;
        
        return `
            <tr>
                <td style="color: var(--text-muted); font-size: 0.8rem;">#${r.id}</td>
                <td style="font-size: 0.82rem; color: var(--text-secondary);">${escapeHtml(r.timestamp)}</td>
                <td style="font-family: monospace; font-size: 0.84rem;">${escapeHtml(r.client_ip)}</td>
                <td><span class="method-tag ${methodClass}">${escapeHtml(r.method)}</span></td>
                <td style="font-family: monospace; font-size: 0.82rem; max-width: 320px; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(r.uri_stem)}">
                    ${escapeHtml(r.uri_stem)}
                </td>
                <td><span class="status-pill ${statusClass}">${r.status}</span></td>
                <td style="font-weight: 500; font-size: 0.82rem; color: ${r.time_taken > 1000 ? '#f59e0b' : 'var(--text-secondary)'};">
                    ${r.time_taken} ms
                </td>
                <td>
                    <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.75rem;" onclick="viewDetails(${idx})">
                        Ver Mais
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function getStatusClass(status) {
    if (status >= 200 && status < 300) return 'status-2xx';
    if (status >= 300 && status < 400) return 'status-3xx';
    if (status >= 400 && status < 500) return 'status-4xx';
    if (status >= 500) return 'status-5xx';
    return '';
}

function viewDetails(index) {
    const item = logsCache[index];
    if (!item) return;

    const modalContent = document.getElementById('modal-content');
    modalContent.innerHTML = `
        <div style="display: grid; grid-template-columns: 140px 1fr; gap: 10px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">
            <strong style="color: var(--text-muted);">Timestamp:</strong>
            <div>${escapeHtml(item.timestamp)} UTC</div>
            <strong style="color: var(--text-muted);">IP do Cliente:</strong>
            <div style="font-family: monospace;">${escapeHtml(item.client_ip)}</div>
            <strong style="color: var(--text-muted);">Método HTTP:</strong>
            <div><span class="method-tag method-${item.method}">${escapeHtml(item.method)}</span></div>
            <strong style="color: var(--text-muted);">URI / Endpoint:</strong>
            <div style="font-family: monospace; color: #38bdf8; word-break: break-all;">${escapeHtml(item.uri_stem)}</div>
            <strong style="color: var(--text-muted);">Query String:</strong>
            <div style="font-family: monospace; word-break: break-all;">${item.uri_query !== '-' ? escapeHtml(item.uri_query) : '<span style="color: var(--text-muted);">Nenhuma</span>'}</div>
            <strong style="color: var(--text-muted);">Status HTTP:</strong>
            <div><span class="status-pill ${getStatusClass(item.status)}">${item.status}</span> (Sub: ${item.substatus}, Win32: ${item.win32_status})</div>
            <strong style="color: var(--text-muted);">Tempo de Resposta:</strong>
            <div style="font-weight: 600;">${item.time_taken} ms</div>
            <strong style="color: var(--text-muted);">Servidor / Porta:</strong>
            <div>${escapeHtml(item.server_ip)}:${item.server_port}</div>
            <strong style="color: var(--text-muted);">Usuário Autenticado:</strong>
            <div>${item.username !== '-' ? escapeHtml(item.username) : '<span style="color: var(--text-muted);">Anônimo (-)</span>'}</div>
            <strong style="color: var(--text-muted);">Referer:</strong>
            <div style="word-break: break-all;">${item.referer !== '-' ? escapeHtml(item.referer) : '<span style="color: var(--text-muted);">-</span>'}</div>
            <strong style="color: var(--text-muted);">User-Agent:</strong>
            <div style="font-size: 0.8rem; color: var(--text-secondary); word-break: break-all; background: rgba(0,0,0,0.25); padding: 8px; border-radius: 6px;">
                ${escapeHtml(item.user_agent)}
            </div>
        </div>
    `;

    const modal = document.getElementById('log-modal');
    modal.style.display = 'flex';
}

function closeModal() {
    document.getElementById('log-modal').style.display = 'none';
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
