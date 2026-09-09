from rest_framework import serializers
from users.serializers import UserSerializer
from .models import BlogPost

class BlogPostSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    
    class Meta:
        model = BlogPost
        fields = (
            'id', 'title', 'slug', 'excerpt', 'content', 'image',
            'category', 'author', 'author_name', 'read_time',
            'status', 'published_at', 'created_at'
        )