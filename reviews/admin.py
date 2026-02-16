from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Property, Review, Reply, ReviewReport, PropertyOwnerResponse, CustomUser, Notification, ReviewVote, PropertyImage

User = get_user_model()


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Admin interface for CustomUser model."""
    list_display = ['username', 'email', 'user_type', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['user_type', 'is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('User Type', {
            'fields': ('user_type',)
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('User Type', {
            'fields': ('user_type',)
        }),
    )


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['address', 'city', 'state', 'property_type', 'created_by', 'created_at', 'approved_reviews_count']
    list_filter = ['property_type', 'city', 'state', 'created_at']
    search_fields = ['address', 'city', 'state', 'zip_code']
    readonly_fields = ['created_at', 'updated_at']
    fields = ['image', 'address', 'city', 'state', 'zip_code', 'property_type', 'created_by', 'created_at', 'updated_at']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['title', 'property', 'rating', 'author_display', 'created_by', 'is_approved', 'is_flagged', 'created_at']
    list_filter = ['is_approved', 'is_flagged', 'rating', 'is_anonymous', 'created_at']
    search_fields = ['title', 'content', 'author_name', 'property__address', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_reviews', 'reject_reviews']

    fieldsets = (
        ('Review Information', {
            'fields': ('property', 'rating', 'title', 'content', 'pros_cons')
        }),
        ('Living Period', {
            'fields': ('date_lived_from', 'date_lived_to')
        }),
        ('Author Information', {
            'fields': ('created_by', 'author_name', 'is_anonymous')
        }),
        ('Moderation', {
            'fields': ('is_approved', 'is_flagged', 'flagged_reason'),
            'description': 'Comments are automatically approved. Flag for review if violations are reported.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def author_display(self, obj):
        if obj.is_anonymous or not obj.author_name:
            return "Anonymous"
        return obj.author_name
    author_display.short_description = 'Author'

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} review(s) approved.")
    approve_reviews.short_description = "Approve selected reviews"

    def reject_reviews(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f"{queryset.count()} review(s) rejected.")
    reject_reviews.short_description = "Reject selected reviews"
    
    actions = ['approve_reviews', 'reject_reviews', 'flag_for_review']

    def flag_for_review(self, request, queryset):
        """Flag reviews for moderation."""
        queryset.update(is_flagged=True)
        self.message_user(request, f"{queryset.count()} review(s) flagged for moderation.")
    flag_for_review.short_description = "Flag selected reviews for moderation"


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ['review', 'author_display', 'parent_reply', 'created_by', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'is_anonymous', 'created_at']
    search_fields = ['content', 'author_name', 'review__property__address', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Reply Information', {
            'fields': ('review', 'parent_reply', 'content')
        }),
        ('Author Information', {
            'fields': ('author_name', 'is_anonymous', 'created_by')
        }),
        ('Moderation', {
            'fields': ('is_approved',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def author_display(self, obj):
        if obj.is_anonymous or not obj.author_name:
            return "Anonymous"
        return obj.author_name
    author_display.short_description = 'Author'


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ['review', 'reason', 'reported_by', 'is_resolved', 'created_at']
    list_filter = ['reason', 'is_resolved', 'created_at']
    search_fields = ['review__content', 'description', 'reported_by__username']
    readonly_fields = ['created_at']
    actions = ['mark_resolved', 'mark_unresolved']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('review', 'reported_by', 'reason', 'description')
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_by', 'resolved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def mark_resolved(self, request, queryset):
        """Mark reports as resolved."""
        from django.utils import timezone
        queryset.update(is_resolved=True, resolved_by=request.user, resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} report(s) marked as resolved.")
    mark_resolved.short_description = "Mark selected reports as resolved"
    
    def mark_unresolved(self, request, queryset):
        """Mark reports as unresolved."""
        queryset.update(is_resolved=False, resolved_by=None, resolved_at=None)
        self.message_user(request, f"{queryset.count()} report(s) marked as unresolved.")
    mark_unresolved.short_description = "Mark selected reports as unresolved"


@admin.register(PropertyOwnerResponse)
class PropertyOwnerResponseAdmin(admin.ModelAdmin):
    list_display = ['review', 'owner_name', 'created_by', 'is_approved', 'is_flagged', 'created_at']
    list_filter = ['is_approved', 'is_flagged', 'created_at']
    search_fields = ['content', 'owner_name', 'review__property__address', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Response Information', {
            'fields': ('review', 'content', 'owner_name', 'created_by')
        }),
        ('Moderation', {
            'fields': ('is_approved', 'is_flagged')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'recipient__username']
    readonly_fields = ['created_at']
    actions = ['mark_as_read', 'mark_as_unread']
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('recipient', 'notification_type', 'title', 'message', 'is_read')
        }),
        ('Related Content', {
            'fields': ('property', 'review', 'reply')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def mark_as_read(self, request, queryset):
        """Mark notifications as read."""
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} notification(s) marked as read.")
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        """Mark notifications as unread."""
        queryset.update(is_read=False)
        self.message_user(request, f"{queryset.count()} notification(s) marked as unread.")
    mark_as_unread.short_description = "Mark selected notifications as unread"


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ['review', 'user', 'vote_type', 'created_at']
    list_filter = ['vote_type', 'created_at']
    search_fields = ['review__content', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Vote Information', {
            'fields': ('review', 'user', 'vote_type')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ['property', 'order', 'image', 'created_at']
    list_filter = ['created_at']
    search_fields = ['property__address', 'property__city']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Image Information', {
            'fields': ('property', 'image', 'order')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

