import sqlite3

conn = sqlite3.connect("bank.db")
cursor = conn.cursor()

print("--- USERS ---")
users = cursor.execute("SELECT * FROM users").fetchall()
for user in users:
    print(user)

print("\n--- TRANSACTIONS ---")
transactions = cursor.execute("SELECT * FROM transactions").fetchall()
for tx in transactions:
    print(tx)

conn.close()