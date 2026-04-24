from __future__ import annotations

from src.models.schemas import Listing
from src.skills.verification import generate_verification_items


def generate_tour_questions(listing: Listing) -> list[str]:
    questions = [
        "What is included in the sale and what is excluded?",
        "Have there been any recent repairs, disputes, or insurance claims?",
        "What are the typical utility costs?",
        "Are there any known parking, noise, damp, or maintenance issues?",
    ]
    if "garden" in listing.features:
        questions.append("What is the garden orientation and drainage like after heavy rain?")
    if listing.commute_minutes is None:
        questions.append("What is the realistic door-to-door commute at peak time?")
    for item in generate_verification_items(listing)[:5]:
        if item.question not in questions:
            questions.append(item.question)
    return questions
