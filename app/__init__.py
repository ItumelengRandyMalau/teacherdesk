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

        # Send clerks to their dedicated workspace.
        if session.get("role") == "clerk":
            return redirect(url_for("clerk_dashboard"))

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

    
    @app.route("/clerk")
    @role_required("clerk")
    def clerk_dashboard():

        # Retrieve the number of learners registered at the school.
        total_learners = mongo.db.learners.count_documents({})

        # Retrieve the number of assessments created by teachers.
        total_assessments = mongo.db.assessments.count_documents({})

        # Retrieve the number of marks entered across all assessments.
        total_marks = mongo.db.marks.count_documents({})

        return render_template(
            "clerk.html",
            username=session["username"],
            total_learners=total_learners,
            total_assessments=total_assessments,
            total_marks=total_marks
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

    
    @app.route(
        "/teacher/assessments/<assessment_id>/marks",
        methods=["GET", "POST"]
    )
    @role_required("teacher")
    def enter_marks(assessment_id):

        message = ""

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

        if request.method == "POST":

            # Process each learner's submitted mark.
            for learner in learners:

                field_name = f"mark_{learner['_id']}"
                submitted_mark = request.form.get(field_name, "").strip()

                # Skip learners whose mark was left blank.
                if not submitted_mark:
                    continue

                try:
                    mark = float(submitted_mark)

                    if mark < 0 or mark > assessment["max_mark"]:
                        message = (
                            f"Marks must be between 0 and "
                            f"{assessment['max_mark']}."
                        )
                        break

                except ValueError:
                    message = "Please enter valid numeric marks."
                    break

            # Save marks only if all submitted values are valid.
            if not message:

                for learner in learners:

                    field_name = f"mark_{learner['_id']}"
                    submitted_mark = request.form.get(
                        field_name, ""
                    ).strip()

                    if not submitted_mark:
                        continue

                    mark = float(submitted_mark)

                    # Update an existing mark or create a new one.
                    mongo.db.marks.update_one(
                        {
                            "assessment_id": assessment["_id"],
                            "learner_id": learner["_id"]
                        },
                        {
                            "$set": {
                                "assessment_id": assessment["_id"],
                                "assignment_id": assignment["_id"],
                                "teacher_id": teacher_id,
                                "learner_id": learner["_id"],
                                "learner_number": learner["learner_number"],
                                "mark": mark,
                                "max_mark": assessment["max_mark"],
                                "percentage": round(
                                    (mark / assessment["max_mark"]) * 100,
                                    2
                                )
                            }
                        },
                        upsert=True
                    )

                if any(
                    request.form.get(
                        f"mark_{learner['_id']}", ""
                    ).strip()
                    for learner in learners
                ):
                    message = "Marks saved successfully."
                else:
                    message = "Please enter at least one mark."

        # Retrieve marks already saved for this assessment.
        saved_marks = {
            str(record["learner_id"]): record["mark"]
            for record in mongo.db.marks.find({
                "assessment_id": assessment["_id"]
            })
        }
        
        return render_template(
            "enter_marks.html",
            username=session["username"],
            assessment=assessment,
            assignment=assignment,
            learners=learners,
            saved_marks=saved_marks,
            message=message
        )
    
    @app.route("/teacher/assessments/<assessment_id>/results")
    @role_required("teacher")
    def assessment_results(assessment_id):

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

        if not assessment:
            abort(404)

        # Retrieve the class linked to this assessment.
        assignment = mongo.db.assignments.find_one({
            "_id": assessment["assignment_id"],
            "teacher_id": teacher_id
        })

        if not assignment:
            abort(404)

        # Retrieve all active learners in this class.
        learners = list(
            mongo.db.learners.find({
                "grade": assignment["grade"],
                "class_name": assignment["class_name"],
                "status": "active"
            }).sort("learner_number", 1)
        )

        # Retrieve marks saved for this assessment.
        saved_marks = mongo.db.marks.find({
            "assessment_id": assessment["_id"],
            "teacher_id": teacher_id
        })

        # Organise marks by learner ID for easy lookup.
        marks_by_learner = {
            str(record["learner_id"]): record
            for record in saved_marks
        }

        results = []
        percentages = []

        # Include every active learner, even if not yet marked.
        for learner in learners:

            mark_record = marks_by_learner.get(
                str(learner["_id"])
            )

            percentage = (
                mark_record.get("percentage")
                if mark_record else None
            )

            if percentage is not None:
                percentages.append(float(percentage))

            results.append({
                "learner": learner,
                "mark": mark_record,
                "percentage": percentage
            })

        # Calculate the average percentage of marked learners.
        average_percentage = (
            round(sum(percentages) / len(percentages), 2)
            if percentages else None
        )

        # Count learners in each performance range.
        performance_distribution = {
            "Below 40%": 0,
            "40–49%": 0,
            "50–59%": 0,
            "60–69%": 0,
            "70–79%": 0,
            "80–100%": 0
        }

        for percentage in percentages:

            if percentage < 40:
                performance_distribution["Below 40%"] += 1
            elif percentage < 50:
                performance_distribution["40–49%"] += 1
            elif percentage < 60:
                performance_distribution["50–59%"] += 1
            elif percentage < 70:
                performance_distribution["60–69%"] += 1
            elif percentage < 80:
                performance_distribution["70–79%"] += 1
            else:
                performance_distribution["80–100%"] += 1

        return render_template(
            "assessment_results.html",
            username=session["username"],
            assessment=assessment,
            assignment=assignment,
            results=results,
            average_percentage=average_percentage,
            marked_count=len(percentages),
            unmarked_count=len(learners) - len(percentages),
            performance_distribution=performance_distribution
        )

    @app.route("/clerk/assessments")
    @role_required("clerk")
    def clerk_assessments():

        # Retrieve all assessments created by teachers.
        assessments = list(
            mongo.db.assessments.find({})
        )

        # Attach class and teacher information to each assessment.
        for assessment in assessments:

            assignment = mongo.db.assignments.find_one({
                "_id": assessment["assignment_id"]
            })

            assessment["assignment"] = assignment

            # Find the teacher responsible for the assignment.
            if assignment:
                teacher = mongo.db.users.find_one({
                    "_id": assignment["teacher_id"]
                })
            else:
                teacher = None

            assessment["teacher_name"] = (
                teacher["username"] if teacher else "Unknown"
            )

        return render_template(
            "clerk_assessments.html",
            username=session["username"],
            assessments=assessments
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
