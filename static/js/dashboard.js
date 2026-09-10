document.addEventListener('DOMContentLoaded', () => {
    fetchDashboardData();
});

async function fetchDashboardData() {
    try {
        const response = await fetch('/api/dashboard-data');
        if (!response.ok) {
            throw new Error('Falha ao carregar dados do dashboard');
        }
        const data = await response.json();
        renderDashboard(data);
    } catch (err) {
        document.getElementById('dashboard-loading').innerHTML = `
            <div style="color: var(--status-5xx);">Erro ao carregar dados do dashboard: ${err.message}</div>
        `;
    }
}

function renderDashboard(data) {
    document.getElementById('dashboard-loading').style.display = 'none';
    document.getElementById('dashboard-content').style.display = 'block';

    // 1. Atualizar KPIs
    document.getElementById('kpi-total-req').textContent = data.total_requests.toLocaleString();
    document.getElementById('kpi-unique-ips').textContent = data.unique_ips.toLocaleString();
    document.getElementById('kpi-error-rate').textContent = `${data.error_rate}%`;
    document.getElementById('kpi-error-sub').textContent = `${data.total_errors.toLocaleString()} erros (4xx/5xx)`;
    document.getElementById('kpi-avg-time').textContent = `${data.avg_time} ms`;
    document.getElementById('kpi-max-time').textContent = `Máx: ${data.max_time.toLocaleString()} ms | Mín: ${data.min_time} ms`;

    // 2. Gráfico Timeline (Line / Bar)
    renderTimelineChart(data.timeline);

    // 3. Gráfico Grupos de Status (Donut)
    renderStatusGroupsChart(data.status_groups);

    // 4. Gráfico Métodos HTTP (Barra horizontal / Polar)
    renderMethodsChart(data.methods);

    // 5. Gráfico Top Status Codes (Bar)
    renderStatusesChart(data.top_statuses);

    // 6. Preencher Tabelas
    renderTopUrisTable(data.top_uris);
    renderTopIpsTable(data.top_ips);
    renderSlowestUrisTable(data.slowest_uris);

    // 7. Preencher Contadores por Minuto (URI Path, IP, Método)
    renderMinuteTables(data);
}

function renderTimelineChart(timeline) {
    const ctx = document.getElementById('chart-timeline').getContext('2d');
    const labels = timeline.map(t => t.time_slot);
    const totals = timeline.map(t => t.count);
    const errors = timeline.map(t => t.errors);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Total de Requisições',
                    data: totals,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.12)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 3,
                    pointBackgroundColor: '#38bdf8'
                },
                {
                    label: 'Erros (>=400)',
                    data: errors,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 3,
                    pointBackgroundColor: '#ef4444'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { family: 'Inter' } }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#64748b', maxRotation: 45, minRotation: 0 },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                y: {
                    ticks: { color: '#64748b' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                }
            }
        }
    });
}

function renderStatusGroupsChart(statusGroups) {
    const ctx = document.getElementById('chart-status-groups').getContext('2d');
    const labels = statusGroups.map(s => s.status_group);
    const counts = statusGroups.map(s => s.count);

    const colorsMap = {
        '2xx Success': '#10b981',
        '3xx Redirect': '#38bdf8',
        '4xx Client Error': '#f59e0b',
        '5xx Server Error': '#ef4444',
        'Other': '#8b5cf6'
    };

    const backgroundColors = labels.map(l => colorsMap[l] || '#94a3b8');

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: counts,
                backgroundColor: backgroundColors,
                borderWidth: 2,
                borderColor: '#121826'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', font: { family: 'Inter' } }
                }
            },
            cutout: '68%'
        }
    });
}

function renderMethodsChart(methods) {
    const ctx = document.getElementById('chart-methods').getContext('2d');
    const labels = methods.map(m => m.method);
    const counts = methods.map(m => m.count);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Requisições',
                data: counts,
                backgroundColor: [
                    '#38bdf8',
                    '#10b981',
                    '#fbbf24',
                    '#ef4444',
                    '#8b5cf6',
                    '#06b6d4'
                ],
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { display: false }
                },
                y: {
                    ticks: { color: '#64748b' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                }
            }
        }
    });
}

function renderStatusesChart(topStatuses) {
    const ctx = document.getElementById('chart-statuses').getContext('2d');
    const labels = topStatuses.map(s => `HTTP ${s.status}`);
    const counts = topStatuses.map(s => s.count);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Ocorrências',
                data: counts,
                backgroundColor: '#6366f1',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { display: false }
                },
                y: {
                    ticks: { color: '#64748b' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                }
            }
        }
    });
}

function renderTopUrisTable(topUris) {
    const tbody = document.getElementById('top-uris-tbody');
    tbody.innerHTML = topUris.map(u => `
        <tr>
            <td style="font-family: monospace; font-size: 0.82rem; color: #38bdf8; max-width: 320px; overflow: hidden; text-overflow: ellipsis;">
                ${escapeHtml(u.uri_stem)}
            </td>
            <td style="text-align: right; font-weight: 600;">${u.count.toLocaleString()}</td>
            <td style="text-align: right; color: var(--text-secondary);">${u.avg_time} ms</td>
        </tr>
    `).join('');
}

function renderTopIpsTable(topIps) {
    const tbody = document.getElementById('top-ips-tbody');
    tbody.innerHTML = topIps.map(ip => {
        const hasXff = ip.x_forwarded_for && ip.x_forwarded_for !== '-';
        const displayLabel = hasXff
            ? `<span style="color: #f8fafc;">${escapeHtml(ip.client_ip)}</span> <span style="color: var(--text-muted); font-size: 0.76rem;">&rarr;</span> <span style="color: var(--accent-cyan); font-weight: 600;">${escapeHtml(ip.x_forwarded_for)}</span>`
            : `<span style="color: #f8fafc;">${escapeHtml(ip.client_ip)}</span>`;
        const filterVal = hasXff ? ip.x_forwarded_for : ip.client_ip;

        return `
            <tr>
                <td style="font-family: monospace; font-size: 0.83rem; max-width: 320px; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(ip.client_ip)} - ${escapeHtml(ip.x_forwarded_for || '-')}">
                    ${displayLabel}
                </td>
                <td style="text-align: right; font-weight: 600;">${ip.count.toLocaleString()}</td>
                <td style="text-align: right;">
                    <a href="/logs?ip=${encodeURIComponent(filterVal)}" class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.75rem;">
                        Filtrar Logs
                    </a>
                </td>
            </tr>
        `;
    }).join('');
}

function renderSlowestUrisTable(slowestUris) {
    const tbody = document.getElementById('slowest-uris-tbody');
    tbody.innerHTML = slowestUris.map(s => `
        <tr>
            <td style="font-family: monospace; font-size: 0.82rem; color: #fbbf24; max-width: 450px; overflow: hidden; text-overflow: ellipsis;">
                ${escapeHtml(s.uri_stem)}
            </td>
            <td style="text-align: right; font-weight: 600; color: var(--status-4xx);">${s.avg_time} ms</td>
            <td style="text-align: right; color: var(--text-muted);">${s.max_time.toLocaleString()} ms</td>
            <td style="text-align: right; font-weight: 500;">${s.count.toLocaleString()}</td>
        </tr>
    `).join('');
}

// === RENDERIZAÇÃO E ORDENAÇÃO DOS CONTADORES POR MINUTO ===

let minuteDataCache = {
    uri: [],
    ip: [],
    method: []
};

let minuteSortState = {
    uri: { field: 'count', dir: 'desc' },
    ip: { field: 'count', dir: 'desc' },
    method: { field: 'count', dir: 'desc' }
};

function renderMinuteTables(data) {
    minuteDataCache.uri = data.minute_by_uri || [];
    minuteDataCache.ip = data.minute_by_ip || [];
    minuteDataCache.method = data.minute_by_method || [];

    setupMinuteTableSorting();
    refreshMinuteTable('uri');
    refreshMinuteTable('ip');
    refreshMinuteTable('method');
}

function setupMinuteTableSorting() {
    document.querySelectorAll('.sortable-th[data-table]').forEach(th => {
        // Remover listeners antigos clonando o nó se necessário
        const newTh = th.cloneNode(true);
        th.parentNode.replaceChild(newTh, th);
        
        newTh.addEventListener('click', () => {
            const tableKey = newTh.getAttribute('data-table');
            const field = newTh.getAttribute('data-field');
            const state = minuteSortState[tableKey];

            if (state.field === field) {
                state.dir = (state.dir === 'asc') ? 'desc' : 'asc';
            } else {
                state.field = field;
                state.dir = 'desc';
            }

            updateMinuteSortIcons(tableKey);
            refreshMinuteTable(tableKey);
        });
    });
}

function updateMinuteSortIcons(tableKey) {
    const state = minuteSortState[tableKey];
    const fields = ['count', 'avg_time', 'errors'];
    
    fields.forEach(f => {
        const icon = document.getElementById(`sort-icon-${tableKey}-${f}`);
        const th = document.querySelector(`.sortable-th[data-table="${tableKey}"][data-field="${f}"]`);
        if (!icon) return;

        if (state.field === f) {
            if (th) th.classList.add('active-sort');
            icon.textContent = (state.dir === 'asc') ? '▲' : '▼';
        } else {
            if (th) th.classList.remove('active-sort');
            icon.textContent = '↕';
        }
    });
}

function refreshMinuteTable(tableKey) {
    let items = [...(minuteDataCache[tableKey] || [])];
    const state = minuteSortState[tableKey];

    items.sort((a, b) => {
        let valA = a[state.field];
        let valB = b[state.field];

        if (typeof valA === 'string') {
            valA = parseFloat(valA) || 0;
            valB = parseFloat(valB) || 0;
        }

        if (valA < valB) return state.dir === 'asc' ? -1 : 1;
        if (valA > valB) return state.dir === 'asc' ? 1 : -1;
        return 0;
    });

    if (tableKey === 'uri') renderMinuteByUri(items);
    else if (tableKey === 'ip') renderMinuteByIp(items);
    else if (tableKey === 'method') renderMinuteByMethod(items);
}

function renderMinuteByUri(items) {
    const tbody = document.getElementById('minute-uri-tbody');
    if (!tbody) return;
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhum dado por minuto disponível.</td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(item => `
        <tr>
            <td style="font-family: monospace; font-size: 0.82rem; color: var(--text-secondary);">${escapeHtml(item.minute_slot)}</td>
            <td style="font-family: monospace; font-size: 0.82rem; color: #38bdf8; max-width: 380px; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.uri_stem)}</td>
            <td style="text-align: right; font-weight: 700; color: #f8fafc;">${item.count.toLocaleString()}</td>
            <td style="text-align: right; color: var(--text-secondary);">${item.avg_time} ms</td>
            <td style="text-align: right; font-weight: 600; color: ${item.errors > 0 ? 'var(--status-5xx)' : 'var(--text-muted)'};">${item.errors}</td>
        </tr>
    `).join('');
}

function renderMinuteByIp(items) {
    const tbody = document.getElementById('minute-ip-tbody');
    if (!tbody) return;
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhum dado por minuto disponível.</td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(item => {
        const hasXff = item.x_forwarded_for && item.x_forwarded_for !== '-';
        const displayLabel = hasXff
            ? `<span style="color: #f8fafc;">${escapeHtml(item.client_ip)}</span> <span style="color: var(--text-muted); font-size: 0.76rem;">&rarr;</span> <span style="color: var(--accent-cyan); font-weight: 600;">${escapeHtml(item.x_forwarded_for)}</span>`
            : `<span style="color: #f8fafc;">${escapeHtml(item.client_ip)}</span>`;
        const filterVal = hasXff ? item.x_forwarded_for : item.client_ip;

        return `
            <tr>
                <td style="font-family: monospace; font-size: 0.82rem; color: var(--text-secondary);">${escapeHtml(item.minute_slot)}</td>
                <td style="font-family: monospace; font-size: 0.83rem; max-width: 320px; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(item.client_ip)} - ${escapeHtml(item.x_forwarded_for || '-')}">
                    ${displayLabel}
                </td>
                <td style="text-align: right; font-weight: 700; color: #f8fafc;">${item.count.toLocaleString()}</td>
                <td style="text-align: right; color: var(--text-secondary);">${item.avg_time} ms</td>
                <td style="text-align: right; font-weight: 600; color: ${item.errors > 0 ? 'var(--status-5xx)' : 'var(--text-muted)'};">${item.errors}</td>
                <td style="text-align: right;">
                    <a href="/logs?ip=${encodeURIComponent(filterVal)}" class="btn btn-secondary" style="padding: 3px 8px; font-size: 0.72rem;">
                        Filtrar
                    </a>
                </td>
            </tr>
        `;
    }).join('');
}

function renderMinuteByMethod(items) {
    const tbody = document.getElementById('minute-method-tbody');
    if (!tbody) return;
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhum dado por minuto disponível.</td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(item => `
        <tr>
            <td style="font-family: monospace; font-size: 0.82rem; color: var(--text-secondary);">${escapeHtml(item.minute_slot)}</td>
            <td><span class="method-tag method-${item.method}">${escapeHtml(item.method)}</span></td>
            <td style="text-align: right; font-weight: 700; color: #f8fafc;">${item.count.toLocaleString()}</td>
            <td style="text-align: right; color: var(--text-secondary);">${item.avg_time} ms</td>
            <td style="text-align: right; font-weight: 600; color: ${item.errors > 0 ? 'var(--status-5xx)' : 'var(--text-muted)'};">${item.errors}</td>
        </tr>
    `).join('');
}

function switchMinuteTab(tab) {
    const tabs = ['uri', 'ip', 'method'];
    tabs.forEach(t => {
        const content = document.getElementById(`tab-content-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (t === tab) {
            if (content) content.style.display = 'block';
            if (btn) {
                btn.className = 'btn btn-primary';
            }
        } else {
            if (content) content.style.display = 'none';
            if (btn) {
                btn.className = 'btn btn-secondary';
            }
        }
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
