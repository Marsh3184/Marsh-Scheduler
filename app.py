# --- Flask App: Marsh Scheduler with Journal and Email ---
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
from flask import session

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


app = Flask(__name__)
app.secret_key = 'fmub osfs jyxw onrf'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
db = SQLAlchemy(app)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'Chris' and password == 'Newme2019':  # <-- customize this
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
    flash("Task added successfully.")
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

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
