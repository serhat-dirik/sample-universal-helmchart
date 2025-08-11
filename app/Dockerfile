# Use a lightweight Python base image
FROM python:3.9-slim

# Create a non-root user with a specific UID
RUN useradd --uid 1001 --create-home appuser

# Set the working directory
WORKDIR /app

# Copy the application code
COPY main.py .

# Switch to the non-root user
USER 1001

# Command to run the application
CMD ["python", "main.py"]