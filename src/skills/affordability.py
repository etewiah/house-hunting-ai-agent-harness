from __future__ import annotations

from src.models.schemas import AffordabilityEstimate, Listing


def estimate_monthly_payment(
    listing: Listing,
    deposit_percent: float = 0.15,
    annual_rate: float = 0.0525,
    term_years: int = 25,
) -> AffordabilityEstimate:
    deposit = round(listing.price * deposit_percent)
    loan = listing.price - deposit
    monthly_rate = annual_rate / 12
    months = term_years * 12
    payment = loan * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)

    return AffordabilityEstimate(
        listing_id=listing.id,
        deposit=deposit,
        loan_amount=loan,
        monthly_payment=round(payment),
        assumptions=[
            f"{deposit_percent:.0%} deposit",
            f"{annual_rate:.2%} annual interest",
            f"{term_years}-year term",
            "estimated mortgage payment only; excludes fees, taxes, insurance, utilities, and maintenance",
        ],
    )
