from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3

app = Flask(__name__)
app.secret_key = "super_secret_bank_key"

def init_db():
    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()
    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            pin TEXT NOT NULL,
            balance REAL DEFAULT 0.0
        )
    """)
    # Transactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return render_template("dashboard.html", name=session["user_name"])

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    pin = data.get("pin", "").strip()

    if not name or not email or not pin:
        return jsonify({"message": "All fields are required"}), 400

    conn = sqlite3.connect("bank.db")
    try:
        conn.execute("INSERT INTO users (name, email, pin, balance) VALUES (?, ?, ?, 1000.0)", (name, email, pin))
        conn.commit()
        msg = "Registration successful! Initial balance of ₹1000 added."
        code = 200
    except sqlite3.IntegrityError:
        msg = "Email already registered."
        code = 400
    finally:
        conn.close()
    return jsonify({"message": msg}), code

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "").strip().lower()
    pin = data.get("pin", "").strip()

    conn = sqlite3.connect("bank.db")
    user = conn.execute("SELECT id, name FROM users WHERE email = ? AND pin = ?", (email, pin)).fetchone()
    conn.close()

    if user:
        session["user_id"] = user[0]
        session["user_name"] = user[1]
        return jsonify({"message": "Login successful!"})
    return jsonify({"message": "Invalid email or PIN"}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/get_account_data")
def get_account_data():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()
    
    balance = cursor.execute("SELECT balance FROM users WHERE id = ?", (session["user_id"],)).fetchone()[0]
    
    tx_rows = cursor.execute(
        "SELECT type, amount, timestamp FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 5",
        (session["user_id"],)
    ).fetchall()
    
    conn.close()
    
    transactions = [{"type": row[0], "amount": row[1], "timestamp": row[2]} for row in tx_rows]
    return jsonify({"balance": balance, "transactions": transactions})

@app.route("/transaction", methods=["POST"])
def transaction():
    if "user_id" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json
    tx_type = data.get("type") 
    try:
        amount = float(data.get("amount", 0))
    except ValueError:
        return jsonify({"message": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"message": "Amount must be greater than zero"}), 400

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()
    
    current_balance = cursor.execute("SELECT balance FROM users WHERE id = ?", (session["user_id"],)).fetchone()[0]

    if tx_type == "withdraw" and amount > current_balance:
        conn.close()
        return jsonify({"message": "Insufficient funds!"}), 400

    new_balance = current_balance + amount if tx_type == "deposit" else current_balance - amount
    
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, session["user_id"]))
    cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)",
                   (session["user_id"], tx_type.capitalize(), amount))
    conn.commit()
    conn.close()

    return jsonify({"message": f"{tx_type.capitalize()} of ₹{amount} successful!", "new_balance": new_balance})

if __name__ == "__main__":
    app.run(debug=True)



@app.route("/transfer", methods=["POST"])
def transfer():
    if "user_id" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json
    recipient_email = data.get("email", "").strip().lower()
    try:
        amount = float(data.get("amount", 0))
    except ValueError:
        return jsonify({"message": "Invalid amount"}), 400

    if amount <= 0:
        return jsonify({"message": "Amount must be greater than zero"}), 400

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    # Get sender info
    sender = cursor.execute("SELECT email, balance FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    sender_email, sender_balance = sender[0], sender[1]

    if recipient_email == sender_email:
        conn.close()
        return jsonify({"message": "You cannot transfer money to yourself!"}), 400

    # Check recipient
    recipient = cursor.execute("SELECT id, balance FROM users WHERE email = ?", (recipient_email,)).fetchone()
    if not recipient:
        conn.close()
        return jsonify({"message": "Recipient email not found!"}), 404

    recipient_id, recipient_balance = recipient[0], recipient[1]

    if amount > sender_balance:
        conn.close()
        return jsonify({"message": "Insufficient funds!"}), 400

    # Perform transfer
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (sender_balance - amount, session["user_id"]))
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (recipient_balance + amount, recipient_id))

    # Log transactions
    cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)",
                   (session["user_id"], f"Transfer Out to {recipient_email}", amount))
    cursor.execute("INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)",
                   (recipient_id, f"Transfer In from {sender_email}", amount))

    conn.commit()
    conn.close()

    return jsonify({"message": f"Successfully transferred ₹{amount} to {recipient_email}!"})