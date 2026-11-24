from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=160, unique=True)
    is_active = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default="#64748B")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Module(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="modules")
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["product", "name"], name="unique_product_module")
        ]

    def __str__(self) -> str:
        return f"{self.product.name} / {self.name}"


class DeployedVersion(models.Model):
    organization = models.ForeignKey(
        "tenants.Organization", on_delete=models.PROTECT, related_name="deployed_versions"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="deployments")
    module = models.ForeignKey(
        Module, on_delete=models.PROTECT, null=True, blank=True, related_name="deployments"
    )
    version = models.CharField(max_length=80)
    deployed_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deployed_at", "-id"]


class ResponseDuePeriod(models.Model):
    priority = models.CharField(max_length=10, unique=True)
    days = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["priority"]
