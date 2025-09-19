# Use the official Python image from the Docker Hub
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install git (needed by gitpython and possibly for pip installs)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install the dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# install Gunicorn
RUN pip install gunicorn==23.0.0

# Copy the entire project into the container
COPY . /app/

# Collect static files
ARG DJANGO_SECRET_KEY_BUILD
RUN DJANGO_SECRET_KEY=secret-key-for-build python manage.py collectstatic --noinput

# Copy the entrypoint script
COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Expose the port the app runs on
EXPOSE 8000

# Default command
CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]