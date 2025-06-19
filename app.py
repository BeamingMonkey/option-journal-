from flask import Flask, render_template, request, redirect, url_for, session, Response
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import csv
from io import StringIO
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_secret_key_here")

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
        strategy = request.form.get("strategy", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pnl = round((exit_price - entry) * qty, 2)

        db = get_db()
        db.execute(
            """INSERT INTO trades (user_id, symbol, entry, exit, qty, currency, reason, timestamp, pnl, strategy)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (current_user.id, symbol, entry, exit_price, qty, currency, reason, timestamp, pnl, strategy)
        )
        db.commit()
        return redirect(url_for("past_trades"))
    return render_template("log_trade.html")

@app.route("/past")
@login_required
def past_trades():
    # Filters
    symbol = request.args.get("symbol")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    min_pnl = request.args.get("min_pnl")
    max_pnl = request.args.get("max_pnl")
    strategy_filter = request.args.get("strategy")

    # Pagination
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    # Build query with filters
    query = "SELECT * FROM trades WHERE user_id = ?"
    params = [current_user.id]

    if symbol:
        query += " AND symbol LIKE ?"
        params.append(f"%{symbol}%")
    if from_date:
        query += " AND date(timestamp) >= date(?)"
        params.append(from_date)
    if to_date:
        query += " AND date(timestamp) <= date(?)"
        params.append(to_date)
    if min_pnl:
        query += " AND pnl >= ?"
        params.append(min_pnl)
    if max_pnl:
        query += " AND pnl <= ?"
        params.append(max_pnl)
    if strategy_filter:
        query += " AND strategy LIKE ?"
        params.append(f"%{strategy_filter}%")

    total_count_query = "SELECT COUNT(*) FROM (" + query + ")"
    db = get_db()
    total_trades = db.execute(total_count_query, params).fetchone()[0]

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    trades = db.execute(query, params).fetchall()

    total_pages = (total_trades + per_page - 1) // per_page

    return render_template("past_trades.html", trades=trades, page=page, total_pages=total_pages,
                           symbol=symbol, from_date=from_date, to_date=to_date,
                           min_pnl=min_pnl, max_pnl=max_pnl, strategy=strategy_filter)

@app.route("/export")
@login_required
def export_csv():
    db = get_db()
    trades = db.execute("SELECT * FROM trades WHERE user_id = ?", (current_user.id,)).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(trades[0].keys() if trades else [])
    for row in trades:
        writer.writerow([row[key] for key in row.keys()])

    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=trades.csv"})

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    stats = db.execute("""
        SELECT 
            SUM(pnl) as total_pnl,
            MAX(pnl) as best_trade,
            MIN(pnl) as worst_trade,
            COUNT(*) as total_trades
        FROM trades WHERE user_id = ?
    """, (current_user.id,)).fetchone()
    return render_template("dashboard.html", stats=stats)

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
            strategy TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    db.commit()

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
