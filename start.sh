#!/bin/bash
# Startup script: Start web server immediately using pre-built data
# Data is populated during Docker build phase for fast cold starts

echo "=== Starting web server ==="
exec gunicorn dashboard:app --bind 0.0.0.0:5000
