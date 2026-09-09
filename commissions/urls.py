from django.urls import path
from .views import CommissionListView, CommissionDetailView

urlpatterns = [
    path('', CommissionListView.as_view(), name='commission-list'),
    path('<int:id>/', CommissionDetailView.as_view(), name='commission-detail'),
]