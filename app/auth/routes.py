
from flask import render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash
from app import mongo
from app.models import User
from app.auth import auth


@auth.route("/register", methods=["GET", "POST"])
def register():

    message = ""

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            message = "All fields are required."

        elif len(password) < 8:
            message = "Password must contain at least 8 characters."

        elif mongo.db.users.find_one({
            "$or": [
                {"username": username},
                {"email": email}
            ]
        }):
            message = "Username or email already exists."

        else:
            user = User(username, email, password)

            mongo.db.users.insert_one(user.to_dict())

            message = "Registration successful!"

    return render_template("register.html", message=message)

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

            return redirect(url_for("home"))

        else:
            message = "Invalid email address or password."

    return render_template("login.html", message=message)

@auth.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("auth.login"))