from django.db import models
from django.core.validators import MinLengthValidator
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from datetime import timedelta
import random

# Cloudinary import with fallback
try:
    from cloudinary.models import CloudinaryField
except ImportError:
    # Fallback to regular ImageField if Cloudinary is not installed
    CloudinaryField = models.ImageField


class CustomUser(AbstractUser):
    """Custom user model with user type field."""
    USER_TYPE_CHOICES = (
        ('user', 'Users'),
        ('staffs', 'Staffs'),
    )
    user_type = models.CharField(
        max_length=10, 
        choices=USER_TYPE_CHOICES,
        default='user',
        help_text="Type of user account"
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="Designates whether the user's email has been verified."
    )
    is_suspended = models.BooleanField(
        default=False,
        help_text="Designates whether this user account has been suspended by staff."
    )
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when the account was suspended."
    )

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

    @property
    def is_staff_user(self):
        """Check if user is a staff member."""
        return self.user_type == 'staffs'


class EmailVerification(models.Model):
    """Model to store email verification codes."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_verifications')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Email Verification'
        verbose_name_plural = 'Email Verifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.code}"

    def is_valid(self):
        """Check if the verification code is still valid."""
        return not self.is_used and timezone.now() <= self.expires_at

    @classmethod
    def generate_code(cls, user):
        """Generate a new 6-digit verification code for a user."""
        # Invalidate all previous unused codes for this user
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        
        # Generate a new 6-digit code
        code = str(random.randint(100000, 999999))
        
        # Create verification record (expires in 30 minutes)
        expires_at = timezone.now() + timedelta(minutes=30)
        verification = cls.objects.create(
            user=user,
            code=code,
            expires_at=expires_at
        )
        
        return verification


class Property(models.Model):
    """Represents a property that can be reviewed."""
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    property_type = models.CharField(
        max_length=50,
        choices=[
            ('apartment', 'Apartment'),
            ('house', 'House'),
            ('condo', 'Condo'),
            ('townhouse', 'Townhouse'),
            ('other', 'Other'),
        ],
        default='apartment'
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Describe what happened at this property"
    )
    image = CloudinaryField(
        'image',
        blank=True,
        null=True,
        folder='properties',
        help_text="Upload a photo of the property"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='properties_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Properties'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.address}, {self.city}, {self.state}"

    @property
    def full_address(self):
        return f"{self.address}, {self.city}, {self.state} {self.zip_code}"

    @property
    def approved_reviews_count(self):
        return self.reviews.count()

    @property
    def average_rating(self):
        all_reviews = self.reviews.all()
        if all_reviews.exists():
            ratings = all_reviews.values_list('rating', flat=True)
            return sum(ratings) / len(ratings)
        return None
    
    @property
    def primary_image(self):
        """Get the primary image (first image or legacy image field)."""
        # First try to get from PropertyImage
        property_image = self.images.first()
        if property_image:
            return property_image.image
        # Fallback to legacy image field
        return self.image if self.image else None


class PropertyImage(models.Model):
    """Multiple images for a property (maximum 6 per property)."""
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images',
        help_text="Property this image belongs to"
    )
    image = CloudinaryField(
        'image',
        folder='properties',
        help_text="Property image"
    )
    order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Property Image'
        verbose_name_plural = 'Property Images'
    
    def __str__(self):
        return f"Image for {self.property.address} (Order: {self.order})"


def get_cloudinary_public_id(cloudinary_field):
    """Extract public_id from CloudinaryField value."""
    if not cloudinary_field:
        return None
    
    try:
        # Method 1: Try to access public_id attribute directly
        if hasattr(cloudinary_field, 'public_id') and cloudinary_field.public_id:
            return cloudinary_field.public_id
        
        # Method 2: Try to get it from the field's internal representation
        field_value = str(cloudinary_field)
        
        # If it's a full Cloudinary URL, extract public_id from it
        if 'cloudinary.com' in field_value:
            # URL format: https://res.cloudinary.com/cloud_name/image/upload/v1234567890/properties/filename.jpg
            # or: https://res.cloudinary.com/cloud_name/image/upload/properties/filename.jpg
            try:
                # Split by /upload/ to get the path part
                if '/upload/' in field_value:
                    path_part = field_value.split('/upload/')[1]
                    # Remove version prefix if present (v1234567890/)
                    if path_part.startswith('v') and '/' in path_part:
                        path_part = path_part.split('/', 1)[1]
                    # Remove file extension
                    if '.' in path_part:
                        path_part = path_part.rsplit('.', 1)[0]
                    return path_part
            except Exception:
                pass
        
        # Method 3: If it's already a public_id format (properties/filename or just filename)
        # Remove file extension if present
        if '.' in field_value:
            if '/' in field_value:
                # Format: "properties/filename.jpg"
                parts = field_value.rsplit('/', 1)
                if len(parts) == 2:
                    folder, filename = parts
                    filename_no_ext = filename.rsplit('.', 1)[0]
                    return f"{folder}/{filename_no_ext}"
            else:
                # Format: "filename.jpg"
                return field_value.rsplit('.', 1)[0]
        
        # Method 4: Return as-is if no extension
        return field_value
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error extracting public_id from CloudinaryField: {e}, value: {cloudinary_field}")
        return None


@receiver(pre_delete, sender=PropertyImage)
def delete_property_image_from_cloudinary(sender, instance, **kwargs):
    """Delete image from Cloudinary when PropertyImage is deleted."""
    if instance.image:
        try:
            import cloudinary
            import cloudinary.uploader
            
            public_id = get_cloudinary_public_id(instance.image)
            
            if public_id:
                try:
                    result = cloudinary.uploader.destroy(public_id, invalidate=True)
                    if result.get('result') == 'ok':
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"Successfully deleted PropertyImage {instance.id} ({public_id}) from Cloudinary")
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to delete PropertyImage {instance.id} ({public_id}) from Cloudinary: {result.get('result')}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error deleting PropertyImage {instance.id} ({public_id}) from Cloudinary: {e}")
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not extract public_id for PropertyImage {instance.id}, image value: {instance.image}")
        except ImportError:
            # Cloudinary not available
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Cloudinary not available, skipping image deletion")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in delete_property_image_from_cloudinary signal: {e}")


@receiver(pre_delete, sender=Property)
def delete_property_main_image_from_cloudinary(sender, instance, **kwargs):
    """Delete main property image from Cloudinary when Property is deleted."""
    if instance.image:
        try:
            import cloudinary
            import cloudinary.uploader
            
            public_id = get_cloudinary_public_id(instance.image)
            
            if public_id:
                try:
                    result = cloudinary.uploader.destroy(public_id, invalidate=True)
                    if result.get('result') == 'ok':
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"Successfully deleted main property image ({public_id}) from Cloudinary for Property {instance.id}")
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to delete main property image ({public_id}) from Cloudinary: {result.get('result')}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error deleting main property image ({public_id}) from Cloudinary: {e}")
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not extract public_id for main property image, Property {instance.id}, image value: {instance.image}")
        except ImportError:
            # Cloudinary not available
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Cloudinary not available, skipping image deletion")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in delete_property_main_image_from_cloudinary signal: {e}")


class Review(models.Model):
    """Represents a review for a property."""
    RATING_CHOICES = [
        (1, 'Very Poor'),
        (2, 'Poor'),
        (3, 'Fair'),
        (4, 'Good'),
        (5, 'Excellent'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews_created',
        help_text="User who created this review (for edit/delete permissions)"
    )
    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200, blank=True, default='')
    content = models.TextField(
        blank=True,
        null=True,
        validators=[MinLengthValidator(50, message="Review must be at least 50 characters if provided.")]
    )
    pros_cons = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Optional: List pros and cons of the property"
    )
    date_lived_from = models.DateField(
        blank=True,
        null=True,
        help_text="Optional: When did you start living here?"
    )
    date_lived_to = models.DateField(
        blank=True,
        null=True,
        help_text="Optional: When did you stop living here? (leave blank if still living there)"
    )
    author_name = models.CharField(max_length=100, blank=True, help_text="Optional - leave blank for anonymous")
    is_anonymous = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True, help_text="Comments are automatically approved and visible")
    is_flagged = models.BooleanField(default=False, help_text="Flagged for moderation review")
    flagged_reason = models.TextField(blank=True, null=True, help_text="Reason for flagging")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        author = self.author_name if self.author_name else "Anonymous"
        return f"Review by {author} for {self.property.address}"

    def save(self, *args, **kwargs):
        # If author_name is provided, mark as not anonymous
        if self.author_name:
            self.is_anonymous = False
        super().save(*args, **kwargs)


class ActiveReplyManager(models.Manager):
    """Manager that filters out replies from suspended users."""
    def get_queryset(self):
        return super().get_queryset().filter(
            Q(created_by__isnull=True) | Q(created_by__is_suspended=False)
        )


class Reply(models.Model):
    """Represents a reply to a review/comment or another reply."""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='replies')
    parent_reply = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='child_replies',
        help_text="Parent reply if this is a reply to a reply"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies_created',
        help_text="User who created this reply"
    )
    content = models.TextField(
        validators=[MinLengthValidator(10, message="Reply must be at least 10 characters.")]
    )
    author_name = models.CharField(max_length=100, blank=True, help_text="Optional - leave blank for anonymous")
    is_anonymous = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True, help_text="Replies are automatically approved and visible")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Managers
    objects = models.Manager()  # Default manager (includes all)
    active = ActiveReplyManager()  # Manager that filters suspended users

    class Meta:
        verbose_name_plural = 'Replies'
        ordering = ['created_at']

    def __str__(self):
        author = self.author_name if self.author_name else "Anonymous"
        if self.parent_reply:
            return f"Reply by {author} to reply #{self.parent_reply.id}"
        return f"Reply by {author} to review #{self.review.id}"

    def save(self, *args, **kwargs):
        # If author_name is provided, mark as not anonymous
        if self.author_name:
            self.is_anonymous = False
        super().save(*args, **kwargs)
    
    @property
    def is_nested_reply(self):
        """Check if this is a reply to another reply."""
        return self.parent_reply is not None
    
    @property
    def active_child_replies(self):
        """Get child replies excluding suspended users."""
        return self.child_replies.filter(
            Q(created_by__isnull=True) | Q(created_by__is_suspended=False)
        ).order_by('created_at')


class ReviewReport(models.Model):
    """Report submitted for a review that may violate terms."""
    REPORT_REASONS = [
        ('personal_attack', 'Personal Attack or Insult'),
        ('off_topic', 'Not About the Property'),
        ('false_information', 'False or Misleading Information'),
        ('spam', 'Spam or Advertisement'),
        ('harassment', 'Harassment or Bullying'),
        ('other', 'Other Violation'),
    ]
    
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_submitted'
    )
    reason = models.CharField(max_length=50, choices=REPORT_REASONS)
    description = models.TextField(
        max_length=500,
        help_text="Please provide details about why you are reporting this review"
    )
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_resolved',
        related_query_name='resolved_report'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [['review', 'reported_by']]  # One report per user per review

    def __str__(self):
        return f"Report on Review #{self.review.id} - {self.get_reason_display()}"


class PropertyOwnerResponse(models.Model):
    """Response from property owner/landlord to a review."""
    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name='owner_response',
        help_text="One response per review"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='property_responses',
        help_text="Property owner/landlord who created this response"
    )
    content = models.TextField(
        validators=[MinLengthValidator(20, message="Response must be at least 20 characters.")],
        help_text="Professional response to the review"
    )
    owner_name = models.CharField(
        max_length=100,
        help_text="Name or title of the property owner/manager"
    )
    is_approved = models.BooleanField(default=True, help_text="Responses are automatically approved")
    is_flagged = models.BooleanField(default=False, help_text="Flagged for moderation review")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Response to Review #{self.review.id} by {self.owner_name}"


class Notification(models.Model):
    """Notifications for users about activities related to their content."""
    NOTIFICATION_TYPES = [
        ('review_posted', 'New Review Posted'),
        ('reply_posted', 'New Reply to Your Review'),
        ('reply_to_reply', 'Reply to Your Reply'),
        ('owner_response', 'Property Owner Responded'),
        ('report_resolved', 'Report Resolved'),
        ('property_reviewed', 'Your Property Was Reviewed'),
    ]
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="User who will receive this notification"
    )
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # Related objects (optional, for linking to content)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    reply = models.ForeignKey(
        Reply,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.recipient.username}"
    
    def get_url(self):
        """Get the URL to the related content."""
        if self.property:
            if self.review:
                # Return URL with anchor to specific review
                return reverse('reviews:property_detail', args=[self.property.id]) + f'#review_{self.review.id}'
            return reverse('reviews:property_detail', args=[self.property.id])
        return "#"


class ReviewVote(models.Model):
    """Tracks helpful/not helpful votes on reviews."""
    VOTE_CHOICES = [
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
    ]
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='votes',
        help_text="Review being voted on"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_votes',
        help_text="User who voted"
    )
    vote_type = models.CharField(
        max_length=20,
        choices=VOTE_CHOICES,
        help_text="Type of vote"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['review', 'user']]  # One vote per user per review
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['review', 'vote_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} voted {self.get_vote_type_display()} on Review #{self.review.id}"
