from flask import Flask, render_template, request, redirect
import sqlite3
import os

app = Flask(__name__)

# DB Setup: create table if it doesn't exist
def init_db():
    with sqlite3.connect("trades.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            symbol TEXT,
                            entry_price REAL,
                            exit_price REAL,
                            reason TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                        )''')
        conn.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    symbol = request.form['symbol']
    entry_price = request.form['entry']
    exit_price = request.form['exit']
    reason = request.form['reason']

    with sqlite3.connect("trades.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trades (symbol, entry_price, exit_price, reason) VALUES (?, ?, ?, ?)",
                       (symbol, entry_price, exit_price, reason))
        conn.commit()
    
    return redirect('/trades')

@app.route('/trades')
def view_trades():
    with sqlite3.connect("trades.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, entry_price, exit_price, reason, timestamp FROM trades ORDER BY timestamp DESC")
        rows = cursor.fetchall()
    return render_template('trades.html', trades=rows)

if __name__ == '__main__':
    app.run(debug=True)
