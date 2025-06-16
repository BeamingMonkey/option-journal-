from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure random key!

# Setup Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

DATABASE = 'trades.db'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id_, username, email, password_hash):
        self.id = id_
        self.username = username
        self.email = email
        self.password_hash = password_hash

    @staticmethod
    def get(user_id):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, password FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return User(*user)
        return None

    @staticmethod
    def get_by_username(username):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return User(*user)
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Initialize DB and create tables
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            email TEXT UNIQUE NOT NULL,
                            password TEXT NOT NULL
                        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            symbol TEXT,
                            entry_price REAL,
                            exit_price REAL,
                            reason TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )''')
        conn.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.get_by_username(username):
            flash('Username already exists')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                           (username, email, password_hash))
            conn.commit()
        except sqlite3.IntegrityError:
            flash('Email already registered')
            return redirect(url_for('register'))
        finally:
            conn.close()

        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.get_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully.')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.')
    return redirect(url_for('index'))

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    symbol = request.form['symbol']
    entry_price = request.form['entry']
    exit_price = request.form['exit']
    reason = request.form['reason']

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO trades (user_id, symbol, entry_price, exit_price, reason) VALUES (?, ?, ?, ?, ?)",
                   (current_user.id, symbol, entry_price, exit_price, reason))
    conn.commit()
    conn.close()
    
    flash('Trade saved successfully!')
    return redirect(url_for('view_trades'))

@app.route('/trades')
@login_required
def view_trades():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, entry_price, exit_price, reason, timestamp FROM trades WHERE user_id = ? ORDER BY timestamp DESC", (current_user.id,))
    rows = cursor.fetchall()
    conn.close()
    return render_template('trades.html', trades=rows)

if __name__ == '__main__':
    app.run(debug=True)
