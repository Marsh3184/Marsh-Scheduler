# --- Flask App: Marsh Scheduler with Journal and Pushover ---
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import time

# Pushover credentials
PUSHOVER_USER_KEY = "u54nq29vztde5znk8nb38989x9xyhq"
PUSHOVER_APP_TOKEN = "a9vonav4pk9qnp9t6gofw4sevs38wy"

def send_pushover_alert(message, title="Marsh Scheduler"):
    data = {
        "token": PUSHOVER_APP_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message,
        "title": title
    }
    requests.post("https://api.pushover.net/1/messages.json", data=data)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
app.secret_key = 'fmub osfs jyxw onrf'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)

@app.template_filter('format_date')
def format_date(value):
    try:
        parsed_date = datetime.strptime(value, "%Y-%m-%d")
        return parsed_date.strftime("%B %d, %Y")
    except:
        return value

@app.template_filter('format_time')
def format_time(value):
    try:
        parsed_time = datetime.strptime(value, "%H:%M")
        return parsed_time.strftime("%I:%M %p").lstrip("0")
    except:
        return value
    
from zoneinfo import ZoneInfo

@app.template_filter('localtime')
def localtime(value):
    try:
        return value.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
    except:
        return value


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'Chris' and password == 'Newme2019':
            session['logged_in'] = True
            flash("Logged in successfully.")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash("Logged out.")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    tasks = Task.query.order_by(Task.date, Task.time).all()
    return render_template('index.html', tasks=tasks)

# --- Models ---
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(10), nullable=False)
    notified_30min = db.Column(db.Boolean, default=False)

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/add', methods=['POST'])
def add():
    task_text = request.form['task']
    task_date = request.form['date']
    task_time = request.form['time']
    new_task = Task(task=task_text, date=task_date, time=task_time)
    db.session.add(new_task)
    db.session.commit()

  # Notify 30 seconds after creation
    def notify_30s():
        time.sleep(30)
        task_dt = datetime.strptime(f"{task_date} {task_time}", "%Y-%m-%d %H:%M")
        formatted_date = task_dt.strftime("%B %d, %Y")
        formatted_time = task_dt.strftime("%I:%M %p").lstrip("0")
        send_pushover_alert(
        f"Task '{task_text}' was just scheduled for {formatted_date} at {formatted_time}.",
        "Task Created"
    )

    from threading import Thread
    Thread(target=notify_30s).start()

    flash("Task added successfully.")
    return redirect(url_for('index'))


@app.route('/edit_task/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_task(id):
    task = Task.query.get_or_404(id)
    if request.method == 'POST':
        task.task = request.form['task']
        task.date = request.form['date']
        task.time = request.form['time']
        db.session.commit()
        flash('Task updated successfully.')
        return redirect(url_for('index'))
    return render_template('edit_task.html', task=task)

@app.route('/delete_task/<int:id>')
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully.')
    return redirect(url_for('index'))

@app.route('/journal', methods=['GET', 'POST'])
@login_required
def journal():
    if request.method == 'POST':
        content = request.form['content']
        entry_id = request.form.get('entry_id')
        if entry_id:
            entry = JournalEntry.query.get(entry_id)
            if entry:
                entry.content = content
        else:
            entry = JournalEntry(content=content)
            db.session.add(entry)
        db.session.commit()
        flash("Journal entry saved.")
        return redirect(url_for('journal'))

    entries = JournalEntry.query.order_by(JournalEntry.timestamp.desc()).all()
    return render_template('journal.html', entries=entries)

@app.route('/edit_journal/<int:id>')
def edit_journal(id):
    entry = JournalEntry.query.get_or_404(id)
    entries = JournalEntry.query.order_by(JournalEntry.timestamp.desc()).all()
    return render_template('journal.html', entries=entries, edit_entry=entry)

@app.route('/delete_journal/<int:id>')
@login_required
def delete_journal(id):
    entry = JournalEntry.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    flash("Journal entry deleted.")
    return redirect(url_for('journal'))

# Background scheduler: notify 30 minutes before
def check_tasks():
    now = datetime.now()
    tasks = Task.query.all()
    for task in tasks:
        if not task.notified_30min:
            task_dt = datetime.strptime(f"{task.date} {task.time}", "%Y-%m-%d %H:%M")
            if task_dt - timedelta(minutes=30) <= now < task_dt:
                formatted_date = task_dt.strftime("%B %d, %Y")
                formatted_time = task_dt.strftime("%I:%M %p").lstrip("0")
                send_pushover_alert(
                    f"Task '{task.task}' is due in 30 minutes on {formatted_date} at {formatted_time}.",
                    "Upcoming Task"
                )
                task.notified_30min = True
                db.session.commit()


scheduler = BackgroundScheduler()
scheduler.add_job(func=check_tasks, trigger="interval", seconds=60)
scheduler.start()

with app.app_context():
    # db.drop_all()
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
