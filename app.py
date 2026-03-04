import os
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from flask import Flask, render_template, redirect, url_for, request, flash, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# -------------------- APP SETUP --------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# -------------------- DATABASE SETUP --------------------
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Some platforms provide postgres:// but SQLAlchemy needs postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Render-safe SQLite path (writable)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------- LOGIN MANAGER --------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# -------------------- MODELS --------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(250), nullable=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    course = db.Column(db.String(150), nullable=False)

    study_time = db.Column(db.Float, nullable=False, default=0.0)
    absences = db.Column(db.Integer, nullable=False, default=0)
    g1 = db.Column(db.Float, nullable=False, default=0.0)
    g2 = db.Column(db.Float, nullable=False, default=0.0)

    predicted_score = db.Column(db.Float, nullable=False, default=0.0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()

# -------------------- PREDICTION LOGIC --------------------
def predict_score(study_time: float, absences: int, g1: float, g2: float) -> float:
    """
    Simple baseline prediction (0..100):
    - Uses avg of g1/g2 (0..20) scaled to 0..100
    - Adds benefit for study time
    - Deducts for absences
    """
    base = (g1 + g2) / 2.0
    score = base * 5  # 0..20 -> 0..100
    score += study_time * 3
    score -= absences * 1.5
    score = max(0, min(100, score))
    return round(score, 2)

# -------------------- ROUTES --------------------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password required!", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------- LOGIN ----------
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

# ---------- LOGOUT ----------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out!", "success")
    return redirect(url_for("login"))

# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    students = Student.query.order_by(Student.id.desc()).all()
    return render_template("dashboard.html", students=students)

# ---------- PREDICTION PAGE (GRAPH PAGE) ----------
@app.route("/prediction")
@login_required
def prediction_page():
    students = Student.query.order_by(Student.id.asc()).all()
    return render_template("prediction.html", students=students)

# ---------- ADD STUDENT ----------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()

        study_time = float(request.form.get("study_time", 0))
        absences = int(request.form.get("absences", 0))
        g1 = float(request.form.get("g1", 0))
        g2 = float(request.form.get("g2", 0))

        if not name or not email or not course:
            flash("Name, Email, Course are required!", "danger")
            return redirect(url_for("add_student"))

        pred = predict_score(study_time, absences, g1, g2)

        student = Student(
            name=name,
            email=email,
            course=course,
            study_time=study_time,
            absences=absences,
            g1=g1,
            g2=g2,
            predicted_score=pred
        )

        db.session.add(student)
        db.session.commit()

        flash("Student added successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_student.html")

# ---------- EDIT STUDENT ----------
@app.route("/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)

    if request.method == "POST":
        student.name = request.form.get("name", "").strip()
        student.email = request.form.get("email", "").strip()
        student.course = request.form.get("course", "").strip()

        student.study_time = float(request.form.get("study_time", 0))
        student.absences = int(request.form.get("absences", 0))
        student.g1 = float(request.form.get("g1", 0))
        student.g2 = float(request.form.get("g2", 0))

        if not student.name or not student.email or not student.course:
            flash("Name, Email, Course are required!", "danger")
            return redirect(url_for("edit_student", student_id=student_id))

        student.predicted_score = predict_score(
            student.study_time, student.absences, student.g1, student.g2
        )

        db.session.commit()
        flash("Student updated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_student.html", student=student)

# ---------- DELETE STUDENT ----------
@app.route("/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted successfully!", "success")
    return redirect(url_for("dashboard"))

# ---------- GRAPH IMAGE ----------
@app.route("/graph.png")
@login_required
def graph_png():
    students = Student.query.order_by(Student.id.asc()).all()
    names = [s.name for s in students]
    scores = [s.predicted_score for s in students]

    fig = plt.figure(figsize=(8, 4))
    plt.bar(names, scores)
    plt.xticks(rotation=30, ha="right")
    plt.title("Predicted Score by Student")
    plt.ylabel("Predicted Score (0-100)")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return Response(buf.getvalue(), mimetype="image/png")

# ---------- PDF DOWNLOAD ----------
@app.route("/download_pdf")
@login_required
def download_pdf():
    students = Student.query.order_by(Student.id.asc()).all()

    filename = "students_report.pdf"
    file_path = os.path.join("/tmp", filename)

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Student Performance Report", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Generated by: {current_user.username}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    data = [["ID", "Name", "Course", "StudyTime", "Abs", "G1", "G2", "Pred(0-100)"]]
    for s in students:
        data.append([s.id, s.name, s.course, s.study_time, s.absences, s.g1, s.g2, s.predicted_score])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_file(file_path, as_attachment=True, download_name=filename)

# -------------------- LOCAL RUN --------------------
if __name__ == "__main__":
    app.run(debug=True)