import pytest

from domains.issues.models import Issue, IssueStatus
from domains.products.models import Product
from domains.search.services import candidate_suggestions

pytestmark = pytest.mark.django_db


def test_duplicate_candidates_narrow_by_product_and_recent_window(officer_a):
    matching_product = Product.objects.create(name="Synthetic Payments")
    other_product = Product.objects.create(name="Synthetic Reports")
    matching = Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        product=matching_product,
        title="Transfer timeout",
        description="Payment transfer timeout",
    )
    Issue.objects.create(
        organization=officer_a.account.organization,
        created_by=officer_a,
        submitted_by=officer_a,
        status=IssueStatus.SUBMITTED,
        product=other_product,
        title="Transfer timeout",
        description="Payment transfer timeout",
    )

    rows = Issue.objects.filter(organization=officer_a.account.organization)
    suggestions = candidate_suggestions(
        rows,
        title="Transfer timeout",
        description="Payment transfer timeout",
        product=matching_product.pk,
    )

    assert [row["id"] for row in suggestions] == [matching.pk]
