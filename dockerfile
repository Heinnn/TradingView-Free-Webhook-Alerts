# Use the official Python image (slim version)
FROM python:3.10.13-slim-bookworm

# Set the working directory to /app
WORKDIR /app

# Copy all local files to the container at /app
COPY . /app

# Upgrade pip and install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-traditional  \
    telnet \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install dependencies defined in requirements.txt
RUN pip install -r requirements.txt

# Expose the port for the application if necessary
EXPOSE 65432

# Specify the command to run on container start
CMD ["python3", "main.py"]
