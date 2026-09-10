import os
import shutil
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import parser
import database

app = Flask(__name__)
app.secret_key = "iis-log-analyzer-secret-key-super-secure"
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024  # Suporte a arquivos de até 2GB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.init_db()

@app.route('/')
def index():
    stats_meta = database.get_stats_meta()
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

    try:
        # Executa o parser multi-core
        records, stats = parser.parse_iis_log_multicore(filepath, max_workers=cores_requested)
        # Salva no banco de dados com índices
        database.save_records(records, stats)
        
        # Limpa arquivo temporário de upload se desejar economizar espaço
        try:
            os.remove(filepath)
        except OSError:
            pass

        return jsonify({
            'success': True,
            'stats': stats,
            'redirect': url_for('dashboard')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard')
def dashboard():
    stats_meta = database.get_stats_meta()
    has_data = bool(stats_meta.get('total_lines'))
    if not has_data:
        flash("Nenhum log carregado ainda. Faça upload de um arquivo para visualizar as métricas.", "warning")
        return redirect(url_for('index'))
    return render_template('dashboard.html', stats=stats_meta)

@app.route('/api/dashboard-data')
def api_dashboard_data():
    data = database.get_dashboard_data()
    if not data:
        return jsonify({'error': 'Nenhum dado encontrado'}), 404
    return jsonify(data)

@app.route('/logs')
def logs():
    stats_meta = database.get_stats_meta()
    has_data = bool(stats_meta.get('total_lines'))
    filter_options = database.get_distinct_filter_values()
    return render_template('logs.html', stats=stats_meta, has_data=has_data, filter_options=filter_options)

@app.route('/api/logs')
def api_logs():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    status = request.args.get('status')
    method = request.args.get('method')
    ip = request.args.get('ip')
    uri = request.args.get('uri')
    min_time = request.args.get('min_time')
    sort_by = request.args.get('sort_by', 'id')
    sort_dir = request.args.get('sort_dir', 'desc')

    result = database.query_logs(
        page=page,
        per_page=per_page,
        status=status,
        method=method,
        ip=ip,
        uri=uri,
        min_time=min_time,
        sort_by=sort_by,
        sort_dir=sort_dir
    )
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
