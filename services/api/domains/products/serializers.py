from rest_framework import serializers

from domains.tenants.models import OrganizationKind

from .models import DeployedVersion, Module, Product


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ("id", "product", "name", "is_active")
        read_only_fields = ("id", "product")


class ProductSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ("id", "name", "is_active", "color", "modules")
        read_only_fields = ("id", "modules")


class ProductWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False)


class ProductColorWriteSerializer(serializers.Serializer):
    color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$")


class ModuleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)


class DeployedVersionSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True, allow_null=True)

    class Meta:
        model = DeployedVersion
        fields = (
            "id",
            "organization",
            "organization_name",
            "product",
            "product_name",
            "module",
            "module_name",
            "version",
            "deployed_at",
        )
        read_only_fields = ("id", "organization_name", "product_name", "module_name")

    def validate(self, attrs):
        product = attrs["product"]
        module = attrs.get("module")
        if module and module.product_id != product.pk:
            raise serializers.ValidationError(
                {"module": "Module must belong to the selected product."}
            )
        if attrs["organization"].kind != OrganizationKind.BANK:
            raise serializers.ValidationError({"organization": "Choose a client organization."})
        return attrs


class ResponseDuePeriodsSerializer(serializers.Serializer):
    periods = serializers.DictField(child=serializers.IntegerField(min_value=0, max_value=3650))

    def validate_periods(self, value):
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if set(value) - allowed:
            raise serializers.ValidationError("Use the configured priority values.")
        return value
