from flask import Flask, render_template, request, redirect, url_for, session, Response
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import psycopg2
import os
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Database connection using DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# --- User Class ---
class User(UserMixin):
    def __init__(self, id_, username, password):
        self.id = id_
        self.username = username
        self.password = password

    @staticmethod
    def get(user_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return User(*row)
        return None

    @staticmethod
    def find_by_username(username):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        conn.close()
        if row:
            return User(*row)
        return None

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
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password_hash))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except Exception as e:
            return f"Username already exists or DB error: {e}", 409
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

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trades (user_id, symbol, entry, exit, qty, currency, reason, timestamp, pnl, strategy)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user.id, symbol, entry, exit_price, qty, currency, reason, timestamp, pnl, strategy))
        conn.commit()
        conn.close()
        return redirect(url_for("past_trades"))
    return render_template("log_trade.html")

@app.route("/past")
@login_required
def past_trades():
    symbol = request.args.get("symbol")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    min_pnl = request.args.get("min_pnl")
    max_pnl = request.args.get("max_pnl")
    strategy_filter = request.args.get("strategy")
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    filters = ["user_id = %s"]
    values = [current_user.id]

    if symbol:
        filters.append("symbol ILIKE %s")
        values.append(f"%{symbol}%")
    if from_date:
        filters.append("timestamp::date >= %s")
        values.append(from_date)
    if to_date:
        filters.append("timestamp::date <= %s")
        values.append(to_date)
    if min_pnl:
        filters.append("pnl >= %s")
        values.append(min_pnl)
    if max_pnl:
        filters.append("pnl <= %s")
        values.append(max_pnl)
    if strategy_filter:
        filters.append("strategy ILIKE %s")
        values.append(f"%{strategy_filter}%")

    where_clause = " AND ".join(filters)
    base_query = f"FROM trades WHERE {where_clause}"

    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) {base_query}", tuple(values))
    total_trades = cur.fetchone()[0]

    cur.execute(f"""
        SELECT id, symbol, entry, exit, qty, currency, reason, timestamp, pnl, strategy
        {base_query}
        ORDER BY timestamp DESC LIMIT %s OFFSET %s
    """, tuple(values + [per_page, offset]))
    trades = cur.fetchall()
    conn.close()

    total_pages = (total_trades + per_page - 1) // per_page

    return render_template("past_trades.html", trades=trades, page=page, total_pages=total_pages)

@app.route("/export")
@login_required
def export_csv():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT symbol, entry, exit, qty, currency, reason, timestamp, pnl, strategy FROM trades WHERE user_id = %s", (current_user.id,))
    trades = cur.fetchall()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Entry", "Exit", "Qty", "Currency", "Reason", "Timestamp", "PnL", "Strategy"])
    for trade in trades:
        writer.writerow(trade)
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=trades.csv"})

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            COALESCE(SUM(pnl), 0),
            COALESCE(MAX(pnl), 0),
            COALESCE(MIN(pnl), 0),
            COUNT(*)
        FROM trades WHERE user_id = %s
    """, (current_user.id,))
    total_pnl, best_trade, worst_trade, total_trades = cur.fetchone()
    conn.close()

    stats = {
        "total_pnl": total_pnl,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "total_trades": total_trades
    }
    return render_template("dashboard.html", stats=stats)

# --- Initialize DB ---
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            symbol TEXT,
            entry REAL,
            exit REAL,
            qty INTEGER,
            currency TEXT,
            reason TEXT,
            timestamp TIMESTAMP,
            pnl REAL,
            strategy TEXT
        )
    """)
    conn.commit()
    conn.close()

# Initialize DB only once on startup
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
