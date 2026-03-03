import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# --------------------------------
# APP
# --------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# --------------------------------
# DATABASE CONFIG (FIXED)
# - If DATABASE_URL exists (Render Postgres) -> use it
# - Else use Render-safe SQLite in /tmp
# --------------------------------
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Some platforms provide postgres:// but SQLAlchemy wants postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # ✅ IMPORTANT FIX: Render writable location
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------------------
# LOGIN MANAGER
# --------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# --------------------------------
# MODELS
# --------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(250), nullable=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    course = db.Column(db.String(150), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ✅ Create tables at startup (works on Render + local)
with app.app_context():
    db.create_all()

# --------------------------------
# ROUTES
# --------------------------------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# -------- REGISTER --------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password are required!", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# -------- LOGIN --------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password!", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")

# -------- LOGOUT --------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))

# -------- DASHBOARD --------
@app.route("/dashboard")
@login_required
def dashboard():
    students = Student.query.order_by(Student.id.desc()).all()
    return render_template("dashboard.html", students=students)

# -------- ADD STUDENT --------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()

        if not name or not email or not course:
            flash("All fields are required!", "danger")
            return redirect(url_for("add_student"))

        student = Student(name=name, email=email, course=course)
        db.session.add(student)
        db.session.commit()

        flash("Student added successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_student.html")

# -------- EDIT STUDENT --------
@app.route("/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)

    if request.method == "POST":
        student.name = request.form.get("name", "").strip()
        student.email = request.form.get("email", "").strip()
        student.course = request.form.get("course", "").strip()

        if not student.name or not student.email or not student.course:
            flash("All fields are required!", "danger")
            return redirect(url_for("edit_student", student_id=student_id))

        db.session.commit()
        flash("Student updated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_student.html", student=student)

# -------- DELETE STUDENT --------
@app.route("/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted successfully!", "success")
    return redirect(url_for("dashboard"))

# -------- PDF DOWNLOAD --------
@app.route("/download_pdf")
@login_required
def download_pdf():
    students = Student.query.order_by(Student.id.asc()).all()

    # ✅ Write PDF in /tmp (Render-safe)
    filename = "students_report.pdf"
    file_path = os.path.join("/tmp", filename)

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Student Portal - Students Report", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Generated by: {current_user.username}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    data = [["ID", "Name", "Email", "Course"]]
    for s in students:
        data.append([str(s.id), s.name, s.email, s.course])

    table = Table(data, colWidths=[50, 150, 180, 130])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_file(file_path, as_attachment=True, download_name=filename)

# --------------------------------
# LOCAL RUN
# --------------------------------
if __name__ == "__main__":
    app.run(debug=True)