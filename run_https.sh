#!/bin/bash
# Script to run Django development server with HTTPS

# Check if certificates exist, if not generate them
if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    echo "Generating SSL certificates..."
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
    echo "Certificates generated!"
fi

# Run the server with HTTPS
echo "Starting Django development server with HTTPS..."
echo "Access your site at: https://localhost:8000"
python3 manage.py runserver_plus --cert-file cert.pem --key-file key.pem
