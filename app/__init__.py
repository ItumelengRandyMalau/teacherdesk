
from flask import Flask, render_template, session
from app.decorators import login_required, role_required
from flask_pymongo import PyMongo
from config import Config

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

    @app.route("/db-check")
    def db_check():
        mongo.cx.admin.command("ping")
        return {"message": "MongoDB connection successful!"}

    return app
