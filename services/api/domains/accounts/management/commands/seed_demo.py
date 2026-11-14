"""Load SYNTHETIC demo organizations and users for local development. DEBUG only."""

from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from domains.accounts import services
from domains.accounts.roles import Role
from domains.issues.models import Issue, IssueStatus
from domains.issues.services import create_draft, submit
from domains.products.models import Module, Product
from domains.tenants.models import Organization, OrganizationKind

DEMO_PASSWORD = "Demo-Pass-2026!"  # synthetic, local-only; printed for the demo operator
BANKS = [("Northwind Demo Bank", "NWD"), ("Riverstone Demo Bank", "RSD")]
USERS: list[tuple[str, str, str, list[Role]]] = [
    ("ds.admin", "DATASOFT", "Dana Admin", [Role.DATASOFT_ADMIN]),
    ("ds.support", "DATASOFT", "Sami Support", [Role.SUPPORT_AGENT]),
    ("ds.support2", "DATASOFT", "Rafi Support", [Role.SUPPORT_AGENT]),
    ("nwd.officer", "NWD", "Nadia Officer", [Role.ISSUE_OFFICER]),
    ("nwd.verifier", "NWD", "Noor Verifier", [Role.ISSUE_VERIFIER]),
    ("nwd.dual", "NWD", "Nabil Dual-Role", [Role.ISSUE_OFFICER, Role.ISSUE_VERIFIER]),
    ("rsd.officer", "RSD", "Rina Officer", [Role.ISSUE_OFFICER]),
    ("rsd.verifier", "RSD", "Rumi Verifier", [Role.ISSUE_VERIFIER]),
]


class Command(BaseCommand):
    help = "Create synthetic demo banks and users (idempotent, DEBUG only)."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DJANGO_DEBUG=1 (synthetic local data).")
        services.ensure_datasoft_organization()
        for name, code in BANKS:
            Organization.objects.get_or_create(
                code=code, defaults={"name": name, "kind": OrganizationKind.BANK}
            )
        for username, code, full_name, roles in USERS:
            if User.objects.filter(username=username).exists():
                continue
            user = services.create_user_unchecked(
                organization=Organization.objects.get(code=code),
                username=username,
                email=f"{username}@example.test",
                full_name=full_name,
                roles=roles,
            )
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password"])
            user.account.must_change_password = False
            user.account.save(update_fields=["must_change_password"])
        product, _ = Product.objects.get_or_create(name="Synthetic Service Core")
        Module.objects.get_or_create(product=product, name="Test Ledger")
        for code in ("NWD", "RSD"):
            officer = User.objects.get(username=f"{code.lower()}.officer")
            for title, request_type, submitted in (
                (f"{code} synthetic login issue", "BUG", True),
                (f"{code} synthetic support question", "SUPPORT", True),
                (f"{code} synthetic draft change", "CHANGE", False),
            ):
                if Issue.objects.filter(
                    organization=officer.account.organization, title=title
                ).exists():
                    continue
                issue = create_draft(
                    officer,
                    {
                        "title": title,
                        "description": "Synthetic demonstration data only.",
                        "request_type": request_type,
                        "product": product,
                        "priority": "MEDIUM",
                        "environment": (
                            "Synthetic test environment" if request_type == "BUG" else ""
                        ),
                        "steps_to_reproduce": "Open the test page" if request_type == "BUG" else "",
                        "expected_result": "Test page loads" if request_type == "BUG" else "",
                        "actual_result": "Synthetic error appears" if request_type == "BUG" else "",
                    },
                )
                if submitted and issue.status == IssueStatus.DRAFT:
                    submit(officer, issue)
        self.stdout.write(f"Synthetic demo users ready ({len(USERS)}); password: {DEMO_PASSWORD}")
        for username, code, _, roles in USERS:
            self.stdout.write(f"  {username:14} {code:9} {', '.join(roles)}")
