from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import Property, Review, Reply, ReviewReport, PropertyOwnerResponse, CustomUser

User = get_user_model()


class PropertySearchForm(forms.Form):
    """Form for searching and filtering properties."""
    PROPERTY_TYPE_CHOICES = [
        ('', 'All Types'),
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('condo', 'Condo'),
        ('townhouse', 'Townhouse'),
        ('other', 'Other'),
    ]
    
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search by address, city, or zip code...'
        })
    )
    property_type = forms.ChoiceField(
        required=False,
        choices=PROPERTY_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    state = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'State (e.g., CA, NY)'
        })
    )
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'City'
        })
    )
    min_rating = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Any Rating'),
            ('1', '1+ Stars'),
            ('2', '2+ Stars'),
            ('3', '3+ Stars'),
            ('4', '4+ Stars'),
            ('5', '5 Stars'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('rating_high', 'Highest Rated'),
            ('rating_low', 'Lowest Rated'),
            ('most_reviews', 'Most Reviews'),
            ('least_reviews', 'Least Reviews'),
        ],
        initial='newest',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )


class ReviewForm(forms.ModelForm):
    """Form for submitting a review."""
    use_real_name = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        })
    )
    author_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Your name (optional - leave blank for anonymous)'
        }),
        help_text="Leave blank to post anonymously"
    )

    class Meta:
        model = Review
        fields = ['rating', 'content', 'pros_cons', 'date_lived_from', 'date_lived_to', 'author_name']
        widgets = {
            'rating': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 6,
                'placeholder': 'Share your experience (minimum 50 characters). Remember: comments should be based on your personal opinion and experience.'
            }),
            'pros_cons': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 4,
                'placeholder': 'Optional: List pros and cons'
            }),
            'date_lived_from': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
            'date_lived_to': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].label = 'Overall Rating'
        self.fields['content'].label = 'Your Review'
    
    def clean_content(self):
        """Validate content to prevent personal attacks and ensure property-focused reviews."""
        content = self.cleaned_data.get('content', '').strip().lower()
        
        if not content:
            return self.cleaned_data.get('content', '')
        
        # List of common personal attack words/phrases (basic list - can be expanded)
        personal_attack_indicators = [
            'stupid', 'idiot', 'moron', 'loser', 'jerk', 'asshole', 'bastard',
            'hate you', 'you are', 'you\'re a', 'you suck', 'kill yourself',
            'you should die', 'you deserve', 'fuck you', 'damn you'
        ]
        
        # Check for personal attack patterns
        for indicator in personal_attack_indicators:
            if indicator in content:
                raise forms.ValidationError(
                    "Reviews must focus on the property, not personal attacks. "
                    "Please describe your experience with the property itself, not individuals."
                )
        
        # Check if content is too focused on personal attacks (contains many personal pronouns)
        # This is a simple heuristic - can be improved
        personal_pronouns = ['you', 'your', 'you\'re', 'you\'ve', 'you\'ll']
        pronoun_count = sum(content.count(pronoun) for pronoun in personal_pronouns)
        
        # If there are too many "you" references, it might be a personal attack
        if pronoun_count > 5 and len(content) < 200:
            raise forms.ValidationError(
                "Please focus your review on the property and your experience, "
                "not on personal attacks or addressing individuals directly."
            )
        
        return self.cleaned_data.get('content', '')


class PropertyForm(forms.ModelForm):
    """Form for creating a new property."""
    
    class Meta:
        model = Property
        fields = ['address', 'city', 'state', 'zip_code', 'property_type', 'description', 'image']
        widgets = {
            'address': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Street address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'State'
            }),
            'zip_code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Zip code'
            }),
            'property_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 6,
                'placeholder': 'Describe what happened at this property (minimum 50 characters if provided)'
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
        }


class PropertyWithReviewForm(forms.Form):
    """Combined form for creating a property with an initial review."""
    # Property fields
    address = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Street address'
        })
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'City'
        })
    )
    state = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'State'
        })
    )
    zip_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Zip code'
        })
    )
    property_type = forms.ChoiceField(
        choices=Property._meta.get_field('property_type').choices,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'rows': 6,
            'placeholder': 'Describe what happened at this property (minimum 50 characters if provided)'
        })
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
            'accept': 'image/*'
        })
    )
    
    # Review fields
    review_title = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'e.g., "Constant water problems"'
        })
    )
    review_content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'rows': 6,
            'placeholder': 'Share your experience (minimum 50 characters if provided)'
        })
    )
    rating = forms.ChoiceField(
        choices=Review.RATING_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    pros_cons = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'rows': 4,
            'placeholder': 'Optional: List pros and cons (e.g., Pros: Great location, Cons: Noisy neighbors)'
        })
    )
    date_lived_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date'
        })
    )
    date_lived_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'type': 'date'
        })
    )
    use_real_name = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        })
    )
    author_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Your name'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        description = cleaned_data.get('description', '').strip()
        review_content = cleaned_data.get('review_content', '').strip()
        rating = cleaned_data.get('rating')
        
        # Validate description if provided
        if description and len(description) < 50:
            raise forms.ValidationError("Property description must be at least 50 characters if provided.")
        
        # Validate review content length if provided (but it's optional)
        if review_content and len(review_content) < 50:
                raise forms.ValidationError("Comment content must be at least 50 characters.")
        
        return cleaned_data


class UserRegistrationForm(UserCreationForm):
    """Form for user registration."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Email address'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Username'
        })
    )
    accept_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        }),
        label='I agree to the Terms of Service and Privacy Policy'
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Confirm password'
        })
    )

    user_type = forms.ChoiceField(
        choices=CustomUser.USER_TYPE_CHOICES,
        initial='user',
        widget=forms.HiddenInput(),  # Hidden by default, shown only in admin
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'user_type']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove help text for password fields
        for fieldname in ['username', 'password1', 'password2']:
            self.fields[fieldname].help_text = None
    
    def clean_accept_terms(self):
        """Validate that terms are accepted."""
        accept_terms = self.cleaned_data.get('accept_terms')
        if not accept_terms:
            raise forms.ValidationError(
                "You must agree to the Terms of Service and Privacy Policy to create an account."
            )
        return accept_terms


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile information."""
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Email address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Last name'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with Tailwind styling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            })


class ReviewReportForm(forms.ModelForm):
    """Form for reporting a review."""
    
    class Meta:
        model = ReviewReport
        fields = ['reason', 'description']
        widgets = {
            'reason': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 4,
                'placeholder': 'Please provide specific details about why you are reporting this review...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reason'].label = 'Reason for Reporting'
        self.fields['description'].label = 'Additional Details'


class PropertyOwnerResponseForm(forms.ModelForm):
    """Form for property owner to respond to a review."""
    
    class Meta:
        model = PropertyOwnerResponse
        fields = ['content', 'owner_name']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 6,
                'placeholder': 'Provide a professional response to this review. Focus on addressing concerns constructively...'
            }),
            'owner_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Your name or property management company name'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = 'Your Response'
        self.fields['owner_name'].label = 'Your Name / Company Name'
    
    def clean_content(self):
        """Validate response content to prevent personal attacks."""
        content = self.cleaned_data.get('content', '').strip().lower()
        
        if not content:
            return self.cleaned_data.get('content', '')
        
        # Check for personal attack indicators
        personal_attack_indicators = [
            'stupid', 'idiot', 'moron', 'loser', 'jerk', 'liar', 'you are lying',
            'you\'re wrong', 'you don\'t know', 'you\'re a', 'you suck'
        ]
        
        for indicator in personal_attack_indicators:
            if indicator in content:
                raise forms.ValidationError(
                    "Responses must be professional and constructive. "
                    "Please address concerns respectfully without personal attacks."
                )
        
        return self.cleaned_data.get('content', '')


class ReplyForm(forms.ModelForm):
    """Form for replying to a review."""
    use_real_name = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        })
    )
    author_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm',
            'placeholder': 'Your name (optional - leave blank for anonymous)'
        }),
        help_text="Leave blank to post anonymously"
    )

    class Meta:
        model = Reply
        fields = ['content', 'author_name']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm',
                'rows': 3,
                'placeholder': 'Write your reply (minimum 10 characters)...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = 'Your Reply'
        if 'instance' in kwargs and kwargs['instance']:
            reply = kwargs['instance']
            self.fields['use_real_name'].initial = not reply.is_anonymous
            self.fields['author_name'].initial = reply.author_name if not reply.is_anonymous else ''

