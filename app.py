from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

DATABASE = "trading_journal.db"

# --- DB Setup ---
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# --- User Class ---
class User(UserMixin):
    def __init__(self, id_, username, password):
        self.id = id_
        self.username = username
        self.password = password

    @staticmethod
    def get(user_id):
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        db.close()
        if not user:
            return None
        return User(user["id"], user["username"], user["password"])

    @staticmethod
    def find_by_username(username):
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        if not user:
            return None
        return User(user["id"], user["username"], user["password"])

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Routes ---

@app.route("/")
@login_required
def index():
    return render_template("index.html", username=current_user.username)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            return "Passwords do not match", 400

        password_hash = generate_password_hash(password)
        try:
            db = get_db()
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password_hash))
            db.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Username already exists", 409
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.find_by_username(username)
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("index"))
        return "Invalid credentials", 401
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/log", methods=["GET", "POST"])
@login_required
def log_trade():
    if request.method == "POST":
        symbol = request.form["symbol"]
        entry = float(request.form["entry"])
        exit_price = float(request.form["exit"])
        qty = int(request.form["qty"])
        currency = request.form["currency"]
        reason = request.form["reason"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pnl = round((exit_price - entry) * qty, 2)

        db = get_db()
        db.execute(
            "INSERT INTO trades (user_id, symbol, entry, exit, qty, currency, reason, timestamp, pnl) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (current_user.id, symbol, entry, exit_price, qty, currency, reason, timestamp, pnl)
        )
        db.commit()
        return redirect(url_for("past_trades"))
    return render_template("log_trade.html")

@app.route("/past")
@login_required
def past_trades():
    db = get_db()
    trades = db.execute(
        "SELECT symbol, entry, exit, qty, currency, reason, timestamp, pnl FROM trades WHERE user_id = ? ORDER BY timestamp DESC",
        (current_user.id,)
    ).fetchall()
    return render_template("past_trades.html", trades=trades)

# --- Initialize DB ---
def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT,
            entry REAL,
            exit REAL,
            qty INTEGER,
            currency TEXT,
            reason TEXT,
            timestamp TEXT,
            pnl REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    db.commit()

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
