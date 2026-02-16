from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Avg, Count
from django.contrib import messages
from django.contrib.auth import login, authenticate, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django import forms
from datetime import timedelta
import hashlib
import time
from .models import Property, Review, Reply, ReviewReport, PropertyOwnerResponse, Notification, ReviewVote, PropertyImage, EmailVerification
from .forms import PropertySearchForm, ReviewForm, PropertyForm, PropertyWithReviewForm, UserRegistrationForm, UserProfileForm, CustomPasswordChangeForm, ReplyForm, ReviewReportForm, PropertyOwnerResponseForm
from .decorators import staff_required
from .notifications import (
    notify_review_posted, notify_reply_posted, notify_owner_response, notify_report_resolved
)

User = get_user_model()


def home(request):
    """Home page redirects to all properties."""
    return redirect('reviews:all_properties')


def terms_of_service(request):
    """Terms of Service page."""
    return render(request, 'reviews/terms_of_service.html')


def privacy_policy(request):
    """Privacy Policy page."""
    return render(request, 'reviews/privacy_policy.html')


def safety_guidelines(request):
    """Safety Guidelines and Disclaimer page."""
    return render(request, 'reviews/safety_guidelines.html')


def all_properties(request):
    """Display all properties with search, filter, and sort functionality."""
    form = PropertySearchForm(request.GET or None)
    # Filter out properties from suspended users
    # Handle cases where created_by might be None (deleted users) - hide those properties
    properties = Property.objects.filter(
        Q(created_by__isnull=False) & Q(created_by__is_suspended=False)
    ).annotate(
        # Count only reviews from non-suspended users
        review_count=Count('reviews', filter=Q(reviews__created_by__isnull=True) | Q(reviews__created_by__is_suspended=False)),
        # Average rating only from non-suspended users
        avg_rating=Avg('reviews__rating', filter=Q(reviews__created_by__isnull=True) | Q(reviews__created_by__is_suspended=False))
    )
    
    # Apply filters
    query = ''
    if form.is_valid():
        # Text search
        if form.cleaned_data.get('query'):
            query = form.cleaned_data['query']
            properties = properties.filter(
                Q(address__icontains=query) |
                Q(city__icontains=query) |
                Q(state__icontains=query) |
                Q(zip_code__icontains=query)
            )
        
        # Property type filter
        if form.cleaned_data.get('property_type'):
            properties = properties.filter(property_type=form.cleaned_data['property_type'])
        
        # State filter
        if form.cleaned_data.get('state'):
            properties = properties.filter(state__icontains=form.cleaned_data['state'])
        
        # City filter
        if form.cleaned_data.get('city'):
            properties = properties.filter(city__icontains=form.cleaned_data['city'])
        
        # Minimum rating filter
        if form.cleaned_data.get('min_rating'):
            min_rating = float(form.cleaned_data['min_rating'])
            properties = properties.filter(avg_rating__gte=min_rating)
        
        # Sorting
        sort_by = form.cleaned_data.get('sort_by', 'newest')
        if sort_by == 'newest':
            properties = properties.order_by('-created_at')
        elif sort_by == 'oldest':
            properties = properties.order_by('created_at')
        elif sort_by == 'rating_high':
            properties = properties.order_by('-avg_rating', '-created_at')
        elif sort_by == 'rating_low':
            properties = properties.order_by('avg_rating', '-created_at')
        elif sort_by == 'most_reviews':
            properties = properties.order_by('-review_count', '-created_at')
        elif sort_by == 'least_reviews':
            properties = properties.order_by('review_count', '-created_at')
        else:
            properties = properties.order_by('-created_at')
    else:
        # Default sorting if form is not valid
        properties = properties.order_by('-created_at')
    
    context = {
        'properties': properties,
        'form': form,
        'query': query,
        'active_filters': {
            'property_type': form.data.get('property_type', ''),
            'state': form.data.get('state', ''),
            'city': form.data.get('city', ''),
            'min_rating': form.data.get('min_rating', ''),
            'sort_by': form.data.get('sort_by', 'newest'),
        }
    }
    return render(request, 'reviews/all_properties.html', context)


@login_required
def create_property(request):
    """Create a new property with optional initial review."""
    if request.method == 'POST':
        form = PropertyWithReviewForm(request.POST, request.FILES)
        if form.is_valid():
            # Create property
            property_obj = Property.objects.create(
                address=form.cleaned_data['address'],
                city=form.cleaned_data['city'],
                state=form.cleaned_data['state'],
                zip_code=form.cleaned_data['zip_code'],
                property_type=form.cleaned_data['property_type'],
                description=form.cleaned_data.get('description', '').strip() or None,
                image=form.cleaned_data.get('image'),  # Keep for backward compatibility
                created_by=request.user
            )
            
            # Handle Cloudinary image public IDs (from direct upload)
            cloudinary_public_ids_str = request.POST.get('cloudinary_public_ids', '')
            cloudinary_public_ids = []
            if cloudinary_public_ids_str:
                # Split comma-separated public IDs
                cloudinary_public_ids = [pid.strip() for pid in cloudinary_public_ids_str.split(',') if pid.strip()]
            
            if cloudinary_public_ids:
                max_images = 6
                public_ids_to_add = cloudinary_public_ids[:max_images]
                
                # Create PropertyImage objects with Cloudinary public IDs
                for idx, public_id in enumerate(public_ids_to_add):
                    # Validate public_id format (basic check)
                    if public_id and isinstance(public_id, str) and len(public_id) > 0:
                        # CloudinaryField accepts public_id directly
                        # The public_id from Cloudinary API already includes the folder path
                        PropertyImage.objects.create(
                            property=property_obj,
                            image=public_id,  # CloudinaryField accepts public_id
                            order=idx
                        )
                
                if len(cloudinary_public_ids) > max_images:
                    messages.warning(request, f'Maximum {max_images} images allowed per property. Only the first {max_images} images were uploaded.')
            
            # Fallback: Handle file uploads if Cloudinary direct upload not used
            images = request.FILES.getlist('images')
            if images and not cloudinary_public_ids:
                max_images = 6
                images_to_add = images[:max_images]
                from .security import validate_image_file, sanitize_filename
                
                valid_images = []
                for idx, img in enumerate(images_to_add):
                    try:
                        validate_image_file(img)
                        img.name = sanitize_filename(img.name)
                        valid_images.append((img, idx))
                    except ValidationError as e:
                        messages.error(request, f'Image {idx + 1}: {str(e)}')
                
                for img, idx in valid_images:
                    PropertyImage.objects.create(
                        property=property_obj,
                        image=img,
                        order=idx
                    )
                
                if len(images) > max_images:
                    messages.warning(request, f'Maximum {max_images} images allowed per property. Only the first {max_images} images were uploaded.')
            
            # Also handle single image field for backward compatibility
            if form.cleaned_data.get('image') and not images:
                # If single image is uploaded and no multiple images, create PropertyImage
                existing_count = PropertyImage.objects.filter(property=property_obj).count()
                if existing_count < 6:
                    from .security import validate_image_file, sanitize_filename
                    try:
                        single_img = form.cleaned_data['image']
                        validate_image_file(single_img)
                        single_img.name = sanitize_filename(single_img.name)
                        PropertyImage.objects.create(
                            property=property_obj,
                            image=single_img,
                            order=0
                        )
                    except ValidationError as e:
                        messages.error(request, f'Image validation failed: {str(e)}')
            
            # Create review if rating is provided (content is optional)
            review_content = form.cleaned_data.get('review_content', '').strip()
            rating = form.cleaned_data.get('rating')
            
            if rating:
                # Spam and duplicate prevention
                # Check for duplicate review (same user, same property)
                existing_review = Review.objects.filter(
                    property=property_obj,
                    created_by=request.user
                ).first()
                
                if existing_review:
                    messages.error(
                        request,
                        'You have already submitted a review for this property. You can edit or delete your existing review.'
                    )
                    return redirect('reviews:property_detail', property_id=property_obj.id)
                
                # Rate limiting: Check if user posted too many reviews recently (max 3 per hour)
                one_hour_ago = timezone.now() - timedelta(hours=1)
                recent_reviews_count = Review.objects.filter(
                    created_by=request.user,
                    created_at__gte=one_hour_ago
                ).count()
                
                if recent_reviews_count >= 3:
                    messages.error(
                        request,
                        'You have submitted too many reviews recently. Please wait before submitting another review.'
                    )
                    return redirect('reviews:property_detail', property_id=property_obj.id)
                
                # Check if user wants to post anonymously
                post_as = request.POST.get('post_as')
                # Checkbox fields: if checked, value is 'on' in POST, and True in cleaned_data
                # If unchecked, not in POST, and False in cleaned_data
                use_real_name = request.POST.get('use_real_name') == 'on' or form.cleaned_data.get('use_real_name', False)
                
                # If post_as checkbox is checked (value='anonymous'), post anonymously
                # Otherwise use real name if use_real_name is checked
                if post_as == 'anonymous' or not use_real_name:
                    # Post anonymously
                    author_name = ''
                    is_anonymous = True
                else:
                    # Use real name (from form or user's name)
                    author_name = form.cleaned_data.get('author_name', '').strip()
                    if not author_name:
                        # Fallback to user's full name or username
                        author_name = request.user.get_full_name() or request.user.username
                    is_anonymous = False
                
                # Auto-generate title from content or rating
                if review_content:
                    auto_title = review_content[:50] + ('...' if len(review_content) > 50 else '')
                else:
                    rating_labels = {1: 'Very Poor', 2: 'Poor', 3: 'Fair', 4: 'Good', 5: 'Excellent'}
                    auto_title = f"{rating} star rating - {rating_labels.get(rating, 'Rating')}"
                
                review = Review.objects.create(
                    property=property_obj,
                    created_by=request.user,
                    title=auto_title,
                    content=review_content if review_content else None,
                    rating=rating,
                    pros_cons=form.cleaned_data.get('pros_cons', ''),
                    date_lived_from=form.cleaned_data.get('date_lived_from'),
                    date_lived_to=form.cleaned_data.get('date_lived_to'),
                    author_name=author_name,
                    is_anonymous=is_anonymous,
                    is_approved=True  # Auto-approve comments
                )
                # Notify property owner
                notify_review_posted(review)
                messages.success(request, 'Property and comment added successfully!')
            else:
                messages.success(request, 'Property added successfully!')
            
            return redirect('reviews:property_detail', property_id=property_obj.id)
    else:
        form = PropertyWithReviewForm()
    
    context = {
        'form': form,
    }
    return render(request, 'reviews/create_property.html', context)


def register(request):
    """User registration with email verification."""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Set user_type to 'user' by default for regular registrations
            # Staff users should be created through admin
            user.user_type = form.cleaned_data.get('user_type', 'user')
            user.email_verified = False  # Email not verified yet
            user.save()
            
            # Generate and send verification code
            verification = EmailVerification.generate_code(user)
            
            # Send verification email
            try:
                contact_email = getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)
                protocol = 'https' if request.is_secure() else 'http'
                domain = request.get_host()
                
                html_message = render_to_string(
                    'reviews/email_verification.html',
                    {
                        'user': user,
                        'code': verification.code,
                        'contact_email': contact_email,
                        'protocol': protocol,
                        'domain': domain,
                    }
                )
                plain_message = render_to_string(
                    'reviews/email_verification.txt',
                    {
                        'user': user,
                        'code': verification.code,
                        'contact_email': contact_email,
                        'protocol': protocol,
                        'domain': domain,
                    }
                )
                
                send_mail(
                    subject='Verify Your Email - Property Reviews',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                messages.success(request, f'Account created! Please check your email ({user.email}) for a verification code.')
                return redirect('reviews:verify_email', user_id=user.id)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send verification email: {e}")
                messages.error(request, 'Account created but failed to send verification email. Please contact support.')
                return redirect('reviews:verify_email', user_id=user.id)
    else:
        form = UserRegistrationForm()
        # Hide user_type field for regular registration (defaults to 'user')
        form.fields['user_type'].widget = forms.HiddenInput()
        form.fields['user_type'].initial = 'user'
    
    context = {
        'form': form,
    }
    return render(request, 'reviews/register.html', context)


def user_login(request):
    """User login."""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        username = None
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            # Check if user exists and is suspended BEFORE authentication
            try:
                user_obj = User.objects.get(username=username)
                if hasattr(user_obj, 'is_suspended') and user_obj.is_suspended:
                    messages.error(request, 'Your account has been suspended. Please contact support for assistance.')
                    form = AuthenticationForm()
                    context = {
                        'form': form,
                        'suspended_message': True,
                    }
                    return render(request, 'reviews/login.html', context)
            except User.DoesNotExist:
                pass  # User doesn't exist, continue with normal authentication
            
            user = authenticate(username=username, password=password)
            if user is not None:
                # Double-check if account is suspended (in case it was suspended between checks)
                if hasattr(user, 'is_suspended') and user.is_suspended:
                    messages.error(request, 'Your account has been suspended. Please contact support for assistance.')
                    form = AuthenticationForm()
                    context = {
                        'form': form,
                        'suspended_message': True,
                    }
                    return render(request, 'reviews/login.html', context)
                elif not user.is_active:
                    messages.error(request, 'Your account is inactive. Please contact support for assistance.')
                    form = AuthenticationForm()
                else:
                    login(request, user)
                    messages.success(request, f'Welcome back, {username}!')
                    next_url = request.GET.get('next', 'reviews:home')
                    return redirect(next_url)
    else:
        form = AuthenticationForm()
    
    context = {
        'form': form,
    }
    return render(request, 'reviews/login.html', context)


def property_detail(request, property_id):
    """View property details and reviews."""
    property_obj = get_object_or_404(Property, id=property_id)
    
    # Hide property if creator is suspended
    if property_obj.created_by and hasattr(property_obj.created_by, 'is_suspended') and property_obj.created_by.is_suspended:
        messages.error(request, 'This property is no longer available.')
        return redirect('reviews:all_properties')
    
    # Get sort parameter for reviews
    review_sort = request.GET.get('review_sort', 'newest')
    
    # Filter out reviews from suspended users
    # Handle cases where created_by might be None (deleted users) - show those
    all_reviews = property_obj.reviews.filter(
        Q(created_by__isnull=True) | Q(created_by__is_suspended=False)
    )
    
    # Apply sorting to reviews
    if review_sort == 'newest':
        all_reviews = all_reviews.order_by('-created_at')
    elif review_sort == 'oldest':
        all_reviews = all_reviews.order_by('created_at')
    elif review_sort == 'rating_high':
        all_reviews = all_reviews.order_by('-rating', '-created_at')
    elif review_sort == 'rating_low':
        all_reviews = all_reviews.order_by('rating', '-created_at')
    else:
        all_reviews = all_reviews.order_by('-created_at')
    
    # Check if user has already reviewed this property
    user_review = None
    if request.user.is_authenticated:
        user_review = property_obj.reviews.filter(created_by=request.user).first()
    
    # Calculate statistics (only from non-suspended users)
    review_count = all_reviews.count()
    avg_rating = all_reviews.aggregate(Avg('rating'))['rating__avg']
    
    # Rating distribution (only from non-suspended users)
    rating_dist = {}
    for rating_val, rating_label in Review.RATING_CHOICES:
        count = all_reviews.filter(rating=rating_val).count()
        rating_dist[rating_val] = {
            'label': rating_label,
            'count': count,
            'percentage': (count / review_count * 100) if review_count > 0 else 0
        }
    
    # Handle reply submission (for non-AJAX requests, keep redirect behavior)
    if request.method == 'POST' and 'reply_to_review' in request.POST and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Require authentication to submit replies
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to reply to comments. Please log in or create an account.')
            return redirect('reviews:login')
        
        review_id = request.POST.get('reply_to_review')
        try:
            parent_review = Review.objects.get(id=review_id, property=property_obj)
            reply_form = ReplyForm(request.POST)
            if reply_form.is_valid():
                # Spam prevention for replies
                if request.user.is_authenticated:
                    # Rate limiting: Check if user posted too many replies recently (max 5 per hour)
                    one_hour_ago = timezone.now() - timedelta(hours=1)
                    recent_replies_count = Reply.objects.filter(
                        created_by=request.user,
                        created_at__gte=one_hour_ago
                    ).count()
                    
                    if recent_replies_count >= 5:
                        messages.error(
                            request,
                            'You have submitted too many replies recently. Please wait before submitting another reply.'
                        )
                        return redirect('reviews:property_detail', property_id=property_id)
                
                reply = reply_form.save(commit=False)
                reply.review = parent_review
                reply.created_by = request.user if request.user.is_authenticated else None
                
                # Check if user wants to post anonymously
                post_as = request.POST.get('post_as')
                use_real_name = request.POST.get('use_real_name') == 'on' or reply_form.cleaned_data.get('use_real_name', False)
                
                if post_as == 'anonymous' or not use_real_name:
                    reply.author_name = ''
                    reply.is_anonymous = True
                else:
                    author_name = reply_form.cleaned_data.get('author_name', '').strip()
                    if not author_name:
                        if request.user.is_authenticated:
                            author_name = request.user.get_full_name() or request.user.username
                    reply.author_name = author_name
                    reply.is_anonymous = False
                
                reply.is_approved = True
                reply.save()
                # Notify review author or parent reply author
                notify_reply_posted(reply)
                messages.success(request, 'Your reply has been posted!')
                return redirect('reviews:property_detail', property_id=property_id)
            else:
                messages.error(request, 'Please correct the errors in your reply.')
        except Review.DoesNotExist:
            messages.error(request, 'The review you are trying to reply to does not exist.')
    
    # Handle review submission
    if request.method == 'POST' and 'submit_review' in request.POST:
        # Require authentication to submit reviews
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to submit a comment. Please log in or create an account.')
            return redirect('reviews:login')
        
        form = ReviewForm(request.POST)
        if form.is_valid():
            # Spam and duplicate prevention
            if request.user.is_authenticated:
                # Check for duplicate review (same user, same property)
                existing_review = Review.objects.filter(
                    property=property_obj,
                    created_by=request.user
                ).first()
                
                if existing_review:
                    messages.error(
                        request,
                        'You have already submitted a review for this property. You can edit or delete your existing review.'
                    )
                    return redirect('reviews:property_detail', property_id=property_id)
                
                # Rate limiting: Check if user posted too many reviews recently (max 3 per hour)
                one_hour_ago = timezone.now() - timedelta(hours=1)
                recent_reviews_count = Review.objects.filter(
                    created_by=request.user,
                    created_at__gte=one_hour_ago
                ).count()
                
                if recent_reviews_count >= 3:
                    messages.error(
                        request,
                        'You have submitted too many reviews recently. Please wait before submitting another review.'
                    )
                    return redirect('reviews:property_detail', property_id=property_id)
                
                # Check for duplicate content (similar content within last 24 hours)
                one_day_ago = timezone.now() - timedelta(days=1)
                content = form.cleaned_data.get('content', '').strip()
                if content:
                    similar_reviews = Review.objects.filter(
                        created_by=request.user,
                        content__icontains=content[:50],  # Check first 50 chars
                        created_at__gte=one_day_ago
                    ).exclude(property=property_obj)
                    
                    if similar_reviews.exists():
                        messages.error(
                            request,
                            'You have recently submitted a similar review. Please write a unique review for this property.'
                        )
                        return redirect('reviews:property_detail', property_id=property_id)
            
            review = form.save(commit=False)
            review.property = property_obj
            review.created_by = request.user  # User is authenticated at this point
            
            # Auto-generate title from content if not provided
            if not review.title:
                content = form.cleaned_data.get('content', '').strip()
                if content:
                    # Use first 50 characters of content as title
                    review.title = content[:50] + ('...' if len(content) > 50 else '')
                else:
                    review.title = 'Comment'
            
            # Check if user wants to post anonymously
            post_as = request.POST.get('post_as')
            # Checkbox fields: if checked, value is 'on' in POST, and True in cleaned_data
            # If unchecked, not in POST, and False in cleaned_data
            use_real_name = request.POST.get('use_real_name') == 'on' or form.cleaned_data.get('use_real_name', False)
            
            # If post_as checkbox is checked (value='anonymous'), post anonymously
            # Otherwise use real name if use_real_name is checked
            if post_as == 'anonymous' or not use_real_name:
                # Post anonymously
                review.author_name = ''
                review.is_anonymous = True
            else:
                # Use real name (from form or user's name)
                author_name = form.cleaned_data.get('author_name', '').strip()
                if not author_name:
                    # Fallback to user's full name or username
                    if request.user.is_authenticated:
                        author_name = request.user.get_full_name() or request.user.username
                review.author_name = author_name
                review.is_anonymous = False
            
            # Auto-approve comments (no approval needed)
            review.is_approved = True
            review.save()
            # Notify property owner
            notify_review_posted(review)
            messages.success(
                request,
                'Thank you for your comment! It has been posted and is now visible.'
            )
            return redirect('reviews:property_detail', property_id=property_id)
    else:
        form = ReviewForm()
    
    # Pre-fill the form with current user's name if authenticated
    if request.user.is_authenticated:
        form.fields['author_name'].initial = request.user.get_full_name() or request.user.username
        form.fields['use_real_name'].initial = True
    else:
        form.fields['use_real_name'].initial = False
    
    # Preload replies and owner responses for all reviews
    # Get top-level replies (replies without parent_reply)
    def get_replies_with_children(review):
        """Get all top-level replies with their nested children, excluding suspended users."""
        # Filter out replies from suspended users
        # Handle cases where created_by might be None (deleted users) - show those
        top_level_replies = review.replies.filter(
            parent_reply__isnull=True
        ).filter(
            Q(created_by__isnull=True) | Q(created_by__is_suspended=False)
        ).order_by('created_at')
        
        return list(top_level_replies)
    
    reviews_with_replies = []
    for review in all_reviews:
        top_level_replies = get_replies_with_children(review)
        owner_response = getattr(review, 'owner_response', None) if hasattr(review, 'owner_response') else None
        
        # Get vote counts and user's vote
        helpful_count = ReviewVote.objects.filter(review=review, vote_type='helpful').count()
        not_helpful_count = ReviewVote.objects.filter(review=review, vote_type='not_helpful').count()
        user_vote = None
        if request.user.is_authenticated:
            user_vote_obj = ReviewVote.objects.filter(review=review, user=request.user).first()
            user_vote = user_vote_obj.vote_type if user_vote_obj else None
        
        reviews_with_replies.append({
            'review': review,
            'replies': top_level_replies,
            'reply_form': ReplyForm(),  # Create a form for each review
            'owner_response': owner_response,
            'helpful_count': helpful_count,
            'not_helpful_count': not_helpful_count,
            'user_vote': user_vote,
        })
    
    # Get property images
    property_images = property_obj.images.all()
    
    context = {
        'property': property_obj,
        'reviews_with_replies': reviews_with_replies,
        'review_count': review_count,
        'avg_rating': avg_rating,
        'rating_dist': rating_dist,
        'form': form,
        'user_review': user_review,
        'review_sort': review_sort,
        'property_images': property_images,
    }
    return render(request, 'reviews/property_detail.html', context)


@login_required
def edit_review(request, review_id):
    """Edit a review."""
    review = get_object_or_404(Review, id=review_id)
    
    # Strict check: Only the user who created the review can edit it
    if not review.created_by or review.created_by != request.user:
        messages.error(request, 'You do not have permission to edit this review. Only the review creator can edit their own review.')
        return redirect('reviews:property_detail', property_id=review.property.id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            # Check if user wants to post anonymously
            post_as = request.POST.get('post_as')
            # Checkbox fields are only in cleaned_data if they were checked
            # So we need to check both POST data and cleaned_data
            use_real_name = request.POST.get('use_real_name') == 'on' or form.cleaned_data.get('use_real_name', False)
            
            review = form.save(commit=False)
            
            if post_as == 'anonymous' or not use_real_name:
                review.author_name = ''
                review.is_anonymous = True
            else:
                author_name = form.cleaned_data.get('author_name', '').strip()
                if not author_name:
                    author_name = request.user.get_full_name() or request.user.username
                review.author_name = author_name
                review.is_anonymous = False
            
            # Keep approval status when edited (comments stay approved)
            review.is_approved = True
            review.save()
            
            messages.success(request, 'Your comment has been updated successfully.')
            return redirect('reviews:property_detail', property_id=review.property.id)
    else:
        form = ReviewForm(instance=review)
        # Pre-fill the form with current values
        if review.author_name and not review.is_anonymous:
            form.fields['use_real_name'].initial = True
            form.fields['author_name'].initial = review.author_name
        else:
            form.fields['use_real_name'].initial = False
            form.fields['author_name'].initial = ''
    
    context = {
        'form': form,
        'review': review,
        'property': review.property,
    }
    return render(request, 'reviews/edit_review.html', context)


@login_required
def delete_review(request, review_id):
    """Delete a review."""
    review = get_object_or_404(Review, id=review_id)
    property_id = review.property.id
    
    # Strict check: Only the user who created the review can delete it
    if not review.created_by or review.created_by != request.user:
        messages.error(request, 'You do not have permission to delete this review. Only the review creator can delete their own review.')
        return redirect('reviews:property_detail', property_id=property_id)
    
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Your review has been deleted.')
        return redirect('reviews:property_detail', property_id=property_id)
    
    context = {
        'review': review,
        'property': review.property,
    }
    return render(request, 'reviews/delete_review.html', context)


@login_required
def delete_property(request, property_id):
    """Delete a property and all associated images from Cloudinary."""
    property_obj = get_object_or_404(Property, id=property_id)
    
    # Strict check: Only the user who created the property can delete it
    if not property_obj.created_by or property_obj.created_by != request.user:
        messages.error(request, 'You do not have permission to delete this property. Only the property owner can delete their own property.')
        return redirect('reviews:user_profile')
    
    if request.method == 'POST':
        # Delete images from Cloudinary before deleting the property
        try:
            import cloudinary
            import cloudinary.uploader
            
            # Import the helper function from models
            from .models import get_cloudinary_public_id
            
            # Delete all PropertyImage objects from Cloudinary
            property_images = property_obj.images.all()
            deleted_count = 0
            for prop_image in property_images:
                try:
                    public_id = get_cloudinary_public_id(prop_image.image)
                    if public_id:
                        # Delete from Cloudinary
                        result = cloudinary.uploader.destroy(public_id, invalidate=True)
                        if result.get('result') == 'ok':
                            deleted_count += 1
                        else:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Cloudinary deletion failed for {public_id}: {result.get('result')}")
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Could not extract public_id for PropertyImage {prop_image.id}")
                except Exception as e:
                    # Log error but continue with deletion
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to delete image {prop_image.id} from Cloudinary: {e}")
            
            # Delete the main property image if it exists
            if property_obj.image:
                try:
                    public_id = get_cloudinary_public_id(property_obj.image)
                    if public_id:
                        # Delete from Cloudinary
                        result = cloudinary.uploader.destroy(public_id, invalidate=True)
                        if result.get('result') == 'ok':
                            deleted_count += 1
                        else:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Cloudinary deletion failed for main image {public_id}: {result.get('result')}")
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning("Could not extract public_id for main property image")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to delete main property image from Cloudinary: {e}")
            
            # Log deletion summary
            if deleted_count > 0:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Successfully deleted {deleted_count} image(s) from Cloudinary for property {property_obj.id}")
        except ImportError:
            # Cloudinary not available, skip deletion
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Cloudinary not available, skipping image deletion")
        except Exception as e:
            # Log error but continue with property deletion
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting images from Cloudinary: {e}")
        
        # Delete the property (this will cascade delete PropertyImage objects)
        property_obj.delete()
        messages.success(request, 'Your property has been deleted successfully.')
        return redirect('reviews:user_profile')
    
    context = {
        'property': property_obj,
    }
    return render(request, 'reviews/delete_property.html', context)


@login_required
def edit_profile(request):
    """Edit profile information page."""
    user = request.user
    
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('reviews:edit_profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        profile_form = UserProfileForm(instance=user)
    
    context = {
        'user': user,
        'profile_form': profile_form,
    }
    return render(request, 'reviews/edit_profile.html', context)


def verify_email(request, user_id):
    """Email verification page where users enter their 6-digit code."""
    user = get_object_or_404(User, id=user_id)
    
    if user.email_verified:
        messages.info(request, 'Your email has already been verified.')
        return redirect('reviews:login')
    
    error_message = None
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        
        if not code or len(code) != 6:
            error_message = 'Please enter a valid 6-digit code.'
        else:
            # Find a valid verification code for this user
            verification = EmailVerification.objects.filter(
                user=user,
                code=code,
                is_used=False
            ).order_by('-created_at').first()
            
            if verification and verification.is_valid():
                # Mark as used
                verification.is_used = True
                verification.save()
                
                # Verify user's email
                user.email_verified = True
                user.save()
                
                messages.success(request, 'Email verified successfully! You can now log in.')
                return redirect('reviews:login')
            else:
                error_message = 'Invalid or expired verification code. Please check your email or request a new code.'
    
    context = {
        'user': user,
        'error_message': error_message,
    }
    return render(request, 'reviews/verify_email.html', context)


def resend_verification_code(request, user_id):
    """Resend verification code to user's email."""
    user = get_object_or_404(User, id=user_id)
    
    if user.email_verified:
        messages.info(request, 'Your email has already been verified.')
        return redirect('reviews:login')
    
    try:
        # Generate new verification code
        verification = EmailVerification.generate_code(user)
        
        # Send verification email
        contact_email = getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        
        html_message = render_to_string(
            'reviews/email_verification.html',
            {
                'user': user,
                'code': verification.code,
                'contact_email': contact_email,
                'protocol': protocol,
                'domain': domain,
            }
        )
        plain_message = render_to_string(
            'reviews/email_verification.txt',
            {
                'user': user,
                'code': verification.code,
                'contact_email': contact_email,
                'protocol': protocol,
                'domain': domain,
            }
        )
        
        send_mail(
            subject='Verify Your Email - Property Reviews',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        messages.success(request, f'A new verification code has been sent to {user.email}')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to resend verification email: {e}")
        messages.error(request, 'Failed to send verification email. Please try again later.')
    
    return redirect('reviews:verify_email', user_id=user.id)


@login_required
def get_cloudinary_upload_signature(request):
    """Generate Cloudinary upload signature for direct client-side uploads."""
    try:
        import cloudinary
        from cloudinary import api
        
        cloud_name = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME', '')
        api_key = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('API_KEY', '')
        api_secret = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('API_SECRET', '')
        
        if not all([cloud_name, api_key, api_secret]):
            return JsonResponse({'error': 'Cloudinary not configured'}, status=500)
        
        # Generate timestamp
        timestamp = str(int(time.time()))
        
        # Create upload preset parameters
        params = {
            'timestamp': timestamp,
            'folder': 'properties',
        }
        
        # Generate signature
        params_to_sign = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature_string = params_to_sign + api_secret
        signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()
        
        return JsonResponse({
            'cloud_name': cloud_name,
            'api_key': api_key,
            'timestamp': timestamp,
            'signature': signature,
            'folder': 'properties',
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate Cloudinary signature: {e}")
        return JsonResponse({'error': 'Failed to generate upload signature'}, status=500)


@login_required
def change_password(request):
    """Change password page."""
    user = request.user
    
    if request.method == 'POST':
        password_form = CustomPasswordChangeForm(user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)  # Important: keeps user logged in
            messages.success(request, 'Your password has been changed successfully!')
            return redirect('reviews:change_password')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        password_form = CustomPasswordChangeForm(user)
    
    context = {
        'user': user,
        'password_form': password_form,
    }
    return render(request, 'reviews/change_password.html', context)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Custom password reset confirm view that sends email notification after successful reset."""
    template_name = 'reviews/password_reset_confirm.html'
    success_url = reverse_lazy('reviews:password_reset_complete')
    
    def form_valid(self, form):
        """Override to send email notification after password reset."""
        # Save the user before sending email (password is already set)
        user = form.save()
        
        # Send password change notification email
        try:
            contact_email = getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)
            
            # Render email templates
            html_message = render_to_string(
                'reviews/password_changed_email.html',
                {
                    'user': user,
                    'contact_email': contact_email,
                }
            )
            plain_message = render_to_string(
                'reviews/password_changed_email.txt',
                {
                    'user': user,
                    'contact_email': contact_email,
                }
            )
            
            # Send email
            send_mail(
                subject='Your Password Has Been Changed - Property Reviews',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            # Log error but don't fail the password reset
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send password change notification email: {e}")
        
        # Call parent's form_valid to complete the reset
        return super().form_valid(form)


def user_profile(request):
    """User profile page displaying user's properties and reviews."""
    user = request.user
    
    # Get all properties created by the user
    user_properties = Property.objects.filter(created_by=user).annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-created_at')
    
    # Get all reviews created by the user
    user_reviews = Review.objects.filter(created_by=user).select_related('property').order_by('-created_at')[:10]
    
    context = {
        'user': user,
        'user_properties': user_properties,
        'user_reviews': user_reviews,
        'properties_count': user_properties.count(),
        'reviews_count': Review.objects.filter(created_by=user).count(),
    }
    return render(request, 'reviews/user_profile.html', context)


@require_http_methods(["POST"])
def submit_reply_api(request):
    """API endpoint for submitting replies via AJAX."""
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'You must be logged in to post a reply.'
        }, status=401)
    
    try:
        review_id = request.POST.get('review_id') or request.POST.get('reply_to_review')
        parent_reply_id = request.POST.get('parent_reply_id')  # For nested replies
        
        if not review_id:
            return JsonResponse({
                'success': False,
                'error': 'Review ID is required.'
            }, status=400)
        
        parent_review = Review.objects.get(id=review_id)
        
        # If parent_reply_id is provided, validate it
        parent_reply = None
        if parent_reply_id:
            try:
                parent_reply = Reply.objects.get(id=parent_reply_id, review=parent_review)
            except Reply.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Parent reply not found.'
                }, status=404)
        
        # Spam prevention for replies
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_replies_count = Reply.objects.filter(
            created_by=request.user,
            created_at__gte=one_hour_ago
        ).count()
        
        if recent_replies_count >= 5:
            return JsonResponse({
                'success': False,
                'error': 'You have submitted too many replies recently. Please wait before submitting another reply.'
            }, status=429)
        
        reply_form = ReplyForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.review = parent_review
            reply.parent_reply = parent_reply  # Set parent if replying to a reply
            reply.created_by = request.user
            
            # Check if user wants to post anonymously
            post_as = request.POST.get('post_as')
            use_real_name = request.POST.get('use_real_name') == 'on' or reply_form.cleaned_data.get('use_real_name', False)
            
            if post_as == 'anonymous' or not use_real_name:
                reply.author_name = ''
                reply.is_anonymous = True
            else:
                author_name = reply_form.cleaned_data.get('author_name', '').strip()
                if not author_name:
                    author_name = request.user.get_full_name() or request.user.username
                reply.author_name = author_name
                reply.is_anonymous = False
            
            reply.is_approved = True
            reply.save()
            
            # Notify review author or parent reply author
            notify_reply_posted(reply)
            
            # Return JSON response with reply data
            return JsonResponse({
                'success': True,
                'message': 'Your reply has been posted!',
                'reply': {
                    'id': reply.id,
                    'content': reply.content,
                    'author_name': reply.author_name if not reply.is_anonymous else 'Anonymous',
                    'is_anonymous': reply.is_anonymous,
                    'created_at': reply.created_at.strftime('%b %d, %Y'),
                    'created_at_iso': reply.created_at.isoformat(),
                    'parent_reply_id': reply.parent_reply.id if reply.parent_reply else None,
                    'is_nested': reply.is_nested_reply,
                }
            })
        else:
            # Return form errors
            errors = {}
            for field, error_list in reply_form.errors.items():
                errors[field] = error_list[0] if error_list else 'Invalid value'
            
            return JsonResponse({
                'success': False,
                'error': 'Please correct the errors in your reply.',
                'errors': errors
            }, status=400)
            
    except Review.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'The review you are trying to reply to does not exist.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while posting your reply. Please try again.'
        }, status=500)


@login_required
def edit_reply(request, reply_id):
    """Edit a reply."""
    reply = get_object_or_404(Reply, id=reply_id)
    
    # Strict check: Only the user who created the reply can edit it
    if not reply.created_by or reply.created_by != request.user:
        messages.error(request, 'You do not have permission to edit this reply.')
        return redirect('reviews:property_detail', property_id=reply.review.property.id)
    
    if request.method == 'POST':
        form = ReplyForm(request.POST, instance=reply)
        if form.is_valid():
            # Check if user wants to post anonymously
            post_as = request.POST.get('post_as')
            use_real_name = request.POST.get('use_real_name') == 'on' or form.cleaned_data.get('use_real_name', False)
            
            reply = form.save(commit=False)
            
            if post_as == 'anonymous' or not use_real_name:
                reply.author_name = ''
                reply.is_anonymous = True
            else:
                author_name = form.cleaned_data.get('author_name', '').strip()
                if not author_name:
                    author_name = request.user.get_full_name() or request.user.username
                reply.author_name = author_name
                reply.is_anonymous = False
            
            reply.is_approved = True
            reply.save()
            
            messages.success(request, 'Your reply has been updated successfully.')
            return redirect('reviews:property_detail', property_id=reply.review.property.id)
    else:
        form = ReplyForm(instance=reply)
        # Pre-fill the form with current values
        if reply.author_name and not reply.is_anonymous:
            form.fields['use_real_name'].initial = True
            form.fields['author_name'].initial = reply.author_name
        else:
            form.fields['use_real_name'].initial = False
            form.fields['author_name'].initial = ''
    
    context = {
        'form': form,
        'reply': reply,
        'review': reply.review,
    }
    return render(request, 'reviews/edit_reply.html', context)


@login_required
def delete_reply(request, reply_id):
    """Delete a reply."""
    reply = get_object_or_404(Reply, id=reply_id)
    property_id = reply.review.property.id
    
    # Strict check: Only the user who created the reply can delete it
    if not reply.created_by or reply.created_by != request.user:
        messages.error(request, 'You do not have permission to delete this reply.')
        return redirect('reviews:property_detail', property_id=property_id)
    
    if request.method == 'POST':
        reply.delete()
        messages.success(request, 'Your reply has been deleted.')
        return redirect('reviews:property_detail', property_id=property_id)
    
    context = {
        'reply': reply,
        'review': reply.review,
        'property': reply.review.property,
    }
    return render(request, 'reviews/delete_reply.html', context)


@require_http_methods(["POST"])
@login_required
def edit_reply_api(request, reply_id):
    """API endpoint for editing replies via AJAX."""
    try:
        reply = Reply.objects.get(id=reply_id)
        
        # Check permissions
        if not reply.created_by or reply.created_by != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to edit this reply.'
            }, status=403)
        
        reply_form = ReplyForm(request.POST, instance=reply)
        if reply_form.is_valid():
            # Check if user wants to post anonymously
            post_as = request.POST.get('post_as')
            use_real_name = request.POST.get('use_real_name') == 'on' or reply_form.cleaned_data.get('use_real_name', False)
            
            reply = reply_form.save(commit=False)
            
            if post_as == 'anonymous' or not use_real_name:
                reply.author_name = ''
                reply.is_anonymous = True
            else:
                author_name = reply_form.cleaned_data.get('author_name', '').strip()
                if not author_name:
                    author_name = request.user.get_full_name() or request.user.username
                reply.author_name = author_name
                reply.is_anonymous = False
            
            reply.is_approved = True
            reply.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Your reply has been updated successfully!',
                'reply': {
                    'id': reply.id,
                    'content': reply.content,
                    'author_name': reply.author_name if not reply.is_anonymous else 'Anonymous',
                    'is_anonymous': reply.is_anonymous,
                    'created_at': reply.created_at.strftime('%b %d, %Y'),
                    'updated_at': reply.updated_at.strftime('%b %d, %Y'),
                }
            })
        else:
            errors = {}
            for field, error_list in reply_form.errors.items():
                errors[field] = error_list[0] if error_list else 'Invalid value'
            
            return JsonResponse({
                'success': False,
                'error': 'Please correct the errors in your reply.',
                'errors': errors
            }, status=400)
            
    except Reply.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'The reply does not exist.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating your reply. Please try again.'
        }, status=500)


@require_http_methods(["POST"])
@login_required
def delete_reply_api(request, reply_id):
    """API endpoint for deleting replies via AJAX."""
    try:
        reply = Reply.objects.get(id=reply_id)
        
        # Check permissions
        if not reply.created_by or reply.created_by != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to delete this reply.'
            }, status=403)
        
        reply.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Your reply has been deleted successfully.'
        })
        
    except Reply.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'The reply does not exist.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while deleting your reply. Please try again.'
        }, status=500)


def report_review(request, review_id):
    """Report a review for violating terms."""
    review = get_object_or_404(Review, id=review_id)
    
    if request.method == 'POST':
        form = ReviewReportForm(request.POST)
        if form.is_valid():
            # Check if user already reported this review
            if request.user.is_authenticated:
                existing_report = ReviewReport.objects.filter(
                    review=review,
                    reported_by=request.user
                ).first()
                
                if existing_report:
                    messages.info(request, 'You have already reported this review. Our team will review it.')
                    return redirect('reviews:property_detail', property_id=review.property.id)
            
            report = form.save(commit=False)
            report.review = review
            report.reported_by = request.user if request.user.is_authenticated else None
            
            # Flag the review for moderation
            review.is_flagged = True
            review.flagged_reason = f"Reported: {report.get_reason_display()}"
            review.save()
            
            report.save()
            messages.success(
                request,
                'Thank you for your report. Our moderation team will review this review. '
                'The review has been flagged for review.'
            )
            return redirect('reviews:property_detail', property_id=review.property.id)
    else:
        form = ReviewReportForm()
    
    context = {
        'form': form,
        'review': review,
        'property': review.property,
    }
    return render(request, 'reviews/report_review.html', context)


@login_required
def respond_to_review(request, review_id):
    """Allow property owner to respond to a review."""
    review = get_object_or_404(Review, id=review_id)
    
    # Check if there's already a response
    if hasattr(review, 'owner_response'):
        messages.info(request, 'A response to this review already exists.')
        return redirect('reviews:property_detail', property_id=review.property.id)
    
    # Check if user created the property (property owner)
    if not review.property.created_by or review.property.created_by != request.user:
        messages.error(
            request,
            'Only the property owner can respond to reviews for their property.'
        )
        return redirect('reviews:property_detail', property_id=review.property.id)
    
    if request.method == 'POST':
        form = PropertyOwnerResponseForm(request.POST)
        if form.is_valid():
            response = form.save(commit=False)
            response.review = review
            response.created_by = request.user
            response.is_approved = True
            response.save()
            # Notify review author
            notify_owner_response(response)
            messages.success(request, 'Your response has been posted successfully.')
            return redirect('reviews:property_detail', property_id=review.property.id)
    else:
        form = PropertyOwnerResponseForm()
    
    context = {
        'form': form,
        'review': review,
        'property': review.property,
    }
    return render(request, 'reviews/respond_to_review.html', context)


@staff_required
def staff_dashboard(request):
    """Staff dashboard for managing reports and moderation."""
    # Statistics
    total_reports = ReviewReport.objects.count()
    unresolved_reports = ReviewReport.objects.filter(is_resolved=False).count()
    flagged_reviews = Review.objects.filter(is_flagged=True).count()
    total_properties = Property.objects.count()
    total_reviews = Review.objects.count()
    total_users = User.objects.count()
    
    # Recent reports
    recent_reports = ReviewReport.objects.filter(is_resolved=False).order_by('-created_at')[:10]
    
    # Recent flagged reviews
    recent_flagged = Review.objects.filter(is_flagged=True).order_by('-created_at')[:10]
    
    context = {
        'total_reports': total_reports,
        'unresolved_reports': unresolved_reports,
        'flagged_reviews': flagged_reviews,
        'total_properties': total_properties,
        'total_reviews': total_reviews,
        'total_users': total_users,
        'recent_reports': recent_reports,
        'recent_flagged': recent_flagged,
    }
    return render(request, 'reviews/staff_dashboard.html', context)


@staff_required
def staff_reports(request):
    """View all reports."""
    reports = ReviewReport.objects.all().order_by('-created_at')
    
    # Filtering
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'resolved':
        reports = reports.filter(is_resolved=True)
    elif status_filter == 'unresolved':
        reports = reports.filter(is_resolved=False)
    
    reason_filter = request.GET.get('reason', 'all')
    if reason_filter != 'all':
        reports = reports.filter(reason=reason_filter)
    
    context = {
        'reports': reports,
        'status_filter': status_filter,
        'reason_filter': reason_filter,
    }
    return render(request, 'reviews/staff_reports.html', context)


@staff_required
def staff_report_detail(request, report_id):
    """View details of a specific report."""
    report = get_object_or_404(ReviewReport, id=report_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'resolve':
            report.is_resolved = True
            report.resolved_by = request.user
            report.resolved_at = timezone.now()
            report.save()
            # Notify reporter
            notify_report_resolved(report)
            messages.success(request, 'Report marked as resolved.')
            return redirect('reviews:staff_reports')
        
        elif action == 'unresolve':
            report.is_resolved = False
            report.resolved_by = None
            report.resolved_at = None
            report.save()
            messages.success(request, 'Report marked as unresolved.')
            return redirect('reviews:staff_report_detail', report_id=report_id)
        
        elif action == 'delete_review':
            review = report.review
            property_id = review.property.id
            review.delete()
            messages.success(request, 'Review deleted successfully.')
            return redirect('reviews:staff_reports')
        
        elif action == 'unflag_review':
            review = report.review
            review.is_flagged = False
            review.flagged_reason = ''
            review.save()
            messages.success(request, 'Review unflagged.')
            return redirect('reviews:staff_report_detail', report_id=report_id)
    
    context = {
        'report': report,
    }
    return render(request, 'reviews/staff_report_detail.html', context)


@staff_required
def staff_flagged_reviews(request):
    """View all flagged reviews."""
    flagged_reviews = Review.objects.filter(is_flagged=True).order_by('-created_at')
    
    context = {
        'flagged_reviews': flagged_reviews,
    }
    return render(request, 'reviews/staff_flagged_reviews.html', context)


@staff_required
def staff_review_action(request, review_id):
    """Handle actions on reviews (approve, reject, unflag, delete)."""
    review = get_object_or_404(Review, id=review_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            review.is_approved = True
            review.is_flagged = False
            review.flagged_reason = ''
            review.save()
            messages.success(request, 'Review approved and unflagged.')
        
        elif action == 'reject':
            review.is_approved = False
            review.save()
            messages.success(request, 'Review rejected.')
        
        elif action == 'unflag':
            review.is_flagged = False
            review.flagged_reason = ''
            review.save()
            messages.success(request, 'Review unflagged.')
        
        elif action == 'delete':
            property_id = review.property.id
            review.delete()
            messages.success(request, 'Review deleted successfully.')
            return redirect('reviews:staff_flagged_reviews')
        
        return redirect('reviews:staff_flagged_reviews')
    
    return redirect('reviews:staff_flagged_reviews')


@staff_required
def staff_users(request):
    """View all users with search and filtering."""
    from django.core.paginator import Paginator
    
    users = User.objects.all().order_by('-date_joined')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Filtering
    user_type_filter = request.GET.get('user_type', 'all')
    if user_type_filter != 'all':
        users = users.filter(user_type=user_type_filter)
    
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    email_verified_filter = request.GET.get('email_verified', 'all')
    if email_verified_filter == 'verified':
        users = users.filter(email_verified=True)
    elif email_verified_filter == 'unverified':
        users = users.filter(email_verified=False)
    
    # Annotate with counts
    from django.db.models import Count
    users = users.annotate(
        properties_count=Count('properties_created'),
        reviews_count=Count('reviews_created')
    )
    
    # Pagination
    paginator = Paginator(users, 25)  # 25 users per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'users': page_obj,
        'user_type_filter': user_type_filter,
        'status_filter': status_filter,
        'email_verified_filter': email_verified_filter,
        'search_query': search_query,
    }
    return render(request, 'reviews/staff_users.html', context)


@staff_required
def staff_user_detail(request, user_id):
    """View detailed information about a specific user."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Get user statistics (even if user is suspended, show their content to staff)
    properties = Property.objects.filter(created_by=user_obj).order_by('-created_at')
    reviews = Review.objects.filter(created_by=user_obj).order_by('-created_at')
    replies = Reply.objects.filter(created_by=user_obj).order_by('-created_at')
    # Note: Staff can see suspended users' content in their detail view for moderation purposes
    
    context = {
        'user_obj': user_obj,
        'properties': properties[:10],  # Latest 10
        'reviews': reviews[:10],  # Latest 10
        'replies': replies[:10],  # Latest 10
        'total_properties': properties.count(),
        'total_reviews': reviews.count(),
        'total_replies': replies.count(),
    }
    return render(request, 'reviews/staff_user_detail.html', context)


@staff_required
def staff_user_edit(request, user_id):
    """Edit user information (limited fields only)."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Prevent staff from editing other staff members (optional security measure)
    if user_obj.user_type == 'staffs' and user_obj != request.user:
        messages.error(request, 'You cannot edit other staff members.')
        return redirect('reviews:staff_users')
    
    if request.method == 'POST':
        # Only allow editing specific fields (not basic info or password)
        user_obj.user_type = request.POST.get('user_type', user_obj.user_type)
        user_obj.is_active = request.POST.get('is_active') == 'on'
        user_obj.email_verified = request.POST.get('email_verified') == 'on'
        
        # Handle suspension (can only be done via toggle, but show status)
        # Note: Suspension should be done via the toggle_suspend endpoint
        
        user_obj.save()
        messages.success(request, f'User {user_obj.username} has been updated successfully.')
        return redirect('reviews:staff_user_detail', user_id=user_obj.id)
    
    context = {
        'user_obj': user_obj,
    }
    return render(request, 'reviews/staff_user_edit.html', context)


@staff_required
@require_POST
def staff_user_reset_password(request, user_id):
    """Generate a random 9-digit password and email it to the user."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Generate random 9-digit password
    import random
    new_password = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    
    # Set the new password
    user_obj.set_password(new_password)
    user_obj.save()
    
    # Send email with new password
    try:
        from django.contrib.sites.shortcuts import get_current_site
        current_site = get_current_site(request)
        protocol = 'https' if request.is_secure() else 'http'
        login_url = f"{protocol}://{current_site.domain}{reverse('reviews:login')}"
        
        subject = 'Your Password Has Been Reset - Property Reviews'
        html_message = render_to_string('reviews/password_reset_staff_email.html', {
            'user': user_obj,
            'new_password': new_password,
            'contact_email': getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL),
            'login_url': login_url,
        })
        plain_message = render_to_string('reviews/password_reset_staff_email.txt', {
            'user': user_obj,
            'new_password': new_password,
            'contact_email': getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL),
            'login_url': login_url,
        })
        
        # Send email to user
        email_sent = send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user_obj.email],  # Send to user's email address
            html_message=html_message,
            fail_silently=False,
        )
        
        if email_sent:
            messages.success(request, f'A new 9-digit password has been generated and sent to {user_obj.email}. The user should check their email inbox.')
        else:
            messages.warning(request, f'Password was reset, but email may not have been sent. Please verify email settings.')
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send password reset email to {user_obj.email}: {e}", exc_info=True)
        messages.error(request, f'Password was reset successfully, but failed to send email to {user_obj.email}. Error: {str(e)}. Please contact the user directly with the new password.')
    
    return redirect('reviews:staff_user_detail', user_id=user_obj.id)


@staff_required
@require_POST
def staff_user_toggle_suspend(request, user_id):
    """Toggle user account suspension."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Prevent staff from suspending themselves
    if user_obj == request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'You cannot suspend your own account.'}, status=400)
        messages.error(request, 'You cannot suspend your own account.')
        return redirect('reviews:staff_user_detail', user_id=user_obj.id)
    
    # Prevent staff from suspending other staff members
    if user_obj.user_type == 'staffs':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'You cannot suspend staff members.'}, status=400)
        messages.error(request, 'You cannot suspend staff members.')
        return redirect('reviews:staff_user_detail', user_id=user_obj.id)
    
    user_obj.is_suspended = not user_obj.is_suspended
    if user_obj.is_suspended:
        user_obj.suspended_at = timezone.now()
    else:
        user_obj.suspended_at = None
    user_obj.save()
    
    action = 'suspended' if user_obj.is_suspended else 'unsuspended'
    messages.success(request, f'User {user_obj.username} has been {action}.')
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_suspended': user_obj.is_suspended,
            'message': f'User {user_obj.username} has been {action}.'
        })
    else:
        # Regular form submission - redirect
        return redirect('reviews:staff_user_detail', user_id=user_obj.id)


@staff_required
def staff_user_delete(request, user_id):
    """Delete a user."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Prevent staff from deleting themselves or other staff members
    if user_obj == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('reviews:staff_users')
    
    if user_obj.user_type == 'staffs':
        messages.error(request, 'You cannot delete staff members.')
        return redirect('reviews:staff_users')
    
    if request.method == 'POST':
        username = user_obj.username
        user_obj.delete()
        messages.success(request, f'User {username} has been deleted successfully.')
        return redirect('reviews:staff_users')
    
    context = {
        'user_obj': user_obj,
    }
    return render(request, 'reviews/staff_user_delete.html', context)


@staff_required
@require_POST
def staff_user_toggle_active(request, user_id):
    """Toggle user active status."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Prevent staff from deactivating themselves
    if user_obj == request.user:
        return JsonResponse({'error': 'You cannot deactivate your own account.'}, status=400)
    
    user_obj.is_active = not user_obj.is_active
    user_obj.save()
    
    status = 'activated' if user_obj.is_active else 'deactivated'
    messages.success(request, f'User {user_obj.username} has been {status}.')
    
    return JsonResponse({
        'success': True,
        'is_active': user_obj.is_active,
        'message': f'User {user_obj.username} has been {status}.'
    })


@staff_required
@require_POST
def staff_user_change_type(request, user_id):
    """Change user type."""
    user_obj = get_object_or_404(User, id=user_id)
    
    # Prevent staff from changing their own type
    if user_obj == request.user:
        return JsonResponse({'error': 'You cannot change your own user type.'}, status=400)
    
    new_type = request.POST.get('user_type')
    if new_type not in ['user', 'staffs']:
        return JsonResponse({'error': 'Invalid user type.'}, status=400)
    
    user_obj.user_type = new_type
    user_obj.save()
    
    messages.success(request, f'User {user_obj.username} type has been changed to {user_obj.get_user_type_display()}.')
    
    return JsonResponse({
        'success': True,
        'user_type': user_obj.user_type,
        'user_type_display': user_obj.get_user_type_display(),
        'message': f'User type updated successfully.'
    })


@staff_required
def staff_properties(request):
    """View all properties with search and filtering."""
    from django.core.paginator import Paginator
    
    # Staff can see all properties, including from suspended users
    properties = Property.objects.all().order_by('-created_at')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        properties = properties.filter(
            Q(address__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(state__icontains=search_query) |
            Q(zip_code__icontains=search_query) |
            Q(created_by__username__icontains=search_query) |
            Q(created_by__email__icontains=search_query)
        )
    
    # Filtering
    property_type_filter = request.GET.get('property_type', 'all')
    if property_type_filter != 'all':
        properties = properties.filter(property_type=property_type_filter)
    
    state_filter = request.GET.get('state', 'all')
    if state_filter != 'all':
        properties = properties.filter(state=state_filter)
    
    # Annotate with counts
    properties = properties.annotate(
        reviews_count=Count('reviews')
    )
    
    # Pagination
    paginator = Paginator(properties, 25)  # 25 properties per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get unique states for filter dropdown
    unique_states = Property.objects.values_list('state', flat=True).distinct().order_by('state')
    
    # Get property type choices from the model field
    property_type_choices = Property._meta.get_field('property_type').choices
    
    context = {
        'properties': page_obj,
        'property_type_filter': property_type_filter,
        'state_filter': state_filter,
        'search_query': search_query,
        'unique_states': unique_states,
        'property_type_choices': property_type_choices,
    }
    return render(request, 'reviews/staff_properties.html', context)


@staff_required
def staff_property_delete(request, property_id):
    """Delete a property (staff can delete any property)."""
    property_obj = get_object_or_404(Property, id=property_id)
    
    if request.method == 'POST':
        # Delete images from Cloudinary before deleting the property
        try:
            import cloudinary
            import cloudinary.uploader
            
            # Import the helper function from models
            from .models import get_cloudinary_public_id
            
            # Delete all PropertyImage objects from Cloudinary
            property_images = property_obj.images.all()
            deleted_count = 0
            for prop_image in property_images:
                try:
                    public_id = get_cloudinary_public_id(prop_image.image)
                    if public_id:
                        # Delete from Cloudinary
                        result = cloudinary.uploader.destroy(public_id, invalidate=True)
                        if result.get('result') == 'ok':
                            deleted_count += 1
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error deleting property image from Cloudinary: {e}")
            
            # Delete main property image from Cloudinary
            try:
                public_id = get_cloudinary_public_id(property_obj.image)
                if public_id:
                    result = cloudinary.uploader.destroy(public_id, invalidate=True)
                    if result.get('result') == 'ok':
                        deleted_count += 1
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error deleting main property image from Cloudinary: {e}")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error during Cloudinary deletion: {e}")
        
        # Delete the property (this will trigger the signal to delete images)
        address = property_obj.full_address
        property_obj.delete()
        messages.success(request, f'Property "{address}" has been deleted successfully.')
        return redirect('reviews:staff_properties')
    
    context = {
        'property': property_obj,
    }
    return render(request, 'reviews/staff_property_delete.html', context)


@login_required
def notifications_center(request):
    """Display all notifications for the current user."""
    notifications = Notification.objects.filter(recipient=request.user)
    
    # Filter by read/unread status
    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_type == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Pagination (optional - show last 50)
    notifications = notifications[:50]
    
    context = {
        'notifications': notifications,
        'filter_type': filter_type,
        'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
    }
    return render(request, 'reviews/notifications_center.html', context)


@require_POST
@ensure_csrf_cookie
@login_required
def mark_notification_read_api(request, notification_id):
    """Mark a notification as read via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed.'}, status=405)
    
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read.'
        })
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found.'
        }, status=404)


@require_POST
@ensure_csrf_cookie
@login_required
def mark_all_notifications_read_api(request):
    """Mark all notifications as read via AJAX."""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({
        'success': True,
        'message': 'All notifications marked as read.'
    })


@login_required
def get_unread_notification_count_api(request):
    """Get the count of unread notifications."""
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({
        'count': count
    })


@require_POST
@ensure_csrf_cookie
@login_required
def vote_review_api(request, review_id):
    """Vote on a review (helpful or not helpful) via AJAX."""
    try:
        review = Review.objects.get(id=review_id)
        vote_type = request.POST.get('vote_type')
        
        if vote_type not in ['helpful', 'not_helpful']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid vote type.'
            }, status=400)
        
        # Check if user already voted
        existing_vote = ReviewVote.objects.filter(review=review, user=request.user).first()
        
        if existing_vote:
            # If voting the same way, remove the vote (toggle off)
            if existing_vote.vote_type == vote_type:
                existing_vote.delete()
                action = 'removed'
            else:
                # Change vote type
                existing_vote.vote_type = vote_type
                existing_vote.save()
                action = 'changed'
        else:
            # Create new vote
            ReviewVote.objects.create(
                review=review,
                user=request.user,
                vote_type=vote_type
            )
            action = 'added'
        
        # Get updated vote counts
        helpful_count = ReviewVote.objects.filter(review=review, vote_type='helpful').count()
        not_helpful_count = ReviewVote.objects.filter(review=review, vote_type='not_helpful').count()
        
        # Get user's current vote
        user_vote = ReviewVote.objects.filter(review=review, user=request.user).first()
        user_vote_type = user_vote.vote_type if user_vote else None
        
        return JsonResponse({
            'success': True,
            'action': action,
            'helpful_count': helpful_count,
            'not_helpful_count': not_helpful_count,
            'user_vote': user_vote_type,
            'message': f'Vote {action} successfully.'
        })
        
    except Review.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Review not found.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while processing your vote.'
        }, status=500)

