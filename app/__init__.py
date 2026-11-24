from flask import Flask, render_template, session, request, redirect, url_for
from app.decorators import login_required, role_required
from flask_pymongo import PyMongo
from config import Config
from app.models import User

mongo = PyMongo()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from app.auth import auth

    if not app.config["MONGO_URI"]:
        raise RuntimeError("MONGO_URI is not configured.")

    mongo.init_app(app)
    app.register_blueprint(auth, url_prefix="/auth")

    @app.route("/")
    @login_required
    def home():

        return render_template(
            "index.html",
            username=session["username"]
        )

    @app.route("/admin")
    @role_required("admin")
    def admin_dashboard():

        total_users = mongo.db.users.count_documents({})

        total_teachers = mongo.db.users.count_documents({
            "role": "teacher"
        })

        return render_template(
            "admin.html",
            username=session["username"],
            total_users=total_users,
            total_teachers=total_teachers
        )

    @app.route("/admin/staff")
    @role_required("admin")
    def staff_directory():

        staff_members = list(
            mongo.db.users.find(
                {},
                {
                    "username": 1,
                    "email": 1,
                    "role": 1
                }
            )
        )

        return render_template(
            "staff.html",
            username=session["username"],
            staff_members=staff_members
        )

    @app.route("/admin/staff/add", methods=["GET", "POST"])
    @role_required("admin")
    def add_staff():

        message = ""

        if request.method == "POST":

            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "")

            if not username or not email or not password or not role:
                message = "All fields are required."

            elif len(password) < 8:
                message = "Password must contain at least 8 characters."

            elif role not in ["teacher", "clerk"]:
                message = "Invalid staff role."

            elif mongo.db.users.find_one({
                "$or": [
                    {"username": username},
                    {"email": email}
                ]
            }):
                message = "Username or email already exists."

            else:
                user = User(username, email, password, role)

                mongo.db.users.insert_one(user.to_dict())

                return redirect(url_for("staff_directory"))

        return render_template(
            "add_staff.html",
            username=session["username"],
            message=message
        )

    @app.route("/db-check")
    def db_check():
        mongo.cx.admin.command("ping")
        return {"message": "MongoDB connection successful!"}

    return app
