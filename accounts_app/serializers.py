from rest_framework import serializers
from .models import Passenger, generate_otp
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import smart_bytes, force_str
from datetime import timedelta
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import send_mail, BadHeaderError
from smtplib import SMTPRecipientsRefused, SMTPException


class PassengerRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, error_messages={'required': 'Passenger must input a password'})
    email = serializers.EmailField(required=True, error_messages={'required': 'An email must be provided'})
    phone_number = serializers.CharField(required=True, error_messages={'required': 'Passenger must provide a phone number'})
    first_name = serializers.CharField(required=True, error_messages={'required': 'First name is required'})
    last_name = serializers.CharField(required=True, error_messages={'required': 'Last name is required'})

    class Meta: # Meta class adds additional info for the main class which is PassengerRegistrationSerializer
        model = Passenger
        fields = ['email', 'phone_number', 'first_name', 'last_name', 'password']

    def validate(self, attrs):
        errors = {}
        phone = attrs.get('phone_number')
        
        if not phone.isdigit() or len(phone) < 11:
            errors['phone_number'] = "Phone number must be at least 11 digits."
            
        password = attrs.get('password')
        if len(password) < 12:
            errors['password'] = "Password must be at least 12 characters long."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


    def create(self, validated_data): # validated_data is the data that has been validated by the serializer
        try:
            passenger = Passenger.objects.create_user( # creates a new user using the create_user method from PassengerManager
                email=validated_data['email'],
                phone_number=validated_data['phone_number'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                password=validated_data['password']
            )
        except Exception:
            raise serializers.ValidationError({"email": "An admin with this email already exists."})
        # Generate OTP for verification
        otp_code = generate_otp(validated_data['email'], 'REGISTER') # this line generates an OTP for the email provided during registration
        user = Passenger.objects.get(email=validated_data['email'])
        send_mail(
            subject='Rail-me Email Verification OTP',
            message=f"Dear {user.first_name},\n\nWelcome on-board Rail-Me.\n\nHope you enjoy the experience.\n\nYour OTP is {otp_code}. It expires in 5 minutes.\n\nBest Regards,\nRail-me Team.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[validated_data['email']],
            fail_silently=False,
        )
        return passenger


class OTPRequestSerializer(serializers.Serializer):
    target = serializers.CharField()

    def create(self, validated_data):
        target = validated_data['target']
        otp_code = generate_otp(target)

        try:
            validate_email(target)
            user = Passenger.objects.filter(email=target).first()
            if not user:
                raise serializers.ValidationError({"error": "No account found with this email address."})

            try:
                send_mail(
                subject="Rail-me Email Verification Code",
                message=(
                    f"Dear {user.first_name},\n\n"
                    f"Your OTP is {otp_code}. It expires in 5 minutes.\n\n"
                    "Thank you for choosing Rail-me"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[target],
                fail_silently=False,
            )
            except SMTPRecipientsRefused:
                raise serializers.ValidationError({"error": "Recipient email temporarily unavailable. Try again later."})
            except (BadHeaderError, SMTPException) as i:
                raise serializers.ValidationError({"error": f"Email sending failed: {str(i)}"})

            return {"message": "OTP sent successfully via email."}

        except ValidationError:
            if target.isdigit() and len(target) == 11:
                user = Passenger.objects.filter(phone_number=target).first()
                if not user:
                    raise serializers.ValidationError({"error": "No account found with this phone number."})

               
                print(f"Send SMS to {target} with OTP {otp_code}")
                return {"message": "OTP sent successfully via SMS."}

            raise serializers.ValidationError({"error": " Please enter a valid email or phone number!!"})


class PassengerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs): # attrs contains the data that has been validated by the serializer as a dictionary while self is the instance of the serializer class
        email = attrs.get('email') # get method retrieves the value associated with the key 'email' from the attrs dictionary
        password = attrs.get('password')

        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError({"detail":"Invalid email or password."})
        
        if not user.is_verified:
            raise serializers.ValidationError({"detail":"Please verify your email before logging in."})
        attrs['user'] = user # stores the successfully authenticated user in attrs dictionary for later use in the view
        # attrs['user'] was used to add to the dictionary without losing the other validated data while attrs=user would replace the entire dictionary with just the user object
        return attrs
    
    
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not Passenger.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found with this email.")
        return value

    def save(self):
        email = self.validated_data['email']
        user = Passenger.objects.get(email=email)
        # Generate JWT token for password reset
        jwt_token = AccessToken.for_user(user) # AccessToken is a module from simplejwt that creates a JWT token for a user
        jwt_token.set_exp(lifetime=timedelta(minutes=15))
        
        # Encode user ID
        uidb64 = urlsafe_base64_encode(smart_bytes(user.id)) # encodes the user's ID safely for use in a URL

        reset_link = f"https://rail-me-be.onrender.com/accounts/reset-password/{uidb64}/{jwt_token}/"

        send_mail(
            subject="Password Reset Request",
            message=f"Hello {user.first_name},\n\nUse the link below to reset your password. "
                    f"This link will expire in 15 minutes.\n\n{reset_link}\n\n"
                    "If you didn’t request this, please ignore this email.",
            from_email=settings.DEFAULT_FROM_EMAIL, # who's sending the email
            recipient_list=[email], # who's receiving the email
        )
        return Response({"message": "Password reset link sent to your email"}, status=status.HTTP_200_OK)


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def save(self, uidb64, token): # safe method takes uidb64 and token from the URL
        # Decode the UID to get the user
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = Passenger.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Passenger.DoesNotExist):
            raise serializers.ValidationError({"error": "Invalid reset link"})

        # Validate the JWT token
        try:
            decoded_token = AccessToken(token)  # Will raise TokenError if invalid or expired
            # Optionally confirm the token belongs to the same user
            if str(decoded_token['user_id']) != str(user.id):
                raise serializers.ValidationError({"error": "Token does not belong to this user."})
        except TokenError:
            raise serializers.ValidationError({"error": "Invalid or expired token"})

        new_password = self.validated_data.get("new_password")
        confirm_password = self.validated_data.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError({"error": "Passwords do not match"})

        # Update user password securely
        user.set_password(new_password)
        user.save()

        return user
    
