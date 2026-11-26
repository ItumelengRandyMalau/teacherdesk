
from datetime import datetime
from pymongo import ReturnDocument


def generate_learner_number(db):
    # Use the current year to separate learner-number sequences by year.
    year = datetime.now().year

    # Atomically increase the counter so simultaneous registrations
    # cannot receive the same sequence number.
    counter = db.counters.find_one_and_update(
        {"_id": f"learner_number_{year}"},
        {"$inc": {"sequence": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    # Format the number as TD + year + four-digit sequence.
    return f"TD{year}{counter['sequence']:04d}"
