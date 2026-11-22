import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AccountsConfig(AppConfig):
    name = "domains.accounts"

    def ready(self) -> None:
        from django.conf import settings

        if not settings.EMAIL_DELIVERY_CONFIGURED:
            logger.warning("Account email delivery is using the console backend.")

    label = "accounts"
    default_auto_field = "django.db.models.BigAutoField"
