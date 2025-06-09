# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by Playwright and potentially other libraries
# The specific dependencies might vary based on the base image (slim vs full)
# Using --with-deps attempts to install browser dependencies too.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Add any other system dependencies needed by your Python packages
    # Example: build-essential if packages need compilation
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
# This command downloads browser binaries into the container
# Run it after pip install playwright
RUN playwright install --with-deps

# Copy the rest of the backend application code into the container
COPY . .

# Make port specified in config available to the world outside this container
# Use an ARG to make the port configurable at build time if needed,
# but typically set by the runtime environment or docker-compose.
EXPOSE 8000

# Define environment variable (can be overridden)
ENV PYTHONPATH=/app
ENV BACKEND_PORT=8000

# Create the default sandbox directory within the image
# Ensure it's owned by the user the container will run as (if not root)
RUN mkdir -p /app/maity_sandbox
# Example: If running as non-root user 'appuser'
# RUN chown appuser:appuser /app/maity_sandbox

# Command to run the application using Uvicorn
# Use the standard port 8000 unless BACKEND_PORT is set differently
# Use "main:app" to find the 'app' variable in the 'main.py' file within the 'backend' module implicitly
# Use --host 0.0.0.0 to bind to all network interfaces inside the container
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
