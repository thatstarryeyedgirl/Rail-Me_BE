from rest_framework import generics, permissions, status
from .models import Admin, Train, OTP
from .serializers import (TrainSerializer, AdminRegistrationSerializer, AdminLoginSerializer, OTPRequestSerializer, 
                          ForgotPasswordSerializer, ResetPasswordSerializer, CommuterSerializer)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from accounts_app.models import Passenger
from bookings_app.models import Booking


# Create your views here.
class AdminRegistrationView(APIView):
    def post(self, request): # handles POST requests to register a new passenger
        serializer = AdminRegistrationSerializer(data=request.data) # passes the user's data into the registration serializer to check it
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Admin registered successfully! OTP sent to email for verification."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendOtpView(APIView):
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class VerifyOTPView(APIView):
    def post(self, request):
        target = request.data.get("target")
        code = request.data.get("otp")

        if not target or not code:
            return Response({"error": "Target and OTP code are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Find the OTP record
        otp_instance = OTP.objects.filter(target=target, code=code, is_used=False).last()

        if not otp_instance:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() > otp_instance.expires_at:
            return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # Get the user related to this target
        admin = Admin.objects.filter(email=target).first()
        if not admin:
            return Response({"error": "Admin not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if admin.is_verified:
            return Response({"message": "Admin is already verified."}, status=status.HTTP_200_OK)

        # Mark the user as verified
        admin.is_verified = True
        admin.save()

        # Mark OTP as used
        otp_instance.is_used = True
        otp_instance.save()

        return Response({"message": "Account verified successfully."}, status=status.HTTP_200_OK)
    

class AdminLoginView(APIView):
    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        if serializer.is_valid():
            admin = serializer.validated_data['admin']
            refresh = RefreshToken.for_user(admin)
            refresh["admin_id"] = admin.id
            
            access = refresh.access_token
            access["admin_id"] = admin.id
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password reset link sent to your email"}, status=status.HTTP_200_OK)
    
    
class ResetPasswordView(APIView):
    def post(self, request, uidb64, token, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(uidb64=uidb64, token=token)
        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
    
    
class AdminJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        admin_id = validated_token.get("admin_id")
        
        if not admin_id:
            # Instead of generic Exception, raise DRF-friendly error
            raise AuthenticationFailed("Invalid token: admin_id missing")

        try:
            return Admin.objects.get(id=admin_id)
        except Admin.DoesNotExist:
            raise AuthenticationFailed("Admin not found")
        
        
class TrainCreateView(generics.CreateAPIView):
    queryset = Train.objects.all()
    serializer_class = TrainSerializer
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]


class TrainListView(generics.ListAPIView):
    queryset = Train.objects.all()
    serializer_class = TrainSerializer
    permission_classes = [permissions.IsAuthenticated]

    
class TrainDeleteView(generics.DestroyAPIView):
    queryset = Train.objects.all()
    serializer_class = TrainSerializer
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    

class CommuterListView(generics.ListAPIView):
    queryset = Passenger.objects.all()
    serializer_class = CommuterSerializer
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    

class TotalBookingsView(APIView):
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        total_bookings = Booking.objects.count()
        return Response(
            {"total_bookings": total_bookings},
            status=status.HTTP_200_OK
        )
        

