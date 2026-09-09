from django.urls import path
from .views import AwardListView, AwardDetailView

urlpatterns = [
    path('', AwardListView.as_view(), name='award-list'),
    path('<int:id>/', AwardDetailView.as_view(), name='award-detail'),
]