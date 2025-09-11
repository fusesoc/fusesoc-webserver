#!/bin/sh

# Run database migrations
echo "==> Running django migrations..."
python manage.py migrate

# Initialze the database from GitHub repository.
echo "==> Initialize database..."
python manage.py init_db

# Collect static files (if needed)
echo "==> Collecting static files..."
python manage.py collectstatic --noinput

# Execute the command passed to the container
echo "==> Starting FuseSoC Package Directory Server..."
exec "$@"