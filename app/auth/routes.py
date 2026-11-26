
from flask import render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from bson import ObjectId

from app import mongo
from app.models import User
from app.auth import auth
from app.decorators import login_required


@auth.route("/register", methods=["GET", "POST"])
def register():

    return redirect(url_for("auth.login"))


@auth.route("/login", methods=["GET", "POST"])
def login():

    message = ""

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = mongo.db.users.find_one({"email": email})

        if user and check_password_hash(user["password_hash"], password):

            session.clear()

            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            session["role"] = user["role"]

            # Flag accounts that must replace a temporary password.
            session["must_change_password"] = user.get(
                "must_change_password", False
            )

            if session["must_change_password"]:
                return redirect(url_for("auth.change_password"))

            return redirect(url_for("home"))

        else:
            message = "Invalid email address or password."

    return render_template("login.html", message=message)


@auth.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():

    message = ""

    if request.method == "POST":

        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 8:
            message = "Password must contain at least 8 characters."

        elif new_password != confirm_password:
            message = "The passwords do not match."

        else:
            mongo.db.users.update_one(
                {"_id": ObjectId(session["user_id"])},
                {
                    "$set": {
                        "password_hash": generate_password_hash(new_password),
                        "must_change_password": False
                    }
                }
            )

            session["must_change_password"] = False

            return redirect(url_for("home"))

    return render_template("change_password.html", message=message)


@auth.route("/logout", methods=["POST"])
def logout():

    # Clear the user's session when they explicitly log out.
    session.clear()

    return redirect(url_for("auth.login"))
