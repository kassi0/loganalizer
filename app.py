import os
import shutil
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import parser
import database

app = Flask(__name__)
app.secret_key = "iis-log-analyzer-secret-key-super-secure"
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024  # Suporte a arquivos de até 2GB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.init_db()

@app.before_request
def auto_cleanup():
    """Executa limpeza defensiva de lotes expirados (mais de 24h e não persistentes)."""
    if not request.path.startswith('/static'):
        database.cleanup_expired_batches()

@app.context_processor
def inject_global_data():
    """Injeta lotes disponíveis e lote atual nos templates."""
    batches = database.list_batches()
    current_batch_id = request.args.get('batch_id', type=int) or session.get('active_batch_id')
    if not current_batch_id and batches:
        current_batch_id = batches[0]['id']
    
    current_batch = None
    if current_batch_id:
        for b in batches:
            if b['id'] == current_batch_id:
                current_batch = b
                break

    return {
        'all_batches': batches,
        'active_batch_id': current_batch_id,
        'active_batch': current_batch,
        'total_batches_count': len(batches)
    }

@app.route('/')
def index():
    batch_id = request.args.get('batch_id', type=int) or session.get('active_batch_id')
    stats_meta = database.get_stats_meta(batch_id=batch_id)
    has_data = bool(stats_meta.get('total_lines'))
    return render_template('index.html', stats=stats_meta, has_data=has_data, cpu_count=os.cpu_count() or 4)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'logfile' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado.'}), 400
        
    file = request.files['logfile']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nome de arquivo inválido.'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    cores_requested = request.form.get('cores')
    try:
        cores_requested = int(cores_requested) if cores_requested else os.cpu_count()
    except ValueError:
        cores_requested = os.cpu_count()

    is_persistent = request.form.get('is_persistent') == 'true' or request.form.get('is_persistent') == '1'

    try:
        # Executa o parser multi-core
        records, stats = parser.parse_iis_log_multicore(filepath, max_workers=cores_requested)
        # Salva o lote no banco de dados
        batch_id = database.save_records(records, stats, filename=filename, is_persistent=is_persistent)
        session['active_batch_id'] = batch_id
        
        # Limpa arquivo temporário de upload para economizar espaço
        try:
            os.remove(filepath)
        except OSError:
            pass

        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'stats': stats,
            'redirect': url_for('dashboard', batch_id=batch_id)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/history')
def history():
    batches = database.list_batches()
    return render_template('history.html', batches=batches)

@app.route('/api/batches')
def api_batches():
    batches = database.list_batches()
    return jsonify(batches)

@app.route('/api/batches/<int:batch_id>/toggle-persist', methods=['POST'])
def api_toggle_persist(batch_id):
    result = database.toggle_batch_persistence(batch_id)
    if not result:
        return jsonify({'success': False, 'error': 'Lote não encontrado.'}), 404
    return jsonify({'success': True, 'data': result})

@app.route('/api/batches/<int:batch_id>/delete', methods=['POST', 'DELETE'])
def api_delete_batch(batch_id):
    database.delete_batch(batch_id)
    if session.get('active_batch_id') == batch_id:
        session.pop('active_batch_id', None)
    return jsonify({'success': True, 'message': 'Análise excluída com sucesso.'})

@app.route('/dashboard')
def dashboard():
    batch_id = request.args.get('batch_id', type=int) or session.get('active_batch_id')
    if batch_id:
        session['active_batch_id'] = batch_id
    stats_meta = database.get_stats_meta(batch_id=batch_id)
    has_data = bool(stats_meta.get('total_lines'))
    if not has_data:
        flash("Nenhum log carregado ainda ou a análise foi removida. Faça upload de um arquivo para visualizar as métricas.", "warning")
        return redirect(url_for('index'))
    return render_template('dashboard.html', stats=stats_meta, batch_id=batch_id)

@app.route('/api/dashboard-data')
def api_dashboard_data():
    batch_id = request.args.get('batch_id', type=int) or session.get('active_batch_id')
    include_port_param = request.args.get('include_port', 'true').lower()
    include_port = include_port_param not in ('false', '0', 'no')

    data = database.get_dashboard_data(batch_id=batch_id, include_port=include_port)
    if not data:
        return jsonify({'error': 'Nenhum dado encontrado'}), 404
    return jsonify(data)

@app.route('/logs')
def logs():
    batch_id = request.args.get('batch_id', type=int) or session.get('active_batch_id')
    if batch_id:
        session['active_batch_id'] = batch_id
    stats_meta = database.get_stats_meta(batch_id=batch_id)
    has_data = bool(stats_meta.get('total_lines'))
    filter_options = database.get_distinct_filter_values(batch_id=batch_id)
    return render_template('logs.html', stats=stats_meta, has_data=has_data, filter_options=filter_options, batch_id=batch_id)

@app.route('/api/logs')
def api_logs():
    batch_id = request.args.get('batch_id', type=int) or session.get('active_batch_id')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    status = request.args.get('status')
    method = request.args.get('method')
    ip = request.args.get('ip')
    uri = request.args.get('uri')
    min_time = request.args.get('min_time')
    xff = request.args.get('xff')
    query_param = request.args.get('query')
    port = request.args.get('port')
    sort_by = request.args.get('sort_by', 'id')
    sort_dir = request.args.get('sort_dir', 'desc')

    result = database.query_logs(
        batch_id=batch_id,
        page=page,
        per_page=per_page,
        status=status,
        method=method,
        ip=ip,
        uri=uri,
        min_time=min_time,
        xff=xff,
        query_param=query_param,
        port=port,
        sort_by=sort_by,
        sort_dir=sort_dir
    )
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

