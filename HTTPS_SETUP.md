# HTTPS Development Server Setup

## Installation

1. Install the required packages:
```bash
pip install django-extensions werkzeug pyOpenSSL
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

## Generate SSL Certificates

You have two options:

### Option 1: Use mkcert (Recommended - Creates trusted local certificates)

1. Install mkcert:
   - macOS: `brew install mkcert`
   - Linux: Follow instructions at https://github.com/FiloSottile/mkcert
   - Windows: Download from https://github.com/FiloSottile/mkcert/releases

2. Install the local CA:
```bash
mkcert -install
```

3. Generate certificates:
```bash
mkcert localhost 127.0.0.1 ::1
```

This creates `localhost+2.pem` and `localhost+2-key.pem` files.

### Option 2: Use OpenSSL (Self-signed certificate)

Run this command in your project root:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

## Running the Server with HTTPS

### Using django-extensions (with mkcert certificates):

```bash
python manage.py runserver_plus --cert-file localhost+2.pem --key-file localhost+2-key.pem
```

### Using django-extensions (with OpenSSL certificates):

```bash
python manage.py runserver_plus --cert-file cert.pem --key-file key.pem
```

### Using django-extensions (auto-generate certificates):

```bash
python manage.py runserver_plus --cert-file cert.pem
```

This will automatically generate a self-signed certificate.

## Access Your Site

After starting the server, access it at:
- **https://localhost:8000**
- **https://127.0.0.1:8000**

**Note**: With self-signed certificates, your browser will show a security warning. Click "Advanced" and "Proceed to localhost" to continue.

## Quick Start Script

Create a file `run_https.sh` (or `run_https.bat` on Windows) with:

```bash
#!/bin/bash
python manage.py runserver_plus --cert-file cert.pem --key-file key.pem
```

Make it executable:
```bash
chmod +x run_https.sh
```

Then run:
```bash
./run_https.sh
```
