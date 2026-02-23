from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .views import CustomPasswordResetConfirmView

app_name = 'reviews'

urlpatterns = [
    path('', views.home, name='home'),
    path('properties/', views.all_properties, name='all_properties'),
    path('property/<int:property_id>/', views.property_detail, name='property_detail'),
    path('api/property/<int:property_id>/reviews/', views.property_reviews_page_api, name='property_reviews_page_api'),
    path('property/create/', views.create_property, name='create_property'),
    path('property/<int:property_id>/delete/', views.delete_property, name='delete_property'),
    path('review/<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('review/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('register/', views.register, name='register'),
    path('verify-email/<int:user_id>/', views.verify_email, name='verify_email'),
    path('resend-verification/<int:user_id>/', views.resend_verification_code, name='resend_verification_code'),
    path('login/', views.user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Password Reset
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='reviews/password_reset.html',
             email_template_name='reviews/password_reset_email.txt',
             html_email_template_name='reviews/password_reset_email.html',
             subject_template_name='reviews/password_reset_subject.txt',
             success_url=reverse_lazy('reviews:password_reset_done')
         ), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='reviews/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         CustomPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='reviews/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('api/review/', views.submit_review_api, name='submit_review_api'),
    path('api/reply/', views.submit_reply_api, name='submit_reply_api'),
    path('reply/<int:reply_id>/edit/', views.edit_reply, name='edit_reply'),
    path('reply/<int:reply_id>/delete/', views.delete_reply, name='delete_reply'),
    path('api/reply/<int:reply_id>/edit/', views.edit_reply_api, name='edit_reply_api'),
    path('api/reply/<int:reply_id>/delete/', views.delete_reply_api, name='delete_reply_api'),
    path('legal/terms/', views.terms_of_service, name='terms_of_service'),
    path('legal/privacy/', views.privacy_policy, name='privacy_policy'),
    path('legal/safety/', views.safety_guidelines, name='safety_guidelines'),
    path('review/<int:review_id>/report/', views.report_review, name='report_review'),
    path('review/<int:review_id>/respond/', views.respond_to_review, name='respond_to_review'),
    # Staff routes
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/reports/', views.staff_reports, name='staff_reports'),
    path('staff/reports/<int:report_id>/', views.staff_report_detail, name='staff_report_detail'),
    path('staff/flagged/', views.staff_flagged_reviews, name='staff_flagged_reviews'),
    path('staff/review/<int:review_id>/action/', views.staff_review_action, name='staff_review_action'),
    path('staff/users/', views.staff_users, name='staff_users'),
    path('staff/users/<int:user_id>/', views.staff_user_detail, name='staff_user_detail'),
    path('staff/users/<int:user_id>/edit/', views.staff_user_edit, name='staff_user_edit'),
    path('staff/users/<int:user_id>/delete/', views.staff_user_delete, name='staff_user_delete'),
    path('staff/users/<int:user_id>/toggle-active/', views.staff_user_toggle_active, name='staff_user_toggle_active'),
    path('staff/users/<int:user_id>/change-type/', views.staff_user_change_type, name='staff_user_change_type'),
    path('staff/users/<int:user_id>/reset-password/', views.staff_user_reset_password, name='staff_user_reset_password'),
    path('staff/users/<int:user_id>/toggle-suspend/', views.staff_user_toggle_suspend, name='staff_user_toggle_suspend'),
    path('staff/properties/', views.staff_properties, name='staff_properties'),
    path('staff/properties/<int:property_id>/delete/', views.staff_property_delete, name='staff_property_delete'),
    # Notifications
    path('notifications/', views.notifications_center, name='notifications_center'),
    path('api/notifications/mark-read/<int:notification_id>/', views.mark_notification_read_api, name='mark_notification_read_api'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read_api, name='mark_all_notifications_read_api'),
    path('api/notifications/count/', views.get_unread_notification_count_api, name='get_unread_notification_count_api'),
    # Review Voting
    path('api/review/<int:review_id>/vote/', views.vote_review_api, name='vote_review_api'),
    # Cloudinary Upload
    path('api/cloudinary/signature/', views.get_cloudinary_upload_signature, name='get_cloudinary_upload_signature'),
]

