"""Every finding one pull request review run recorded, in one value."""

from __future__ import annotations

from dataclasses import dataclass

from ._generated.models.customer_code_assessment import CustomerCodeAssessment
from ._generated.models.customer_finding import CustomerFinding
from ._generated.models.customer_review_detail import CustomerReviewDetail


@dataclass(frozen=True)
class PullRequestFindings:
    """One pull request review run and every finding it recorded so far.

    ``findings`` holds the code assessment's findings first, then each
    environment assessment's findings in recorded order. Nothing is filtered:
    findings of a withheld review, resolved findings and repeated findings are
    all kept. ``status`` is the review's own lifecycle status; a ``PENDING`` or
    ``RUNNING`` review may record more findings later.
    """

    review: CustomerReviewDetail
    run_number: int
    status: str
    findings: tuple[CustomerFinding, ...]


def pull_request_findings(review: CustomerReviewDetail, run_number: int) -> PullRequestFindings:
    findings: list[CustomerFinding] = []
    if isinstance(review.code_assessment, CustomerCodeAssessment):
        findings.extend(review.code_assessment.findings)
    for assessment in review.assessments:
        findings.extend(assessment.findings)
    return PullRequestFindings(review, run_number, review.status, tuple(findings))
