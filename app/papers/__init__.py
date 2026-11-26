
from flask import Blueprint

papers = Blueprint("papers", __name__)

from app.papers import routes
