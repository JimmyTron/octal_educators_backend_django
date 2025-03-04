from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
# todo add celery to make this send email work
from task_manager.tasks import send_email_task


from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.mixins import RetrieveModelMixin, ListModelMixin, CreateModelMixin, UpdateModelMixin
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import BasePermission, SAFE_METHODS
# from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.throttling import UserRateThrottle 

from .serializers import BlogSerializer, CategorySerializer, CommentSerializer, ViewCountSerializer
from .models import Blog, Category, Comment, ViewCount, Like
from .pagination import PostLimitOffsetPagination
from .throttles import BlogRateThrottle

from accounts.permissions import ReadOnlyOrAuthenticated

# class ReadOnlyOrAuthenticated(BasePermission):
#     # Custom permission class that allows read access to anyone, but only allows
#     # authenticated users to modify the data
#     def has_permission(self, request, view):
#         if request.method in SAFE_METHODS:
#             return True
#         return request.user.is_authenticated

# Viewset for the Blog model
class BlogViewSet(
    GenericViewSet, ListModelMixin, RetrieveModelMixin, CreateModelMixin,UpdateModelMixin,
):
    # Sets the serializer class and permission class to be used by this viewset
    serializer_class = BlogSerializer
    permission_classes = [ReadOnlyOrAuthenticated]
    pagination_class = PostLimitOffsetPagination
    throttle_classes = [UserRateThrottle, BlogRateThrottle]
     
    def get_queryset(self):
        # Returns all Blog objects and filters based on the category_id query parameter if it exists
        queryset = Blog.objects.select_related('category').all()
        category_id = self.request.query_params.get('category_id')
        print("get all blogs by category")
    
        if category_id is not None:
            queryset = queryset.filter(
                category_id=category_id)
        return queryset

    def perform_create(self, serializer):
        # When a new Blog object is created, sets the created_by field to the current user
        print("create owner of the blog")
        if serializer.is_valid(raise_exception=True):         
            serializer.validated_data['created_by'] = self.request.user
            serializer.save()
            print("created owner of the blog")
            return Response(serializer.data, status=200)
        else:
            return Response({"errors": serializer.errors}, status=400)
        
    

# Viewset for the Category model
class CategoryViewSet(GenericViewSet, ListModelMixin):
    # Sets the queryset, serializer class, and permission class to be used by this viewset
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [ReadOnlyOrAuthenticated]

# Viewset for the Comment model
class CommentViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin, CreateModelMixin,UpdateModelMixin,):
    # Sets the queryset, serializer class, and permission class to be used by this viewset
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [ReadOnlyOrAuthenticated]
    
    def post(self, request, slug, serializer, *args, **kwargs):
        # When a new Comment object is created, sets the created_by and post fields to the current user and the specified Blog object respectively
        post = get_object_or_404(Blog, slug=slug)
        if serializer.is_valid(raise_exception=True):
            serializer.save(created_by=request.user, post=post)
            return Response(serializer.data, status=200)
        else:
            return Response({"errors": serializer.errors}, status=400)

# # Viewset to handle view count operations for blog posts
class ViewCountViewSet(GenericViewSet):
    # Sets the queryset and serializer class to be used by this viewset
    queryset = ViewCount.objects.all()
    serializer_class = ViewCountSerializer

    # Gets the ViewCount object for the specified blog post, creating a new object if one does not exist
    def get_object(self):
        blog_post_id = self.kwargs['blog_post_id']
        obj, _ = ViewCount.objects.get_or_create(blog_post_id=blog_post_id)
        return obj

    # Action to increment the view count for the specified blog post
    @action(detail=True, methods=['post'],name='increment_viewers')
    def increment_viewers(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.increment_viewers()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
 # Function-based view to handle creating likes for blog posts   
@api_view(['POST'])
def post_like(request, pk):
    post = Blog.objects.get(pk=pk)

    # Check if user has already liked the post
    if not post.likes.filter(created_by=request.user):
        like = Like.objects.create(created_by=request.user)

        # Increment likes count for blog post and add new like object
        post = Blog.objects.get(pk=pk)
        post.likes_count = post.likes_count + 1
        post.likes.add(like)
        post.save()

        return JsonResponse({'message': 'like created'})
    else:
        return JsonResponse({'message': 'post already liked'})
    
# subscribers
@login_required
def subscribe_to_blog(request, blog_id):
    blog = get_object_or_404(Blog, id=blog_id)
    blog.subscribers.add(request.user)
    return JsonResponse({'message': 'subscribed'})

@login_required
def unsubscribe_from_blog(request, blog_id):
    blog = get_object_or_404(Blog, id=blog_id)
    blog.subscribers.remove(request.user)
    return JsonResponse({'message': 'unsubscribed'})

@login_required
def is_user_subscribed(request, blog_id):
    blog = Blog.objects.filter(id=blog_id, subscribers=request.user).exists()
    return JsonResponse({'subscribed': blog})

@login_required
def list_subscribers(request, blog_id):
    try:
        blog = Blog.objects.get(id=blog_id)
    except Blog.DoesNotExist:
        return JsonResponse({'error': 'Blog not found'}, status=404)

    if blog.owner == request.user or request.user.is_superuser:
        # User is the owner of the blog or an admin
        subscribers = blog.subscribers.all()
        subscriber_list = [subscriber.username for subscriber in subscribers]

        return JsonResponse({'subscribers': subscriber_list})
    else:
        # User is not the owner or an admin, only return the total number of subscribers
        subscriber_count = blog.subscribers.count()

        return JsonResponse({'subscriber_count': subscriber_count})
    
#TODO class based likes
# class PostLikeView(APIView):
#     def post(self, request, pk):
#         post = Blog.objects.get(pk=pk)

#         if not post.likes.filter(created_by=request.user):
#             like = Like.objects.create(created_by=request.user)

#             post = Blog.objects.get(pk=pk)
#             post.likes_count = post.likes_count + 1
#             post.likes.add(like)
#             post.save()

#             return JsonResponse({'message': 'like created'})
#         else:
#             return JsonResponse({'message': 'post already liked'})

# !not working, waiting for celery
def send_email(request):
    # Code to gather the email subject, message, from_email, and recipient_list
    subject = 'Hello'
    message = 'This is a test email'
    from_email = 'sender@example.com'
    recipient_list = ['recipient@example.com']
    send_email_task.delay(subject, message, from_email, recipient_list)
