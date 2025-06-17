from flask import Flask, render_template, request, redirect
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# DB setup
def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT NOT NULL,
                entry REAL NOT NULL,
                exit REAL NOT NULL,
                qty INTEGER NOT NULL,
                currency TEXT NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
init_db()

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute('SELECT id, password FROM users WHERE username = ?', (username,))
            result = c.fetchone()
            if result and password == result[1]:
                user = User(result[0])
                login_user(user)
                return redirect('/')
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            try:
                c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
                conn.commit()
                return redirect('/login')
            except sqlite3.IntegrityError:
                return 'Username already exists.'
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

@app.route('/log', methods=['POST'])
@login_required
def log_trade():
    symbol = request.form['symbol']
    entry = float(request.form['entry'])
    exit_price = float(request.form['exit'])
    qty = int(request.form['qty'])
    currency = request.form['currency']
    reason = request.form['reason']
    user_id = current_user.id

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO trades (user_id, symbol, entry, exit, qty, currency, reason) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, symbol, entry, exit_price, qty, currency, reason))
        conn.commit()
    return redirect('/past')

@app.route('/past')
@login_required
def past_trades():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''
            SELECT symbol, entry, exit, qty, currency, reason, timestamp, 
                   ROUND((exit - entry) * qty, 2) AS pnl 
            FROM trades 
            WHERE user_id = ? 
            ORDER BY timestamp DESC''', (current_user.id,))
        trades = c.fetchall()
    return render_template('past_trades.html', trades=trades)

if __name__ == '__main__':
    app.run(debug=True)