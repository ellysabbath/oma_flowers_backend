from django.shortcuts import render
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework import generics, permissions, filters
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import random
import string
from datetime import timedelta
import logging
from .models import User, VerificationCode
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    ChangePasswordSerializer, EmailVerificationSerializer,
    ResetPasswordRequestSerializer, ResetPasswordVerifySerializer,
    UpdateProfileSerializer
)

logger = logging.getLogger(__name__)

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate verification code
        verification_code = ''.join(random.choices(string.digits, k=6))
        
        # Save to database
        VerificationCode.objects.create(
            user=user,
            code=verification_code,
            type='email',
            expires_at=timezone.now() + timedelta(minutes=30)
        )
        
        # Send verification email
        try:
            send_mail(
                subject='Verify Your OMA Flowers Account',
                message=f'Your verification code is: {verification_code}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Verification email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
        
        return Response({
            'message': 'Registration successful. Please check your email for verification code.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        refresh = RefreshToken.for_user(user)
        
        # Get distributor info if user is a distributor
        distributor_data = None
        if user.is_distributor():
            try:
                distributor = user.distributor_profile
                distributor_data = {
                    'rank': distributor.rank,
                    'level': distributor.level,
                    'pbv': str(distributor.pbv),
                    'cgv': str(distributor.cgv)
                }
            except:
                pass
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
            'distributor': distributor_data,
            'user_type': user.user_type
        })

class RefreshTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                'access': str(refresh.access_token)
            })
        except:
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logged out successfully'})
        except:
            return Response({'message': 'Logged out successfully'})

class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class UpdateProfileView(generics.UpdateAPIView):
    serializer_class = UpdateProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'old_password': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({'message': 'Password changed successfully'})

class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        logger.info(f"Verify email request received: {request.data}")
        
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        
        logger.info(f"Verifying email: {email}, code: {code}")
        
        try:
            user = User.objects.get(email=email)
            
            # Check if user is already verified
            if user.email_verified:
                logger.info(f"User {email} already verified")
                return Response(
                    {'message': 'Email already verified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Find the verification code in database
            verification = VerificationCode.objects.filter(
                user=user,
                code=code,
                type='email',
                is_used=False
            ).first()
            
            if not verification:
                logger.warning(f"No valid verification code found for {email}")
                return Response(
                    {'error': 'Invalid verification code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Found verification code for {email}: expires at {verification.expires_at}")
            
            if not verification.is_valid():
                logger.warning(f"Verification code expired for {email}")
                return Response(
                    {'error': 'Verification code has expired. Please request a new one.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark as used and verify user
            verification.is_used = True
            verification.save()
            
            user.email_verified = True
            user.email_verified_at = timezone.now()
            user.status = 'active'
            user.save()
            
            logger.info(f"User {email} verified successfully")
            return Response({'message': 'Email verified successfully'})
            
        except User.DoesNotExist:
            logger.error(f"User not found: {email}")
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        logger.info(f"Resend verification request for: {email}")
        
        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            
            if user.email_verified:
                return Response(
                    {'message': 'Email already verified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Invalidate old verification codes
            VerificationCode.objects.filter(
                user=user,
                type='email',
                is_used=False
            ).update(is_used=True)
            
            # Generate new verification code
            verification_code = ''.join(random.choices(string.digits, k=6))
            
            VerificationCode.objects.create(
                user=user,
                code=verification_code,
                type='email',
                expires_at=timezone.now() + timedelta(minutes=30)
            )
            
            # Send verification email
            try:
                send_mail(
                    subject='Verify Your OMA Flowers Account',
                    message=f'Your new verification code is: {verification_code}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                logger.info(f"New verification code sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
            
            return Response({'message': 'New verification code sent'})
            
        except User.DoesNotExist:
            logger.error(f"User not found: {email}")
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class ResetPasswordRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        logger.info(f"Password reset request for: {email}")
        
        try:
            user = User.objects.get(email=email)
            
            # Invalidate old reset codes
            VerificationCode.objects.filter(
                user=user,
                type='password_reset',
                is_used=False
            ).update(is_used=True)
            
            # Generate reset code
            reset_code = ''.join(random.choices(string.digits, k=6))
            
            VerificationCode.objects.create(
                user=user,
                code=reset_code,
                type='password_reset',
                expires_at=timezone.now() + timedelta(minutes=30)
            )
            
            try:
                send_mail(
                    subject='Password Reset - OMA Flowers',
                    message=f'Your password reset code is: {reset_code}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                logger.info(f"Password reset code sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {str(e)}")
            
            return Response({'message': 'Password reset code sent to your email'})
            
        except User.DoesNotExist:
            logger.error(f"User not found: {email}")
            return Response(
                {'error': 'User with this email does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

class ResetPasswordVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        password = serializer.validated_data['password']
        
        logger.info(f"Password reset verification for: {email}")
        
        try:
            user = User.objects.get(email=email)
            
            # Find the reset code in database
            verification = VerificationCode.objects.filter(
                user=user,
                code=code,
                type='password_reset',
                is_used=False
            ).first()
            
            if not verification:
                logger.warning(f"No valid reset code found for {email}")
                return Response(
                    {'error': 'Invalid verification code'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not verification.is_valid():
                logger.warning(f"Reset code expired for {email}")
                return Response(
                    {'error': 'Verification code has expired. Please request a new one.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark as used
            verification.is_used = True
            verification.save()
            
            # Reset password
            user.set_password(password)
            user.save()
            
            logger.info(f"Password reset successfully for {email}")
            return Response({'message': 'Password reset successfully'})
            
        except User.DoesNotExist:
            logger.error(f"User not found: {email}")
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class AdminUsersListView(generics.ListAPIView):
    """
    Get all users (for converting to distributors)
    Any authenticated user can access this
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Start with all users - NO admin check
        queryset = User.objects.all().order_by('-created_at')
        
        # Filter by user_type if provided
        user_type = self.request.query_params.get('user_type')
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        
        # Filter by status if provided
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Exclude users who are already distributors
        exclude_distributors = self.request.query_params.get('exclude_distributors', 'true')
        if exclude_distributors == 'true':
            queryset = queryset.exclude(user_type='distributor')
        
        # Exclude admin users from the list
        queryset = queryset.exclude(user_type='admin')
        
        return queryset


class CustomerListView(generics.ListAPIView):
    """
    List all customers (users with user_type='customer')
    """
    queryset = User.objects.filter(user_type='customer').order_by('-created_at')
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]  # Or IsAuthenticated for production
    filter_backends = [filters.SearchFilter]
    search_fields = ['email', 'first_name', 'last_name', 'full_name']