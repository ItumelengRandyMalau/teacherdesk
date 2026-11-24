
from flask import render_template, request
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