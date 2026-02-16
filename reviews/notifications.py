"""Helper functions for creating notifications."""
from django.db import transaction
from .models import Notification, Review, Reply, PropertyOwnerResponse


def create_notification(recipient, notification_type, title, message, property=None, review=None, reply=None):
    """Create a notification for a user."""
    if not recipient or recipient.is_anonymous:
        return None
    
    # Don't notify users about their own actions
    if review and review.created_by == recipient:
        return None
    if reply and reply.created_by == recipient:
        return None
    
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        property=property,
        review=review,
        reply=reply
    )
    return notification


def notify_review_posted(review):
    """Notify property owner when a new review is posted."""
    if not review.property or not review.property.created_by:
        return
    
    property_obj = review.property
    property_owner = property_obj.created_by
    
    # Don't notify if the review author is the property owner
    if review.created_by == property_owner:
        return
    
    author_name = review.author_name if review.author_name else "Anonymous"
    create_notification(
        recipient=property_owner,
        notification_type='property_reviewed',
        title=f'New Review on Your Property',
        message=f'{author_name} posted a {review.rating}-star review on {property_obj.address}.',
        property=property_obj,
        review=review
    )


def notify_reply_posted(reply):
    """Notify review author when someone replies to their review."""
    if not reply.review or not reply.review.created_by:
        return
    
    review = reply.review
    review_author = review.created_by
    
    # Don't notify if replying to own review
    if reply.created_by == review_author:
        return
    
    author_name = reply.author_name if reply.author_name else "Anonymous"
    
    if reply.parent_reply:
        # This is a reply to a reply
        parent_reply_author = reply.parent_reply.created_by
        if parent_reply_author and parent_reply_author != reply.created_by:
            create_notification(
                recipient=parent_reply_author,
                notification_type='reply_to_reply',
                title=f'Reply to Your Comment',
                message=f'{author_name} replied to your comment on {review.property.address}.',
                property=review.property,
                review=review,
                reply=reply
            )
    else:
        # This is a reply to a review
        create_notification(
            recipient=review_author,
            notification_type='reply_posted',
            title=f'New Reply to Your Review',
            message=f'{author_name} replied to your review on {review.property.address}.',
            property=review.property,
            review=review,
            reply=reply
        )


def notify_owner_response(owner_response):
    """Notify review author when property owner responds to their review."""
    if not owner_response.review or not owner_response.review.created_by:
        return
    
    review = owner_response.review
    review_author = review.created_by
    
    create_notification(
        recipient=review_author,
        notification_type='owner_response',
        title=f'Property Owner Responded',
        message=f'The property owner responded to your review on {review.property.address}.',
        property=review.property,
        review=review
    )


def notify_report_resolved(report):
    """Notify reporter when their report is resolved."""
    if not report.reported_by:
        return
    
    create_notification(
        recipient=report.reported_by,
        notification_type='report_resolved',
        title=f'Report Resolved',
        message=f'Your report on a review has been reviewed and resolved.',
        review=report.review
    )

