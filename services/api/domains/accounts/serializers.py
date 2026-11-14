from typing import Any

from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from domains.tenants.models import Organization

from .roles import Role
from .services import roles_of


class OrganizationSummarySerializer(serializers.ModelSerializer[Organization]):
    class Meta:
        model = Organization
        fields = ["id", "name", "code", "kind"]


class OrganizationSerializer(serializers.ModelSerializer[Organization]):
    class Meta:
        model = Organization
        fields = ["id", "name", "code", "kind", "is_active", "created_at"]
        read_only_fields = ["id", "kind", "is_active", "created_at"]


class PortalUserSerializer(serializers.ModelSerializer[User]):
    full_name = serializers.CharField(source="account.full_name")
    organization = OrganizationSummarySerializer(source="account.organization")
    roles = serializers.SerializerMethodField()
    must_change_password = serializers.BooleanField(source="account.must_change_password")

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "organization",
            "roles",
            "is_active",
            "must_change_password",
            "last_login",
            "date_joined",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=Role.choices)))
    def get_roles(self, user: User) -> list[str]:
        return roles_of(user)


class UserCreateSerializer(serializers.Serializer[Any]):
    username = serializers.RegexField(r"^[\w.@+-]{3,150}$")
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200)
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True)
    )
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=Role.choices), allow_empty=False
    )


class RolesSerializer(serializers.Serializer[Any]):
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=Role.choices), allow_empty=False
    )


class TemporaryCredentialSerializer(serializers.Serializer[Any]):
    user = PortalUserSerializer()
    temporary_password = serializers.CharField(
        help_text="Shown once. Never logged or stored in plaintext."
    )


class LoginSerializer(serializers.Serializer[Any]):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})


class ChangePasswordSerializer(serializers.Serializer[Any]):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)


class ErrorSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)
