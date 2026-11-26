
from datetime import datetime, timezone
from io import BytesIO

from bson import ObjectId
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
    send_file
)
from gridfs import GridFS
from gridfs.errors import NoFile
from werkzeug.utils import secure_filename

from app import mongo
from app.decorators import login_required, role_required
from app.papers import papers


# Only PDF documents are accepted by the Question Paper Bank.
ALLOWED_EXTENSION = ".pdf"


@papers.route("/")
@login_required
def paper_bank():

    # Retrieve the uploaded papers, newest first.
    question_papers = list(
        GridFS(mongo.db).find().sort("uploadDate", -1)
    )

    return render_template(
        "paper_bank.html",
        username=session["username"],
        question_papers=question_papers
    )


@papers.route("/upload", methods=["GET", "POST"])
@role_required("admin", "teacher")
def upload_paper():

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        grade = request.form.get("grade", "").strip()
        subject = request.form.get("subject", "").strip()
        term = request.form.get("term", "").strip()
        year = request.form.get("year", "").strip()

        uploaded_file = request.files.get("paper")

        if not all([title, grade, subject, term, year, uploaded_file]):
            flash("Please complete all fields and select a PDF file.")
            return redirect(url_for("papers.upload_paper"))

        if not year.isdigit() or len(year) != 4:
            flash("Please enter a valid four-digit year.")
            return redirect(url_for("papers.upload_paper"))

        filename = secure_filename(uploaded_file.filename or "")

        if not filename.lower().endswith(ALLOWED_EXTENSION):
            flash("Only PDF files are allowed.")
            return redirect(url_for("papers.upload_paper"))

        # Check the actual file signature rather than trusting its extension.
        file_signature = uploaded_file.stream.read(5)
        uploaded_file.stream.seek(0)

        if file_signature != b"%PDF-":
            flash("The selected file is not a valid PDF document.")
            return redirect(url_for("papers.upload_paper"))

        metadata = {
            "title": title,
            "grade": grade,
            "subject": subject,
            "term": term,
            "year": int(year),
            "uploaded_by": session["user_id"],
            "uploader_name": session["username"],
            "uploaded_at": datetime.now(timezone.utc)
        }

        # GridFS stores the PDF in MongoDB, not on Render's local disk.
        GridFS(mongo.db).put(
            uploaded_file.stream,
            filename=filename,
            content_type="application/pdf",
            metadata=metadata
        )

        flash("Question paper uploaded successfully.")
        return redirect(url_for("papers.paper_bank"))

    return render_template(
        "upload_paper.html",
        username=session["username"]
    )


@papers.route("/<paper_id>/download")
@login_required
def download_paper(paper_id):

    if not ObjectId.is_valid(paper_id):
        abort(404)

    try:
        paper = GridFS(mongo.db).get(ObjectId(paper_id))
    except NoFile:
        abort(404)

    return send_file(
        BytesIO(paper.read()),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=paper.filename
    )


@papers.route("/<paper_id>/delete", methods=["POST"])
@role_required("admin")
def delete_paper(paper_id):

    if not ObjectId.is_valid(paper_id):
        abort(404)

    try:
        GridFS(mongo.db).delete(ObjectId(paper_id))
    except NoFile:
        abort(404)

    flash("Question paper deleted successfully.")
    return redirect(url_for("papers.paper_bank"))
