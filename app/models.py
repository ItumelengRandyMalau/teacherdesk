
from werkzeug.security import generate_password_hash, check_password_hash


class User:
    def __init__(self, username, email, password, role="teacher"):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.role = role

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "role": self.role
        }


class Learner:
    def __init__(
        self,
        learner_number,
        first_name,
        last_name,
        grade,
        class_name,
        status="active"
    ):
        # Store the learner's unique identification number.
        self.learner_number = learner_number

        # Store the learner's personal and academic details.
        self.first_name = first_name
        self.last_name = last_name
        self.grade = grade
        self.class_name = class_name

        # New learners are active by default.
        self.status = status

    def to_dict(self):
        # Convert the learner object into a dictionary for MongoDB.
        return {
            "learner_number": self.learner_number,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "grade": self.grade,
            "class_name": self.class_name,
            "status": self.status
        }

