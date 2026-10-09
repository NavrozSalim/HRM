from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.capabilities import capabilities_for
from apps.accounts.models import User
from apps.organization.models import OfficeSettings


class UserSerializer(serializers.ModelSerializer):
    employee_id = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()
    self_checkin_enabled = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone",
            "is_active",
            "employee_id",
            "capabilities",
            "self_checkin_enabled",
            "password",
        ]
        read_only_fields = ["id"]

    def get_employee_id(self, obj):
        profile = getattr(obj, "employee_profile", None)
        return profile.id if profile else None

    def get_capabilities(self, obj):
        return capabilities_for(obj)

    def get_self_checkin_enabled(self, obj):
        return OfficeSettings.load().self_checkin_enabled

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value

    def validate_role(self, value):
        current = getattr(self.instance, "role", None)
        if value == current:
            return value
        if value == User.Role.SUPER_ADMIN:
            raise serializers.ValidationError("The super user is created from the server settings, not from this form.")
        if value not in {User.Role.MANAGEMENT, User.Role.EMPLOYEE}:
            raise serializers.ValidationError("Choose Management or Employee.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        if not password:
            raise serializers.ValidationError({"password": "A password is required."})
        user = User(**validated_data)
        user.set_password(password)
        if user.role == User.Role.SUPER_ADMIN:
            user.is_staff = True
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.is_staff = instance.role == User.Role.SUPER_ADMIN or instance.is_superuser
        instance.save()
        return instance


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value
