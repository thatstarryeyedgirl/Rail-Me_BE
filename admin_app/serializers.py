from rest_framework import serializers
from .models import Admin, generate_otp, Train
from django.conf import settings
import base64
from django.core.mail import send_mail
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import smart_bytes, force_str
from datetime import timedelta
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
import os
from accounts_app.models import Passenger
from smtplib import SMTPRecipientsRefused



class AdminRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, error_messages={'required': 'Admin must input a password'})
    email = serializers.EmailField(required=True, error_messages={'required': 'Admin must have an email'})
    phone_number = serializers.CharField(required=True, error_messages={'required': 'Admin must have a phone number'})
    first_name = serializers.CharField(required=True, error_messages={'required': 'First name is required'})
    last_name = serializers.CharField(required=True, error_messages={'required': 'Last name is required'})

    class Meta: # Meta class adds additional info for the main class which is PassengerRegistrationSerializer
        model = Admin
        fields = ['email', 'phone_number', 'first_name', 'last_name', 'password']
        
    def validate(self, attrs):
        errors = {}
        email = attrs.get('email')
        phone = attrs.get('phone_number')
        
        # Check if email already exists
        if Admin.objects.filter(email=email).exists():
            errors['email'] = "An admin with this email already exists."
         
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
            admin = Admin.objects.get(email=validated_data['email'])
            if admin:
                raise serializers.ValidationError({"email": "An admin with this email already exists."})
        except Admin.DoesNotExist:
            admin = Admin.objects.create_user( # creates a new user using the create_user method from PassengerManager
                email=validated_data['email'],
                phone_number=validated_data['phone_number'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                password=validated_data['password']
            )
        # Generate OTP for verification
        otp_code = generate_otp(validated_data['email'], 'REGISTER') # this line generates an OTP for the email provided during registration
        # otp_code_phone = generate_otp(validated_data['phone_number'], 'REGISTER')
        user = Admin.objects.get(email=validated_data['email'])
        try:
            send_mail(
                subject='Rail-me Email Verification OTP',
                message=f"Dear Admin {user.first_name},\n\nWelcome on-board Rail-Me.\n\nHope you enjoy the experience.\n\nYour OTP is {otp_code}. It expires in 5 minutes.\n\nBest Regards,\nRail-me.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[validated_data['email']],
                fail_silently=False,
            )
        except Exception:
            raise serializers.ValidationError({"error": "Failed to send verification email. Please try again."})
        return admin


class OTPRequestSerializer(serializers.Serializer):
    target = serializers.CharField()

    def create(self, validated_data):
        target = validated_data['target']
        otp_code = generate_otp(target)

        try:
            validate_email(target)
            admin = Admin.objects.filter(email=target).first()
            if not admin:
                raise serializers.ValidationError({"error": "No account found with this email address."})

            send_mail(
                subject="Rail-me Email Verification Code",
                message=(
                    f"Dear {admin.first_name},\n\n"
                    f"Your OTP is {otp_code}. It expires in 5 minutes.\n\n"
                    "Thank you for choosing Rail-me"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[target],
                fail_silently=False,
            )

            return {"message": "OTP sent successfully via email."}

        except ValidationError:
            if target.isdigit() and len(target) == 11:
                admin = Admin.objects.filter(phone_number=target).first()
                if not admin:
                    raise serializers.ValidationError({"error": "No account found with this phone number."})

                print(f"Send SMS to {target} with OTP {otp_code}")
                return {"message": "OTP sent successfully via SMS."}

            raise serializers.ValidationError({"error": " Please enter a valid email or phone number!!"})


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs): # attrs contains the data that has been validated by the serializer as a dictionary while self is the instance of the serializer class
        email = attrs.get('email') # get method retrieves the value associated with the key 'email' from the attrs dictionary
        password = attrs.get('password')

        admin = Admin.objects.filter(email=email).first()
        if not admin:
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if not check_password(password, admin.password):
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if not admin.is_verified:
            raise serializers.ValidationError({"detail": "Please verify your email before logging in."})

        attrs['admin'] = admin
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not Admin.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found with this email.")
        return value

    def save(self):
        email = self.validated_data['email']
        admin = Admin.objects.get(email=email)
        # Generate JWT token and include admin_id
        token = AccessToken()
        token['admin_id'] = admin.id
        token.set_exp(lifetime=timedelta(minutes=15))  # token expires in 15 minutes
        # Encode user ID
        uidb64 = urlsafe_base64_encode(smart_bytes(admin.id))
        reset_link = f"https://rail-me-be.onrender.com/admins/reset-password/{uidb64}/{token}/"
        try:
            send_mail(
                subject="Password Reset Request",
                message=f"Hello {admin.first_name},\n\nUse the link below to reset your password. "
                    f"This link will expire in 15 minutes.\n\n{reset_link}\n\n"
                    "If you didn’t request this, please ignore this email.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )
        except SMTPRecipientsRefused:
            raise serializers.ValidationError({"error": "Recipient email temporarily unavailable. Try again later."})
        return {"message": "Password reset link sent to your email"}


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def save(self, uidb64, token): # safe method takes uidb64 and token from the URL
        # Decode the UID to get the user
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            admin = Admin.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Admin.DoesNotExist):
            raise serializers.ValidationError({"error": "Invalid reset link"})

        # Validate the JWT token
        try:
            decoded_token = AccessToken(token)  # Will raise TokenError if invalid or expired
            # Optionally confirm the token belongs to the same user
            if str(decoded_token['admin_id']) != str(admin.id):
                raise serializers.ValidationError({"error": "Token does not belong to this user."})
        except TokenError:
            raise serializers.ValidationError({"error": "Invalid or expired token"})

        new_password = self.validated_data.get("new_password")
        confirm_password = self.validated_data.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError({"error": "Passwords do not match"})

        # Update user password securely
        admin.set_password(new_password)
        admin.save()

        return admin


class BinaryImageField(serializers.Field):
    def to_representation(self, value):
        if value:
            return base64.b64encode(value).decode('utf-8')
        return None

    def to_internal_value(self, data):
        # Accept both uploaded files and base64 strings
        if hasattr(data, 'read'):  # file upload (multipart/form-data)
            return data.read()
        try:
            return base64.b64decode(data)
        except Exception:
            raise serializers.ValidationError("Invalid image. Must be a valid file or base64 string.")


class TrainSerializer(serializers.ModelSerializer):
    # Accept image as file or base64 string
    image = BinaryImageField(required=True)

    class Meta:
        model = Train
        fields = ['train_name', 'departure_station', 'destination', 'arrival_station', 'price', 'image', 'seats_remaining', 'created_at']
        read_only_fields = ['arrival_time']
        
        extra_kwargs = {
            'train_name': {'error_messages': {'required': 'Make a choice from the available trains'}},
            'departure_station': {'error_messages': {'required': 'Please select a departure station.'}},
            'destination': {'error_messages': {'required': 'Please select a destination station.'}},
            'arrival_station': {'error_messages': {'required': 'Please provide an arrival station.'}},
            'price': {'error_messages': {'required': 'Please enter the ticket price.'}},
            'image': {'error_messages': {'required': 'An image of the train is required.'}},
        }
        
    def validate(self, attrs):
        train_name = attrs.get('train_name')
        departure_station = attrs.get('departure_station')
        destination = attrs.get('destination')
        image = attrs.get('image')
        arrival_station = attrs.get('arrival_station')

        
        # Ensure image is provided
        if not image:
            raise serializers.ValidationError({"image": "An image is required for every train."})
        # If key details are missing, stop validation early
        if not train_name or not departure_station or not destination:
            return attrs
        # Define allowed routes
        valid_routes = {
            'Rail-Me Express 001' : ('Abeokuta', 'Katsina'),
            'Rail-Me Express 002': ('Abeokuta', 'Kaduna'),
            'Rail-Me Express 003': ('Abeokuta', 'Kano'),
            'Rail-Me Express 004': ('Abeokuta', 'Jigawa'),
            'Rail-Me Express 005': ('Abeokuta', 'Abuja'),
            'Rail-Me Express 006': ('Abeokuta', 'Kebbi'),
            'Rail-Me Express 007': ('Abeokuta', 'Sokoto'),
            'Rail-Me Express 008': ('Abeokuta', 'Zamfara'),
            'Rail-Me Express 009': ('Abeokuta', 'Adamawa'),
            'Rail-Me Express 010': ('Abeokuta', 'Bauchi'),
            'Rail-Me Express 020': ('Abeokuta', 'Borno'),
            'Rail-Me Express 030': ('Abeokuta', 'Gombe'),
            'Rail-Me Express 040': ('Abeokuta', 'Taraba'),
            'Rail-Me Express 050': ('Abeokuta', 'Yobe'),
            'Rail-Me Express 060': ('Abeokuta', 'Kogi'),
            'Rail-Me Express 070': ('Abeokuta', 'Benue'),
            'Rail-Me Express 080': ('Abeokuta', 'Kwara'),
            'Rail-Me Express 090': ('Abeokuta', 'Nasarawa'),
            'Rail-Me Express 101': ('Abeokuta', 'Niger'),
            'Rail-Me Express 202': ('Abeokuta', 'Plateau'),
        }
        # Validate only if train name exists in allowed routes
        
        if train_name not in valid_routes:
            raise serializers.ValidationError({
                "name": f"'{train_name}' is not a valid train route name."
                })
        
        correct_departure, correct_destination = valid_routes[train_name]
        
        # Check departure station
        if correct_departure.lower() not in departure_station.lower():
            raise serializers.ValidationError({
                "departure_station": f"The departure station for {train_name} must be from {correct_departure}."
                })
        # Prevent duplication of train for same route  
        if Train.objects.filter(
            train_name=train_name,
            departure_station=departure_station,
            destination=destination
        ).exists():
            raise serializers.ValidationError(
                {"detail": f"A train named '{train_name}' already runs from {departure_station} to {destination}."}
            )
            
        # Check destination field
        if correct_destination.lower() not in destination.lower():
            raise serializers.ValidationError({
                "destination": f"The destination for {train_name} must be to {correct_destination}."
                })
            # Check arrival station matches destination city
        if correct_destination.lower() not in arrival_station.lower():
            raise serializers.ValidationError({
                "arrival_station": f"The arrival station for {train_name} must be located in {correct_destination}."
                })
            
        # Prevent same departure and destination
        if correct_departure.lower() == correct_destination.lower():
            raise serializers.ValidationError({
                "route": "Departure and destination cannot be the same city."
                })
        return attrs

        
    def get_image_base64(self, obj):
        if obj.image and hasattr(obj.image, 'path'):
            try:
                with open(obj.image.path, 'rb') as image_file:
                    return base64.b64encode(image_file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
            return None  
        
    def create(self, validated_data):
        image_data = validated_data.get('image')

        # If image_data looks like a file path (e.g., "C:/Users/.../train.png")
        if isinstance(image_data, str) and os.path.exists(image_data):
            with open(image_data, 'rb') as f:
                validated_data['image'] = f.read()

        # If it’s uploaded as a file (from Postman or frontend)
        elif hasattr(image_data, 'read'):
            validated_data['image'] = image_data.read()

        # If it’s base64 (optional)
        elif isinstance(image_data, str):
            try:
                validated_data['image'] = base64.b64decode(image_data)
            except Exception:
                raise serializers.ValidationError("Invalid base64 image data.")

        train = Train.objects.create(**validated_data)
        return train


class CommuterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passenger
        fields = ['id', 'email', 'phone_number', 'first_name', 'last_name', 'date_joined']
        read_only_fields = fields
        

