from django.db import models


class Role(models.TextChoices):
    ISSUE_OFFICER = "ISSUE_OFFICER", "Client Issue Officer"
    ISSUE_VERIFIER = "ISSUE_VERIFIER", "Client Issue Verifier"
    DATASOFT_ADMIN = "DATASOFT_ADMIN", "DataSoft Administrator"
    SUPPORT_AGENT = "SUPPORT_AGENT", "DataSoft Support Agent"


BANK_ROLES = frozenset({Role.ISSUE_OFFICER, Role.ISSUE_VERIFIER})
DATASOFT_ROLES = frozenset({Role.DATASOFT_ADMIN, Role.SUPPORT_AGENT})
