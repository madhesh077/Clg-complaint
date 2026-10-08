from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "college_complaint_secret_key")
DB_PATH = os.environ.get("DB_PATH", "college.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn


def create_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            register_number TEXT NOT NULL,
            department TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT id FROM admins WHERE username = ?", ("admin",))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    cursor.execute("PRAGMA table_info(complaints)")
    columns = [column[1] for column in cursor.fetchall()]

    if "student_id" not in columns:
        cursor.execute("ALTER TABLE complaints ADD COLUMN student_id INTEGER")

    if "submitted_at" not in columns:
        cursor.execute("ALTER TABLE complaints ADD COLUMN submitted_at TEXT")

    if "priority" not in columns:
        cursor.execute("ALTER TABLE complaints ADD COLUMN priority TEXT DEFAULT 'Medium'")

    # Duplicate register numbers are checked during registration.
    # No UNIQUE index is created here so existing database records are preserved.
    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    message = ""

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        register_number = request.form["register_number"].strip()
        department = request.form["department"].strip()
        password = request.form["password"]

        if len(password) < 6:
            message = "Password must contain at least 6 characters."
            return render_template("register.html", message=message)

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM students WHERE register_number = ?",
            (register_number,)
        )
        existing = cursor.fetchone()

        if existing:
            conn.close()
            message = "This register number is already registered."
            return render_template("register.html", message=message)

        hashed_password = generate_password_hash(password)

        cursor.execute("""
            INSERT INTO students
            (name, email, register_number, department, password)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, register_number, department, hashed_password))

        conn.commit()
        conn.close()

        return render_template("register_success.html")

    return render_template("register.html", message=message)


@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        register_number = request.form["register_number"].strip()
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, password FROM students WHERE register_number = ?",
            (register_number,)
        )
        student = cursor.fetchone()
        conn.close()

        if student and check_password_hash(student[1], password):
            session.clear()
            session["student_id"] = student[0]
            session["student_logged_in"] = True
            return redirect("/dashboard")

        message = "Invalid register number or password."

    return render_template("login.html", message=message)


@app.route("/dashboard")
def dashboard():
    if not session.get("student_logged_in"):
        return redirect("/login")

    student_id = session.get("student_id")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()

    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END)
        FROM complaints
        WHERE student_id = ?
    """, (student_id,))
    counts = cursor.fetchone()

    conn.close()

    stats = {
        "total": counts[0] or 0,
        "pending": counts[1] or 0,
        "progress": counts[2] or 0,
        "resolved": counts[3] or 0
    }

    return render_template("dashboard.html", student=student, stats=stats)


@app.route("/complaint", methods=["GET", "POST"])
def complaint():
    if not session.get("student_logged_in"):
        return redirect("/login")

    message = ""

    if request.method == "POST":
        title = request.form["title"].strip()
        category = request.form["category"].strip()
        location = request.form["location"].strip()
        description = request.form["description"].strip()
        priority = request.form.get("priority", "Medium").strip()

        if priority not in ["Low", "Medium", "High"]:
            priority = "Medium"

        student_id = session.get("student_id")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO complaints
            (title, category, location, description, status, student_id, submitted_at, priority)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), ?)
        """, (
            title, category, location, description,
            "Pending", student_id, priority
        ))

        complaint_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return render_template("success.html", complaint_id=complaint_id)

    return render_template("complaint.html", message=message)


@app.route("/my_complaints")
def my_complaints():
    if not session.get("student_logged_in"):
        return redirect("/login")

    student_id = session.get("student_id")
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "All")

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT
            id, title, category, location, description,
            status, submitted_at, priority
        FROM complaints
        WHERE student_id = ?
    """
    params = [student_id]

    if search:
        query += """
            AND (
                title LIKE ?
                OR category LIKE ?
                OR location LIKE ?
                OR description LIKE ?
            )
        """
        term = f"%{search}%"
        params.extend([term, term, term, term])

    if status_filter in ["Pending", "In Progress", "Resolved"]:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    complaints = cursor.fetchall()
    conn.close()

    return render_template(
        "my_complaints.html",
        complaints=complaints,
        search=search,
        status_filter=status_filter
    )


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    message = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM admins WHERE username = ?", (username,))
        admin_user = cursor.fetchone()
        conn.close()

        if admin_user and check_password_hash(admin_user[1], password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect("/admin")

        message = "Invalid admin username or password."

    return render_template("admin_login.html", message=message)


@app.route("/admin_register", methods=["GET", "POST"])
def admin_register():
    message = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if len(username) < 3:
            message = "Username must contain at least 3 characters."
        elif len(password) < 6:
            message = "Password must contain at least 6 characters."
        elif password != confirm_password:
            message = "Passwords do not match."
        else:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM admins WHERE username = ?", (username,))
            exists = cursor.fetchone()
            if exists:
                message = "Admin username already exists."
                conn.close()
            else:
                cursor.execute(
                    "INSERT INTO admins (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )
                conn.commit()
                conn.close()
                return redirect("/admin_login")

    return render_template("admin_register.html", message=message)


@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "All")
    priority_filter = request.args.get("priority", "All")

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT
            complaints.id,
            complaints.title,
            complaints.category,
            complaints.location,
            complaints.description,
            complaints.status,
            complaints.submitted_at,
            complaints.priority,
            students.name,
            students.register_number,
            students.department
        FROM complaints
        LEFT JOIN students
        ON complaints.student_id = students.id
        WHERE 1=1
    """
    params = []

    if search:
        query += """
            AND (
                complaints.title LIKE ?
                OR complaints.category LIKE ?
                OR complaints.location LIKE ?
                OR complaints.description LIKE ?
                OR students.name LIKE ?
                OR students.register_number LIKE ?
                OR students.department LIKE ?
            )
        """
        term = f"%{search}%"
        params.extend([term] * 7)

    if status_filter in ["Pending", "In Progress", "Resolved"]:
        query += " AND complaints.status = ?"
        params.append(status_filter)

    if priority_filter in ["Low", "Medium", "High"]:
        query += " AND complaints.priority = ?"
        params.append(priority_filter)

    query += " ORDER BY complaints.id DESC"

    cursor.execute(query, params)
    complaints = cursor.fetchall()

    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END),
            SUM(CASE WHEN priority = 'High' THEN 1 ELSE 0 END)
        FROM complaints
    """)
    raw = cursor.fetchone()

    conn.close()

    stats = {
        "total": raw[0] or 0,
        "pending": raw[1] or 0,
        "progress": raw[2] or 0,
        "resolved": raw[3] or 0,
        "high": raw[4] or 0
    }

    return render_template(
        "admin.html",
        complaints=complaints,
        stats=stats,
        search=search,
        status_filter=status_filter,
        priority_filter=priority_filter
    )


@app.route("/update_status", methods=["POST"])
def update_status():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    complaint_id = request.form["complaint_id"]
    status = request.form["status"]

    if status not in ["Pending", "In Progress", "Resolved"]:
        return redirect("/admin")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE complaints SET status = ? WHERE id = ?",
        (status, complaint_id)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/update_priority", methods=["POST"])
def update_priority():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    complaint_id = request.form["complaint_id"]
    priority = request.form["priority"]

    if priority not in ["Low", "Medium", "High"]:
        return redirect("/admin")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE complaints SET priority = ? WHERE id = ?",
        (priority, complaint_id)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# Initialize the database for both local Python runs and Gunicorn/Render imports.
create_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
