from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer

class CustomRegisterSerializer(RegisterSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    def custom_signup(self, request, user):
        user.first_name = self.validated_data.get('first_name', '')
        user.last_name = self.validated_data.get('last_name', '')
        user.save(update_fields=['first_name', 'last_name'])

        print(f"=== REGISTRATION EMAIL DEBUG ===")
        print(f"New user: {user.email}")
        try:
            from .email_service import send_welcome_email
            send_welcome_email(user)
            print("Welcome email sent successfully!")
        except Exception as e:
            print(f"WELCOME EMAIL ERROR: {e}")

