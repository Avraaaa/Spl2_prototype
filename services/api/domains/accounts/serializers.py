from typing import Any

from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from domains.tenants.models import Organization

from .roles import Role
from .services import is_datasoft_admin, roles_of


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
    can_view_unmasked_original = serializers.SerializerMethodField()

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
            "can_view_unmasked_original",
            "last_login",
            "date_joined",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=Role.choices)))
    def get_roles(self, user: User) -> list[str]:
        return roles_of(user)

    @extend_schema_field(serializers.BooleanField)
    def get_can_view_unmasked_original(self, user: User) -> bool:
        return is_datasoft_admin(user) or user.has_perm("issues.view_unmasked_original")


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


class ProfileUpdateSerializer(serializers.Serializer[Any]):
    full_name = serializers.CharField(max_length=200, required=False)
    email = serializers.EmailField(max_length=254, required=False)


class ChangeUsernameSerializer(serializers.Serializer[Any]):
    username = serializers.RegexField(r"\A[\w.@+-]{3,150}\Z", trim_whitespace=False)
    current_password = serializers.CharField(
        trim_whitespace=False, style={"input_type": "password"}
    )


class ErrorSerializer(serializers.Serializer[Any]):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)
