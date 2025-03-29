# Use the official Python image from the Docker Hub
FROM python:3.12-slim

USER root

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Remove an unwanted package before installing (e.g., "package-to-ignore")
RUN grep -v "pywin32" requirements.txt > filtered_requirements.txt && \
    pip install --no-cache-dir -r filtered_requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Set the default command to run the application
CMD ["python", "PROTEUS.py"]