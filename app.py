from flask import Flask, render_template, request, redirect, url_for, session, Response, flash
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg
import os
import csv
from io import StringIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_secret_key_here")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Use environment variable for database
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    """Connect to the PostgreSQL database."""
    return psycopg.connect(DATABASE_URL, sslmode="require")

# User Model
class User(UserMixin):
    def __init__(self, id_, username, password):
        self.id = id_
        self.username = username
        self.password = password

    @staticmethod
    def get(user_id):
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, password FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
        conn.close()
        if row:
            return User(*row)
        return None

    @staticmethod
    def find_by_username(username):
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
        conn.close()
        if row:
            return User(*row)
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

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

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password_hash))
            conn.commit()
        except Exception as e:
            conn.close()
            return f"Username already exists or error: {e}", 409
        conn.close()
        return redirect(url_for("login"))
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
        market_type = request.form.get("market_type")
        entry = float(request.form["entry"])
        exit_price = float(request.form["exit"])
        qty = int(request.form["qty"])
        currency = request.form["currency"]
        reason = request.form["reason"]
        strategy = request.form.get("strategy") or None
        option_contract = request.form.get("option_contract") or None
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pnl = round((exit_price - entry) * qty, 2)

        # Choose symbol based on market_type
        if market_type == "Index":
            symbol = request.form.get("symbol")
        elif market_type == "Option":
            symbol = request.form.get("symbol")  # You can adapt if needed
        else:
            symbol = request.form.get("other_symbol")

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trades 
                    (user_id, market_type, symbol, entry, exit, qty, currency, reason, timestamp, pnl, strategy, option_contract) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                """, (
                    current_user.id,
                    market_type,
                    symbol,
                    entry,
                    exit_price,
                    qty,
                    currency,
                    reason,
                    timestamp,
                    pnl,
                    strategy,
                    option_contract
                ))
            conn.commit()
            flash("Trade logged successfully!", "success")
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error inserting trade: {e}")
            flash(f"Error inserting trade: {e}", "danger")
        finally:
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

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM trades WHERE {where_clause}", values)
        total_trades = cur.fetchone()[0]

        cur.execute(f"""
            SELECT id, symbol, entry, exit, qty, currency, reason, timestamp, pnl, strategy, option_contract
            FROM trades
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """, values + [per_page, offset])
        trades = cur.fetchall()
    conn.close()

    total_pages = (total_trades + per_page - 1) // per_page
    return render_template("past_trades.html",
                           trades=trades,
                           page=page,
                           total_pages=total_pages,
                           symbol=symbol,
                           from_date=from_date,
                           to_date=to_date,
                           min_pnl=min_pnl,
                           max_pnl=max_pnl,
                           strategy=strategy_filter)

@app.route("/export")
@login_required
def export_csv():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT symbol, entry, exit, qty, currency, reason, timestamp, pnl, strategy, option_contract
            FROM trades WHERE user_id = %s
        """, (current_user.id,))
        trades = cur.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Entry", "Exit", "Qty", "Currency", "Reason", "Timestamp", "PnL", "Strategy", "Option Contract"])
    for trade in trades:
        writer.writerow(trade)

    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=trades.csv"})

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COALESCE(SUM(pnl), 0) AS total_pnl,
                COALESCE(MAX(pnl), 0) AS best_trade,
                COALESCE(MIN(pnl), 0) AS worst_trade,
                COUNT(*) AS total_trades
            FROM trades
            WHERE user_id = %s
        """, (current_user.id,))
        stats = cur.fetchone()
    conn.close()
    stats = {
        "total_pnl": stats[0],
        "best_trade": stats[1],
        "worst_trade": stats[2],
        "total_trades": stats[3]
    }
    return render_template("dashboard.html", stats=stats)

# Initialize Database
def init_db():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                market_type TEXT,
                symbol TEXT,
                entry REAL,
                exit REAL,
                qty INTEGER,
                currency TEXT,
                reason TEXT,
                timestamp TIMESTAMP,
                pnl REAL,
                strategy TEXT,
                option_contract TEXT
            );
        """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    app.run(debug=True)