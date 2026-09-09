from django.urls import path
from .views import (
    BlogPostListView, BlogPostDetailView,
    AdminBlogPostListView, AdminBlogPostDetailView
)

urlpatterns = [
    # Public endpoints
    path('', BlogPostListView.as_view(), name='blog-list'),
    path('<int:id>/', BlogPostDetailView.as_view(), name='blog-detail'),
    
    # Admin endpoints
    path('admin/', AdminBlogPostListView.as_view(), name='admin-blog-list'),
    path('admin/<int:id>/', AdminBlogPostDetailView.as_view(), name='admin-blog-detail'),
]