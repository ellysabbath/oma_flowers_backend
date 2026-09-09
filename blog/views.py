from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import BlogPost
from .serializers import BlogPostSerializer

class BlogPostListView(generics.ListAPIView):
    queryset = BlogPost.objects.select_related('author').filter(status='published')
    serializer_class = BlogPostSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['title', 'excerpt', 'content']

class BlogPostDetailView(generics.RetrieveAPIView):
    queryset = BlogPost.objects.select_related('author').filter(status='published')
    serializer_class = BlogPostSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'

class AdminBlogPostListView(generics.ListCreateAPIView):
    queryset = BlogPost.objects.select_related('author').all()
    serializer_class = BlogPostSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'category']
    search_fields = ['title', 'excerpt', 'content']
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class AdminBlogPostDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = BlogPost.objects.select_related('author').all()
    serializer_class = BlogPostSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'