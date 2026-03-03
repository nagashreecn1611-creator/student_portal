from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import Table
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ------------------ DATABASE MODEL ------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ ROUTES ------------------

@app.route('/')
def home():
    return redirect(url_for("login"))

# ---------- REGISTER ----------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# ---------- LOGIN ----------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            login_user(user)
            return redirect(url_for("dashboard"))

    return render_template("login.html")

# ---------- DASHBOARD ----------

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    prediction = None

    if request.method == "POST":
        studytime = int(request.form.get("studytime"))
        absences = int(request.form.get("absences"))
        g1 = int(request.form.get("g1"))
        g2 = int(request.form.get("g2"))

        # Simple prediction logic
        prediction = int((g1 + g2) / 2)

    return render_template("dashboard.html", prediction=prediction)

# ---------- PDF DOWNLOAD ----------

@app.route("/download_pdf", methods=["POST"])
@login_required
def download_pdf():

    studytime = request.form.get("studytime")
    absences = request.form.get("absences")
    g1 = request.form.get("g1")
    g2 = request.form.get("g2")

    prediction = int((int(g1) + int(g2)) / 2)

    file_path = "report.pdf"
    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Student Performance Report", styles['Title']))
    elements.append(Spacer(1, 20))

    data = [
        ["Study Time", studytime],
        ["Absences", absences],
        ["G1", g1],
        ["G2", g2],
        ["Predicted Final Score", prediction]
    ]

    table = Table(data)
    elements.append(table)

    doc.build(elements)

    return send_file(file_path, as_attachment=True)

# ---------- LOGOUT ----------

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------- RUN ----------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)