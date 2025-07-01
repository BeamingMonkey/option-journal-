# Use official Python base image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy your requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app source code
COPY . .

# Expose port 5000 for Flask
EXPOSE 5000

# Run Gunicorn with 1 worker
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]
