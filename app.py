from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

# Archivo para persistir las tareas
TASKS_FILE = 'tasks.json'


def load_tasks():
    """Carga las tareas desde el archivo JSON"""
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []


def save_tasks(tasks):
    """Guarda las tareas en el archivo JSON"""
    with open(TASKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


@app.route('/')
def index():
    """Página principal con la lista de tareas"""
    tasks = load_tasks()
    return render_template('index.html', tasks=tasks)


@app.route('/add', methods=['POST'])
def add_task():
    """Agregar nueva tarea"""
    task_text = request.form.get('task', '').strip()
    if task_text:
        tasks = load_tasks()
        new_task = {
            'id': len(tasks) + 1,
            'text': task_text,
            'completed': False,
            'created_at': datetime.now().isoformat()
        }
        tasks.append(new_task)
        save_tasks(tasks)
    return redirect(url_for('index'))


@app.route('/toggle/<int:task_id>')
def toggle_task(task_id):
    """Cambiar estado de completado de una tarea"""
    tasks = load_tasks()
    for task in tasks:
        if task['id'] == task_id:
            task['completed'] = not task['completed']
            break
    save_tasks(tasks)
    return redirect(url_for('index'))


@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    """Eliminar una tarea"""
    tasks = load_tasks()
    tasks = [task for task in tasks if task['id'] != task_id]
    save_tasks(tasks)
    return redirect(url_for('index'))


@app.route('/api/tasks', methods=['GET'])
def api_get_tasks():
    """API endpoint para obtener todas las tareas"""
    tasks = load_tasks()
    return jsonify(tasks)


@app.route('/api/tasks', methods=['POST'])
def api_add_task():
    """API endpoint para agregar una tarea"""
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Text is required'}), 400

    tasks = load_tasks()
    new_task = {
        'id': len(tasks) + 1,
        'text': data['text'],
        'completed': False,
        'created_at': datetime.now().isoformat()
    }
    tasks.append(new_task)
    save_tasks(tasks)
    return jsonify(new_task), 201


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    # Configurar puerto y host desde variables de entorno
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_ENV') == 'development'

    print(f"[FLASK] Iniciando Flask en {host}:{port}")
    print(f"[FLASK] Modo debug: {debug}")

    app.run(debug=debug, host=host, port=port)