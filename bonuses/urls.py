from django.urls import path
from .views import BonusListView, BonusDetailView

urlpatterns = [
    path('', BonusListView.as_view(), name='bonus-list'),
    path('<int:id>/', BonusDetailView.as_view(), name='bonus-detail'),
]