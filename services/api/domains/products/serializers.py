from rest_framework import serializers

from .models import Module, Product


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ("id", "product", "name", "is_active")
        read_only_fields = ("id", "product")


class ProductSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ("id", "name", "is_active", "modules")
        read_only_fields = ("id", "modules")


class ProductWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)


class ModuleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
