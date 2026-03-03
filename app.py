import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# --------------------------------
# APP CONFIGURATION
# --------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# Render PostgreSQL support
database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# --------------------------------
# DATABASE MODELS
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

# Create database tables
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

# --------------------------------
# REGISTER
# --------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:

            flash("Username already exists!", "danger")

            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        new_user = User(username=username, password_hash=hashed_password)

        db.session.add(new_user)

        db.session.commit()

        flash("Registration successful! Please login.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")

# --------------------------------
# LOGIN
# --------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):

            login_user(user)

            flash("Login successful!", "success")

            return redirect(url_for("dashboard"))

        else:

            flash("Invalid username or password", "danger")

            return redirect(url_for("login"))

    return render_template("login.html")

# --------------------------------
# LOGOUT
# --------------------------------

@app.route("/logout")
@login_required
def logout():

    logout_user()

    flash("Logged out successfully!", "success")

    return redirect(url_for("login"))

# --------------------------------
# DASHBOARD
# --------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    students = Student.query.all()

    return render_template("dashboard.html", students=students)

# --------------------------------
# ADD STUDENT
# --------------------------------

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_student():

    if request.method == "POST":

        name = request.form["name"]

        email = request.form["email"]

        course = request.form["course"]

        student = Student(name=name, email=email, course=course)

        db.session.add(student)

        db.session.commit()

        flash("Student added successfully!", "success")

        return redirect(url_for("dashboard"))

    return render_template("add_student.html")

# --------------------------------
# EDIT STUDENT
# --------------------------------

@app.route("/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):

    student = Student.query.get_or_404(student_id)

    if request.method == "POST":

        student.name = request.form["name"]

        student.email = request.form["email"]

        student.course = request.form["course"]

        db.session.commit()

        flash("Student updated successfully!", "success")

        return redirect(url_for("dashboard"))

    return render_template("edit_student.html", student=student)

# --------------------------------
# DELETE STUDENT
# --------------------------------

@app.route("/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):

    student = Student.query.get_or_404(student_id)

    db.session.delete(student)

    db.session.commit()

    flash("Student deleted successfully!", "success")

    return redirect(url_for("dashboard"))

# --------------------------------
# DOWNLOAD PDF
# --------------------------------

@app.route("/download_pdf")
@login_required
def download_pdf():

    students = Student.query.all()

    filename = "students_report.pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4)

    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("Student Portal - Student Report", styles["Title"]))

    elements.append(Spacer(1, 20))

    data = [["ID", "Name", "Email", "Course"]]

    for s in students:

        data.append([s.id, s.name, s.email, s.course])

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("GRID", (0,0), (-1,-1), 1, colors.black)
    ]))

    elements.append(table)

    doc.build(elements)

    return send_file(filename, as_attachment=True)

# --------------------------------
# ERROR HANDLING
# --------------------------------

@app.errorhandler(500)
def internal_error(error):

    return "Internal Server Error", 500

# --------------------------------
# RUN LOCAL
# --------------------------------

if __name__ == "__main__":
    app.run(debug=True)