from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=160, unique=True)
    is_active = models.BooleanField(default=True)

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
