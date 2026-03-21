"""User search API endpoint."""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/users/search")
def search_users():
    query = request.args.get("q", "")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # BUG: SQL injection — user input interpolated directly into query string
    results = cursor.execute(
        f"SELECT id, name, email FROM users WHERE name LIKE '%{query}%'"
    ).fetchall()
    conn.close()
    return jsonify([{"id": r[0], "name": r[1], "email": r[2]} for r in results])


if __name__ == "__main__":
    app.run(debug=True)
