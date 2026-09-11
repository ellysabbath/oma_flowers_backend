# users/admin_views.py
"""
Admin-only CRUD for User records.

Endpoints (all under /api/v1/admin/users/):
    GET     /                       list all users (paginated, filterable)
    POST    /                       create user
    GET     /<id>/                  retrieve single user
    PATCH   /<id>/                  partial update
    PUT     /<id>/                  full update
    DELETE  /<id>/                  delete user
    POST    /<id>/set-password/     set a new password
    POST    /<id>/activate/         reactivate account
    POST    /<id>/deactivate/       deactivate account
    POST    /<id>/ban/              set status='banned'
    POST    /<id>/unban/            set status='active'
    POST    /<id>/verify-email/     mark email as verified
    POST    /<id>/make-admin/       promote to admin
    POST    /<id>/make-distributor/ promote to distributor
    POST    /<id>/make-customer/    demote to customer

Notes:
- These views are intentionally open at the DRF layer so you can wire
  them behind whatever admin auth you use (session, JWT role, IP, etc.).
- Add `permission_classes = [IsAdminUser]` in each view (commented) if
  you want DRF to enforce it too.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer

User = get_user_model()


# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------

class AdminUserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _apply_filters(qs, request):
    """Apply querystring filters: user_type, status, search, ordering."""
    user_type = request.query_params.get('user_type')
    if user_type:
        qs = qs.filter(user_type=user_type)

    status_param = request.query_params.get('status')
    if status_param:
        qs = qs.filter(status=status_param)

    email_verified = request.query_params.get('email_verified')
    if email_verified is not None:
        qs = qs.filter(email_verified=str(email_verified).lower() in ('1', 'true', 'yes'))

    is_active = request.query_params.get('is_active')
    if is_active is not None:
        qs = qs.filter(is_active=str(is_active).lower() in ('1', 'true', 'yes'))

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone__icontains=search)
        )

    ordering = request.query_params.get('ordering') or '-date_joined'
    allowed_ordering = {
        'date_joined', '-date_joined',
        'created_at', '-created_at',
        'email', '-email',
        'user_type', '-user_type',
    }
    if ordering in allowed_ordering:
        qs = qs.order_by(ordering)

    return qs


def _error(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': message}, status=code)


# ------------------------------------------------------------------
# List + Create
# ------------------------------------------------------------------

class AdminUserListCreateView(APIView):
    """
    GET  /api/v1/admin/users/     → paginated list of all users
    POST /api/v1/admin/users/     → create a user
    """
    # permission_classes = [IsAdminUser]   # ← enable if you want DRF to enforce it

    def get(self, request):
        qs = User.objects.all()
        qs = _apply_filters(qs, request)

        paginator = AdminUserPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = UserSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        data = request.data.copy()

        # Require password on admin-create
        password = data.get('password')
        if not password:
            return _error('password is required.')

        # Default role if not provided
        data.setdefault('user_type', 'customer')
        data.setdefault('status', 'active')

        serializer = UserSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = User(**{
            k: v for k, v in serializer.validated_data.items()
            if k not in ('password', 'password2')
        })
        # Split full_name if only that was provided
        if data.get('full_name') and not data.get('first_name'):
            parts = str(data['full_name']).split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''

        user.set_password(password)
        user.save()

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------------
# Retrieve + Update + Delete
# ------------------------------------------------------------------

class AdminUserDetailView(APIView):
    """
    GET    /api/v1/admin/users/<id>/
    PATCH  /api/v1/admin/users/<id>/
    PUT    /api/v1/admin/users/<id>/
    DELETE /api/v1/admin/users/<id>/
    """
    # permission_classes = [IsAdminUser]

    def get_object(self, pk):
        return get_object_or_404(User, pk=pk)

    def get(self, request, pk):
        user = self.get_object(pk)
        return Response(UserSerializer(user).data)

    def patch(self, request, pk):
        user = self.get_object(pk)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def put(self, request, pk):
        user = self.get_object(pk)
        serializer = UserSerializer(user, data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        user = self.get_object(pk)

        # Optional safety: prevent deleting yourself
        if request.user.is_authenticated and request.user.pk == user.pk:
            return _error('You cannot delete your own account.', status.HTTP_403_FORBIDDEN)

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------
# Action endpoints
# ------------------------------------------------------------------

class AdminUserSetPasswordView(APIView):
    """POST /api/v1/admin/users/<id>/set-password/   body: { password }"""
    # permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        password = request.data.get('password')
        if not password:
            return _error('password is required.')
        user.set_password(password)
        user.save(update_fields=['password'])
        return Response({'detail': 'Password updated.'})


class AdminUserActivateView(APIView):
    """POST /api/v1/admin/users/<id>/activate/"""
    # permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = True
        if user.status == 'banned':
            user.status = 'active'
        user.save(update_fields=['is_active', 'status'])
        return Response(UserSerializer(user).data)


class AdminUserDeactivateView(APIView):
    """POST /api/v1/admin/users/<id>/deactivate/"""
    # permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response(UserSerializer(user).data)


class AdminUserBanView(APIView):
    """POST /api/v1/admin/users/<id>/ban/"""
    # permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.status = 'banned'
        user.is_active = False
        user.save(update_fields=['status', 'is_active'])
        return Response(UserSerializer(user).data)


class AdminUserUnbanView(APIView):
    """POST /api/v1/admin/users/<id>/unban/"""
    # permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.status = 'active'
        user.is_active = True
        user.save(update_fields=['status', 'is_active'])
        return Response(UserSerializer(user).data)


class AdminUserVerifyEmailView(APIView):
    """POST /api/v1/admin/users/<id>/verify-email/"""
    # permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=['email_verified', 'email_verified_at'])
        return Response(UserSerializer(user).data)


class AdminUserSetRoleView(APIView):
    """
    POST /api/v1/admin/users/<id>/set-role/    body: { user_type: 'admin' | 'distributor' | 'customer' }
    """
    # permission_classes = [IsAdminUser]

    ALLOWED = {'admin', 'distributor', 'customer'}

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user_type = str(request.data.get('user_type', '')).lower()
        if user_type not in self.ALLOWED:
            return _error(f"user_type must be one of {sorted(self.ALLOWED)}.")

        user.user_type = user_type

        # Keep staff/superuser flags coherent with admin role
        if user_type == 'admin':
            user.is_staff = True
        else:
            # Only downgrade if they weren't already a superuser
            if not user.is_superuser:
                user.is_staff = False

        user.save(update_fields=['user_type', 'is_staff'])
        return Response(UserSerializer(user).data)


class AdminUserStatsView(APIView):
    """GET /api/v1/admin/users/stats/   — quick counts for the dashboard."""
    # permission_classes = [IsAdminUser]

    def get(self, request):
        qs = User.objects.all()
        return Response({
            'total': qs.count(),
            'admins': qs.filter(user_type='admin').count(),
            'distributors': qs.filter(user_type='distributor').count(),
            'customers': qs.filter(user_type='customer').count(),
            'active': qs.filter(is_active=True).count(),
            'inactive': qs.filter(is_active=False).count(),
            'banned': qs.filter(status='banned').count(),
            'email_verified': qs.filter(email_verified=True).count(),
        })