from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
import traceback
from werkzeug.exceptions import HTTPException

app = Flask(__name__, template_folder='templates', static_folder='static')

nodes = [
    {'id': '1', 'url': 'http://localhost:6500'},
    {'id': '2', 'url': 'http://localhost:6501'},
    {'id': '3', 'url': 'http://localhost:6502'},
]

leader_cache = None


@app.errorhandler(Exception)
def handle_uncaught(e):
    if isinstance(e, HTTPException):
        return e
    app.logger.error(f"[Frontend] Необработанное исключение:\n{traceback.format_exc()}")
    return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@app.route('/node/<node_id>', methods=['GET'])
def get_node(node_id):
    node = next((n for n in nodes if n['id'] == node_id), None)
    if not node:
        return jsonify({'error': 'Узел не найден'}), 404

    try:
        r1 = requests.get(f"{node['url']}/state", timeout=1)
        status = r1.json()
    except Exception:
        status = {'state': 'down', 'term': None}

    try:
        r2 = requests.get(f"{node['url']}/message_log", timeout=1)
        logs = r2.json().get('messages', [])
    except Exception:
        logs = []

    return jsonify({'status': status, 'logs': logs}), 200


@app.route('/', methods=['GET'])
def index():
    statuses = {}
    logs = {}
    for node in nodes:
        try:
            r1 = requests.get(f"{node['url']}/state", timeout=1)
            statuses[node['id']] = r1.json()
        except Exception:
            statuses[node['id']] = {'state': 'down', 'term': None}

        try:
            r2 = requests.get(f"{node['url']}/message_log", timeout=1)
            logs[node['id']] = r2.json().get('messages', [])
        except Exception:
            logs[node['id']] = []

    return render_template('index.html',
                           nodes=nodes,
                           statuses=statuses,
                           logs=logs)


@app.route('/send', methods=['POST'])
def send():
    message = request.form.get('message')
    leader = None
    for node in nodes:
        try:
            st = requests.get(f"{node['url']}/state", timeout=2).json()
            if st.get('state') == 'Leader':
                leader = node
                break
        except Exception:
            continue
    if leader:
        try:
            requests.post(f"{leader['url']}/client_request", json={'message': message}, timeout=2)
        except Exception:
            pass
    return redirect(url_for('index'))


@app.route('/kill/<node_id>', methods=['POST'])
def kill(node_id):
    node = next((n for n in nodes if n['id'] == node_id), None)
    if node:
        try:
            requests.post(f"{node['url']}/shutdown", timeout=1)
        except Exception:
            app.logger.warning(f"Не удалось отключить узел {node_id}")
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(port=8000, debug=True)
