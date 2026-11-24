
from flask import Flask, render_template, session, redirect, url_for
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
    def home():

        if "user_id" not in session:
            return redirect(url_for("auth.login"))

        return render_template(
            "index.html",
            username=session["username"]
        )

    @app.route("/db-check")
    def db_check():
        mongo.cx.admin.command("ping")
        return {"message": "MongoDB connection successful!"}

    return app
