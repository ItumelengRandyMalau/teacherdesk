from flask import Flask, render_template, session, request, redirect, url_for, abort
from app.decorators import login_required, role_required
from flask_pymongo import PyMongo
from config import Config
from app.models import User, Learner
from app.learner_utils import generate_learner_number
from bson import ObjectId

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

        # Send administrators to their management dashboard.
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        # Send teachers to their personal dashboard.
        if session.get("role") == "teacher":
            return redirect(url_for("teacher_dashboard"))

        # Clerks will use the general homepage until their
        # dedicated workspace is created.
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

    @app.route("/teacher")
    @role_required("teacher")
    def teacher_dashboard():

        # Identify the logged-in teacher.
        teacher_id = ObjectId(session["user_id"])

        # Retrieve only assignments belonging to this teacher.
        assignments = list(
            mongo.db.assignments.find({
                "teacher_id": teacher_id
            }).sort("grade", 1)
        )

        # Retrieve assessments belonging to each assignment.
        for assignment in assignments:
            assignment["assessments"] = list(
                mongo.db.assessments.find({
                    "assignment_id": assignment["_id"],
                    "teacher_id": teacher_id
                }).sort("term", 1)
            )

        return render_template(
            "teacher.html",
            username=session["username"],
            assignments=assignments
        )
    @app.route(
        "/teacher/assignments/<assignment_id>/assessments/add",
        methods=["GET", "POST"]
    )
    @role_required("teacher")
    def add_assessment(assignment_id):

        message = ""

        # Identify the logged-in teacher.
        teacher_id = ObjectId(session["user_id"])

        # Find the requested assignment, but only if it belongs
        # to the logged-in teacher.
        try:
            assignment = mongo.db.assignments.find_one({
                "_id": ObjectId(assignment_id),
                "teacher_id": teacher_id
            })
        except Exception:
            assignment = None

        # Prevent teachers from accessing another teacher's assignment.
        if not assignment:
            abort(404)

        if request.method == "POST":

            title = request.form.get("title", "").strip()
            assessment_type = request.form.get("assessment_type", "").strip()
            term = request.form.get("term", "").strip()
            max_mark = request.form.get("max_mark", "").strip()

            # Check that all fields have been completed.
            if not title or not assessment_type or not term or not max_mark:
                message = "All fields are required."

            else:
                try:
                    max_mark = float(max_mark)

                    if max_mark <= 0:
                        message = "Maximum mark must be greater than zero."

                except ValueError:
                    message = "Please enter a valid maximum mark."

                if not message:
                    assessment = {
                        "assignment_id": assignment["_id"],
                        "teacher_id": teacher_id,
                        "title": title,
                        "assessment_type": assessment_type,
                        "term": term,
                        "max_mark": max_mark
                    }

                    # Save the assessment in MongoDB.
                    mongo.db.assessments.insert_one(assessment)

                    return redirect(url_for("teacher_dashboard"))

        return render_template(
            "add_assessment.html",
            username=session["username"],
            assignment=assignment,
            message=message
        )

    @app.route("/teacher/assessments/<assessment_id>/marks")
    @role_required("teacher")
    def enter_marks(assessment_id):

        # Identify the logged-in teacher.
        teacher_id = ObjectId(session["user_id"])

        # Find the assessment, but only if it belongs to this teacher.
        try:
            assessment = mongo.db.assessments.find_one({
                "_id": ObjectId(assessment_id),
                "teacher_id": teacher_id
            })
        except Exception:
            assessment = None

        # Prevent access to another teacher's assessment.
        if not assessment:
            abort(404)

        # Retrieve the class linked to this assessment.
        assignment = mongo.db.assignments.find_one({
            "_id": assessment["assignment_id"],
            "teacher_id": teacher_id
        })

        if not assignment:
            abort(404)

        # Retrieve only active learners in the assigned class.
        learners = list(
            mongo.db.learners.find({
                "grade": assignment["grade"],
                "class_name": assignment["class_name"],
                "status": "active"
            }).sort("learner_number", 1)
        )

        return render_template(
            "enter_marks.html",
            username=session["username"],
            assessment=assessment,
            assignment=assignment,
            learners=learners
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

    
    @app.route("/admin/learners/add", methods=["GET", "POST"])
    @role_required("admin")
    def add_learner():

        message = ""

        if request.method == "POST":

            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            grade = request.form.get("grade", "").strip()
            class_name = request.form.get("class_name", "").strip()

            # Check that all required learner details have been provided.
            if not first_name or not last_name or not grade or not class_name:
                message = "All fields are required."

            else:
                # Generate a unique learner number using the MongoDB counter.
                learner_number = generate_learner_number(mongo.db)

                # Create a learner object with the submitted information.
                learner = Learner(
                    learner_number,
                    first_name,
                    last_name,
                    grade,
                    class_name
                )

                # Save the learner record in MongoDB.
                mongo.db.learners.insert_one(learner.to_dict())

                return redirect(url_for("learner_directory"))

        return render_template(
            "add_learner.html",
            username=session["username"],
            message=message
        )

    @app.route("/admin/learners")
    @role_required("admin")
    def learner_directory():

        # Retrieve all registered learners from MongoDB.
        learners = list(
            mongo.db.learners.find().sort("learner_number", -1)
        )

        return render_template(
            "learners.html",
            username=session["username"],
            learners=learners
        )


    @app.route("/admin/assignments/add", methods=["GET", "POST"])
    @role_required("admin")
    def add_assignment():

        message = ""

        # Retrieve existing teacher accounts for the dropdown.
        teachers = list(
            mongo.db.users.find(
                {"role": "teacher"},
                {"username": 1, "email": 1}
            )
        )

        if request.method == "POST":

            teacher_id = request.form.get("teacher_id", "")
            grade = request.form.get("grade", "").strip()
            class_name = request.form.get("class_name", "").strip()
            subject = request.form.get("subject", "").strip()

            # Check that all assignment details have been provided.
            if not teacher_id or not grade or not class_name or not subject:
                message = "All fields are required."

            else:
                # Confirm that the selected teacher account exists.
                teacher = mongo.db.users.find_one({
                    "_id": ObjectId(teacher_id),
                    "role": "teacher"
                })

                if not teacher:
                    message = "Please select a valid teacher."

                else:
                    assignment = {
                        "teacher_id": teacher["_id"],
                        "grade": grade,
                        "class_name": class_name,
                        "subject": subject
                    }

                    # Save the assignment in MongoDB.
                    mongo.db.assignments.insert_one(assignment)

                    return redirect(url_for("admin_dashboard"))

        return render_template(
            "add_assignment.html",
            username=session["username"],
            teachers=teachers,
            message=message
        )

    @app.route("/admin/assignments")
    @role_required("admin")
    def assignment_directory():

        # Retrieve all assignments and match each one to its teacher.
        assignments = list(
            mongo.db.assignments.aggregate([
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "teacher_id",
                        "foreignField": "_id",
                        "as": "teacher"
                    }
                },
                {
                    "$unwind": "$teacher"
                },
                {
                    "$sort": {"grade": 1, "class_name": 1}
                }
            ])
        )

        return render_template(
            "assignments.html",
            username=session["username"],
            assignments=assignments
        )
    @app.route("/db-check")
    def db_check():
        mongo.cx.admin.command("ping")
        return {"message": "MongoDB connection successful!"}

    return app
