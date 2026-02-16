# Property Reviews Platform

A Django MVP for a property review platform where users can search for properties and post reviews. Reviews are opinion-based, require admin approval, and support anonymous submissions.

## Features

- **User Authentication**: Register, login, and logout functionality
- **Property Management**: Users can post new properties (login required)
- **Property Search**: Search for properties by address, city, state, or zip code
- **All Properties View**: Browse all properties in a grid layout
- **Review System**: Post reviews with ratings (1-5 stars) and detailed feedback
- **Admin Approval**: All reviews require admin approval before being visible publicly
- **Anonymous Reviews**: Users can post reviews anonymously or with their name
- **Rating Statistics**: View average ratings and rating distributions for properties
- **Mobile-Friendly**: Fully responsive design using Tailwind CSS that works on all devices
- **Modern UI**: Clean, intuitive interface

## Setup

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Create a superuser for admin access:
```bash
python manage.py createsuperuser
```

5. Configure Cloudinary for image storage (optional but recommended):
   - Sign up at https://cloudinary.com/
   - Set environment variables:
     ```bash
     CLOUDINARY_CLOUD_NAME=your_cloud_name
     CLOUDINARY_API_KEY=your_api_key
     CLOUDINARY_API_SECRET=your_api_secret
     ```
   - See `CLOUDINARY_SETUP.md` for detailed instructions
   - If Cloudinary is not configured, images will be stored locally

6. Install HTTPS dependencies (optional, for HTTPS development):
```bash
pip install django-extensions werkzeug pyOpenSSL
```

Or install all dependencies including HTTPS and Cloudinary:
```bash
pip install -r requirements.txt
```

6. Run the development server:

**HTTP (default):**
```bash
python manage.py runserver
```

**HTTPS (recommended for development):**
```bash
# First, generate SSL certificates (one-time setup):
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"

# Then run with HTTPS:
python3 manage.py runserver_plus --cert-file cert.pem --key-file key.pem

# Or use the provided script:
./run_https.sh
```

7. Access the application:
- **HTTP**: http://127.0.0.1:8000/
- **HTTPS**: https://localhost:8000/ or https://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/admin/ or https://localhost:8000/admin/

**Note**: With self-signed certificates, your browser will show a security warning. Click "Advanced" and "Proceed to localhost" to continue.

## Database

The project is configured to use SQLite by default for development. To use PostgreSQL:

1. Update `property_reviews/settings.py` to uncomment the PostgreSQL database configuration
2. Set environment variables:
   - `DB_NAME`: Database name
   - `DB_USER`: Database user
   - `DB_PASSWORD`: Database password
   - `DB_HOST`: Database host (default: localhost)
   - `DB_PORT`: Database port (default: 5432)

## Usage

### User Registration and Login

1. Click "Sign Up" in the navigation bar
2. Fill in username, email, and password
3. After registration, you'll be redirected to login
4. Once logged in, you can post properties and reviews

### Adding Properties

**Option 1: Through the Website (Recommended)**
1. Log in to your account
2. Click "Add Property" in the navigation or home page
3. Fill in the property details (address, city, state, zip code, property type)
4. Submit the form

**Option 2: Through Admin Panel**
Properties can also be added through the Django admin panel at `/admin/`.

### Browsing Properties

- **Search**: Use the search bar on the home page to find specific properties
- **View All**: Click "View All Properties" to see all properties in a grid layout

### Reviewing Properties

1. Search for or browse to find a property
2. Click on a property to view details and existing reviews
3. Scroll down to the review form (or view it in the sidebar on desktop)
4. Fill out the review form with rating, title, and content (minimum 50 characters)
5. Optionally provide your name, or leave blank for anonymous review
6. Submit the review (it will be pending admin approval)

### Approving Reviews

1. Log in to the admin panel at `/admin/`
2. Navigate to "Reviews" section
3. Select reviews to approve and use the "Approve selected reviews" action
4. Approved reviews will become visible on the property detail page

## Legal Considerations

- All reviews are opinion-based to ensure legal safety
- Reviews require admin approval before publication
- Users can post anonymously
- No rental listings or payment features are included

## Project Structure

```
rental/
├── property_reviews/      # Django project settings
├── reviews/              # Main app
│   ├── models.py        # Property and Review models
│   ├── views.py         # View functions
│   ├── forms.py         # Form definitions
│   ├── admin.py         # Admin configuration
│   └── urls.py          # URL routing
├── templates/           # HTML templates
│   ├── base.html       # Base template
│   └── reviews/        # App-specific templates
├── manage.py           # Django management script
└── requirements.txt    # Python dependencies
```

## Development Notes

- The minimum review length is 50 characters
- Reviews are filtered to show only approved ones
- Rating system uses 1-5 stars
- Search is case-insensitive and matches across address, city, state, and zip code

# rent
