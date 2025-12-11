"""
Lecture 5: Docker Demo Application
A simple Task Manager to demonstrate Docker concepts

This app demonstrates:
- Flask web application
- PostgreSQL for persistent storage
- Redis for caching and session data
- Multi-container orchestration with Docker Compose
"""

import os
import json
import socket
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import redis

app = Flask(__name__, static_folder='assets', static_url_path='/assets')
app.secret_key = os.environ.get('SECRET_KEY', 'devops-lecture5-secret-key')

# Configuration from environment variables (Docker best practice!)
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'taskdb')
DB_USER = os.environ.get('DB_USER', 'taskuser')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'taskpass')

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))


def get_redis():
    """Get Redis connection with error handling"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        return r
    except redis.ConnectionError:
        print(f"Warning: Redis not available at {REDIS_HOST}:{REDIS_PORT}")
        return None


def get_db_connection():
    """Get PostgreSQL connection with error handling"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Warning: Database not available: {e}")
        return None


def init_db():
    """Create tables if they don't exist"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    status VARCHAR(20) DEFAULT 'pending',
                    priority VARCHAR(10) DEFAULT 'medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            cur.close()
            conn.close()
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Database initialization error: {e}")


# Initialize on startup
with app.app_context():
    init_db()


# ============== ROUTES ==============

@app.route('/')
def index():
    """Main page - show all tasks"""
    tasks = []
    stats = {'total': 0, 'pending': 0, 'in_progress': 0, 'completed': 0}
    db_status = "disconnected"
    cache_status = "disconnected"
    cache_hit = False
    
    # Check Redis for cached tasks
    r = get_redis()
    if r:
        cache_status = "connected"
        cached_tasks = r.get('tasks_cache')
        if cached_tasks:
            tasks = json.loads(cached_tasks)
            cache_hit = True
            cached_stats = r.get('tasks_stats')
            if cached_stats:
                stats = json.loads(cached_stats)
    
    # If no cache, get from database
    if not cache_hit:
        conn = get_db_connection()
        if conn:
            db_status = "connected"
            try:
                cur = conn.cursor()
                cur.execute('SELECT * FROM tasks ORDER BY created_at DESC')
                tasks = [dict(row) for row in cur.fetchall()]
                
                # Convert datetime objects to strings for JSON serialization
                for task in tasks:
                    if task.get('created_at'):
                        task['created_at'] = task['created_at'].isoformat()
                    if task.get('updated_at'):
                        task['updated_at'] = task['updated_at'].isoformat()
                
                # Calculate stats
                cur.execute('SELECT COUNT(*) as count FROM tasks')
                stats['total'] = cur.fetchone()['count']
                cur.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'pending'")
                stats['pending'] = cur.fetchone()['count']
                cur.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'in_progress'")
                stats['in_progress'] = cur.fetchone()['count']
                cur.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'completed'")
                stats['completed'] = cur.fetchone()['count']
                
                cur.close()
                conn.close()
                
                # Cache the results for 30 seconds
                if r:
                    r.setex('tasks_cache', 30, json.dumps(tasks))
                    r.setex('tasks_stats', 30, json.dumps(stats))
                    
            except Exception as e:
                print(f"Database error: {e}")
    
    return render_template('index.html', 
                         tasks=tasks, 
                         stats=stats,
                         db_status=db_status,
                         cache_status=cache_status,
                         cache_hit=cache_hit)


@app.route('/add', methods=['POST'])
def add_task():
    """Add a new task"""
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'medium')
    
    if not title:
        flash('Task title is required!', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO tasks (title, description, priority) VALUES (%s, %s, %s)',
                (title, description, priority)
            )
            conn.commit()
            cur.close()
            conn.close()
            
            # Invalidate cache
            r = get_redis()
            if r:
                r.delete('tasks_cache', 'tasks_stats')
            
            flash(f'Task "{title}" added!', 'success')
        except Exception as e:
            flash(f'Error adding task: {e}', 'error')
    else:
        flash('Database not available!', 'error')
    
    return redirect(url_for('index'))


@app.route('/update/<int:task_id>', methods=['POST'])
def update_task(task_id):
    """Update task status"""
    status = request.form.get('status', 'pending')
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                'UPDATE tasks SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
                (status, task_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            
            # Invalidate cache
            r = get_redis()
            if r:
                r.delete('tasks_cache', 'tasks_stats')
            
            flash('Task updated!', 'success')
        except Exception as e:
            flash(f'Error updating task: {e}', 'error')
    
    return redirect(url_for('index'))


@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    """Delete a task"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM tasks WHERE id = %s', (task_id,))
            conn.commit()
            cur.close()
            conn.close()
            
            # Invalidate cache
            r = get_redis()
            if r:
                r.delete('tasks_cache', 'tasks_stats')
            
            flash('Task deleted!', 'success')
        except Exception as e:
            flash(f'Error deleting task: {e}', 'error')
    
    return redirect(url_for('index'))


@app.route('/health')
def health():
    """Health check endpoint - useful for Kubernetes!"""
    db_ok = False
    redis_ok = False
    
    conn = get_db_connection()
    if conn:
        db_ok = True
        conn.close()
    
    r = get_redis()
    if r:
        redis_ok = True
    
    status = {
        'status': 'healthy' if (db_ok and redis_ok) else 'degraded',
        'database': 'connected' if db_ok else 'disconnected',
        'cache': 'connected' if redis_ok else 'disconnected',
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(status), 200 if status['status'] == 'healthy' else 503


@app.route('/info')
def info():
    """Show environment info - demonstrates Docker env vars"""
    return jsonify({
        'app': 'DevOps Lecture 5 Demo',
        'version': '1.0.0',
        'pod_name': socket.gethostname(),
        'environment': {
            'DB_HOST': DB_HOST,
            'DB_PORT': DB_PORT,
            'DB_NAME': DB_NAME,
            'REDIS_HOST': REDIS_HOST,
            'REDIS_PORT': REDIS_PORT
        },
        'message': 'Configuration from environment variables!'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)