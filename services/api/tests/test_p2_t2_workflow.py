"""P2-T2: versioned, tenant-scoped workflow decisions and immutable history."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from domains.accounts.roles import Role
from domains.issues.models import Issue, IssueEvent, IssueStatus, WorkflowSettings
from domains.products.models import Product

from .conftest import client_for
from .test_n_06 import payload

pytestmark = pytest.mark.django_db


@pytest.fixture
def context(bank_a, bank_b, datasoft, officer_a, officer_b, support, admin, make_user):
    product = Product.objects.create(name="Synthetic Workflow")
    draft = client_for(officer_a).post("/api/issues/", payload(product.pk), format="json").json()
    issue = Issue.objects.get(pk=draft["id"])
    client_for(officer_a).post(f"/api/issues/{issue.pk}/submit/")
    issue.refresh_from_db()
    unroled = make_user("workflow_unroled", bank_a, Role.ISSUE_OFFICER)
    unroled.memberships.all().delete()
    return {
        "issue": issue,
        "officer": officer_a,
        "other_officer": officer_b,
        "verifier": make_user("workflow_verifier_a", bank_a, Role.ISSUE_VERIFIER),
        "other_verifier": make_user("workflow_verifier_b", bank_b, Role.ISSUE_VERIFIER),
        "support": support,
        "admin": admin,
        "unroled": unroled,
    }


def act(context, actor, action, **fields):
    issue = context["issue"]
    issue.refresh_from_db()
    return client_for(actor).post(
        f"/api/issues/{issue.pk}/{action}/",
        {"version": issue.version, **fields},
        format="json",
    )


def advance(context, through):
    if through == "SUBMITTED":
        return
    assert (
        act(context, context["support"], "accept", tentative_delivery_later=True).status_code == 200
    )
    if through == "ACCEPTED":
        return
    assert (
        act(context, context["support"], "assign", assignee=context["support"].pk).status_code
        == 200
    )
    if through == "PENDING":
        return
    assert act(context, context["support"], "start").status_code == 200
    if through == "IN_PROGRESS":
        return
    assert (
        act(
            context,
            context["support"],
            "deliver",
            delivery_note="Fixed synthetic defect",
            deployment_details="v1",
        ).status_code
        == 200
    )
    if through == "AWAITING_VERIFICATION":
        return
    assert act(context, context["verifier"], "verify").status_code == 200
    if through == "VERIFIED":
        return
    assert act(context, context["support"], "close").status_code == 200


@pytest.mark.parametrize(
    ("state", "action", "role", "fields"),
    [
        ("SUBMITTED", "accept", "support", {"tentative_delivery_later": True}),
        ("SUBMITTED", "accept", "admin", {"tentative_delivery_later": True}),
        ("SUBMITTED", "reject", "support", {"reason": "Cannot reproduce"}),
        ("SUBMITTED", "reject", "admin", {"reason": "Cannot reproduce"}),
        ("ACCEPTED", "assign", "support", {"assignee": "support"}),
        ("ACCEPTED", "assign", "admin", {"assignee": "support"}),
        ("PENDING", "start", "support", {}),
        ("PENDING", "start", "admin", {}),
        (
            "IN_PROGRESS",
            "deliver",
            "support",
            {"delivery_note": "Fixed", "deployment_details": "v1"},
        ),
        ("IN_PROGRESS", "deliver", "admin", {"delivery_note": "Fixed", "deployment_details": "v1"}),
        ("AWAITING_VERIFICATION", "verify", "verifier", {}),
        ("AWAITING_VERIFICATION", "fail-verification", "verifier", {"reason": "Still broken"}),
        ("VERIFIED", "close", "support", {}),
        ("VERIFIED", "close", "admin", {}),
        ("CLOSED", "reopen", "officer", {"reason": "Returned"}),
        ("CLOSED", "reopen", "verifier", {"reason": "Returned"}),
        ("CLOSED", "reopen", "support", {"reason": "Returned"}),
    ],
)
def test_allowed_transition_role_and_state(context, state, action, role, fields):
    advance(context, state)
    fields = {
        key: context[value].pk if key == "assignee" else value for key, value in fields.items()
    }
    before = context["issue"].events.count()
    response = act(context, context[role], action, **fields)
    assert response.status_code == 200, response.content
    assert response.json()["version"] == context["issue"].version + 1
    assert response.json()["last_status_at"]
    assert context["issue"].events.count() == before + 1


@pytest.mark.parametrize(
    "role", ["officer", "verifier", "other_officer", "other_verifier", "unroled"]
)
def test_bank_roles_cannot_perform_staff_transition(context, role):
    response = act(context, context[role], "accept", tentative_delivery_later=True)
    assert response.status_code == (404 if role.startswith("other_") else 403)


@pytest.mark.parametrize(
    "action,fields",
    [
        ("assign", {"assignee": 1}),
        ("start", {}),
        ("deliver", {"delivery_note": "Fixed"}),
        ("verify", {}),
        ("fail-verification", {"reason": "No"}),
        ("close", {}),
        ("reopen", {"reason": "No"}),
    ],
)
def test_wrong_state_is_rejected(context, action, fields):
    actor = context["verifier"] if action in ("verify", "fail-verification") else context["support"]
    response = act(context, actor, action, **fields)
    assert response.status_code == 400


@pytest.mark.parametrize(
    "action,fields",
    [
        ("accept", {"tentative_delivery_later": True}),
        ("reject", {"reason": "No"}),
        ("assign", {"assignee": 1}),
        ("start", {}),
        ("deliver", {"delivery_note": "Fixed"}),
        ("verify", {}),
        ("fail-verification", {"reason": "No"}),
        ("close", {}),
        ("reopen", {"reason": "No"}),
        ("revise-date", {"tentative_delivery_later": True}),
    ],
)
def test_other_bank_is_404_on_every_endpoint(context, action, fields):
    for actor in (context["other_officer"], context["other_verifier"]):
        assert act(context, actor, action, **fields).status_code == 404


def test_stale_version_has_no_side_effect(context):
    issue = context["issue"]
    version = issue.version
    assert (
        act(context, context["support"], "accept", tentative_delivery_later=True).status_code == 200
    )
    count = issue.events.count()
    response = client_for(context["admin"]).post(
        f"/api/issues/{issue.pk}/reject/", {"version": version, "reason": "Too late"}, format="json"
    )
    assert response.status_code == 409
    assert issue.events.count() == count


@pytest.mark.django_db(transaction=True)
def test_two_postgres_sessions_racing_accept_get_one_conflict(context):
    issue = context["issue"]
    body = {"version": issue.version, "tentative_delivery_later": True}
    path = f"/api/issues/{issue.pk}/accept/"

    def send(actor):
        return client_for(actor).post(path, body, format="json").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, (context["support"], context["admin"])))
    assert sorted(results) == [200, 409]
    issue.refresh_from_db()
    assert issue.status == IssueStatus.ACCEPTED
    assert issue.events.filter(kind="ACCEPTED").count() == 1


def test_required_decision_fields_and_no_auto_closure(context):
    issue = context["issue"]
    assert act(context, context["support"], "accept").status_code == 400
    assert act(context, context["support"], "reject", reason=" ").status_code == 400
    assert issue.events.count() == 1
    advance(context, "AWAITING_VERIFICATION")
    issue.refresh_from_db()
    assert issue.status == IssueStatus.AWAITING_VERIFICATION
    assert act(context, context["support"], "close").status_code == 400
    assert act(context, context["officer"], "verify").status_code == 403
    assert act(context, context["verifier"], "verify").status_code == 200
    issue.refresh_from_db()
    assert issue.status == IssueStatus.VERIFIED
    assert act(context, context["officer"], "close").status_code == 403
    assert issue.events.filter(kind="CLOSED").count() == 0


def test_assignment_rejects_bank_user_and_records_reassignment(context):
    advance(context, "ACCEPTED")
    assert (
        act(context, context["support"], "assign", assignee=context["officer"].pk).status_code
        == 400
    )
    assert (
        act(context, context["support"], "assign", assignee=context["support"].pk).status_code
        == 200
    )
    assert act(context, context["admin"], "assign", assignee=context["admin"].pk).status_code == 200
    context["issue"].refresh_from_db()
    assert context["issue"].assignee_id == context["admin"].pk
    assert context["issue"].events.filter(kind="REASSIGNED").exists()


def test_dates_delivery_and_failed_verification(context):
    today = timezone.localdate()
    assert (
        act(context, context["support"], "accept", tentative_delivery_date=str(today)).status_code
        == 200
    )
    assert (
        act(context, context["admin"], "revise-date", tentative_delivery_later=True).status_code
        == 200
    )
    assert (
        act(context, context["support"], "assign", assignee=context["support"].pk).status_code
        == 200
    )
    assert act(context, context["support"], "start").status_code == 200
    context["issue"].refresh_from_db()
    assert context["issue"].actual_delivery_at is None
    assert (
        act(
            context,
            context["support"],
            "deliver",
            delivery_note="Fixed",
            deployment_details="v2",
        ).status_code
        == 200
    )
    context["issue"].refresh_from_db()
    assert context["issue"].actual_delivery_at is not None
    assert act(context, context["verifier"], "fail-verification").status_code == 400
    assert (
        act(context, context["verifier"], "fail-verification", reason="Still broken").status_code
        == 200
    )
    context["issue"].refresh_from_db()
    assert context["issue"].status == IssueStatus.IN_PROGRESS
    assert context["issue"].actual_delivery_at is None
    assert context["issue"].events.filter(kind="TENTATIVE_DATE_REVISED").exists()
    assert (
        context["issue"].events.filter(kind="VERIFICATION_FAILED", reason="Still broken").exists()
    )


@pytest.mark.parametrize("days,expected", [(29, 200), (30, 200), (31, 400)])
def test_reopen_boundary(context, days, expected):
    advance(context, "CLOSED")
    context["issue"].refresh_from_db()
    closed_at = context["issue"].closed_at
    with patch(
        "domains.issues.workflow.timezone.now", return_value=closed_at + timedelta(days=days)
    ):
        response = act(context, context["officer"], "reopen", reason="Returned")
    assert response.status_code == expected
    if expected == 400:
        assert "Recurring" in str(response.json())


def test_configurable_window_admin_only(context):
    path = "/api/issues/workflow-settings/"
    assert (
        client_for(context["officer"]).patch(path, {"reopen_days": 45}, format="json").status_code
        == 403
    )
    response = client_for(context["admin"]).patch(path, {"reopen_days": 45}, format="json")
    assert response.status_code == 200
    assert WorkflowSettings.objects.get().reopen_days == 45


def test_events_are_read_only_and_append_only(context):
    event = IssueEvent.objects.get(issue=context["issue"])
    path = f"/api/issues/{context['issue'].pk}/events/{event.pk}/"
    assert (
        client_for(context["support"]).patch(path, {"reason": "changed"}, format="json").status_code
        == 405
    )
    assert client_for(context["support"]).delete(path).status_code == 405
    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()
