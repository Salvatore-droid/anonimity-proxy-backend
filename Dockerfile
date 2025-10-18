# Dockerfile

# Use official Python runtime as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies including OpenVPN and WireGuard
RUN apt-get update && apt-get install -y \
    # Python build dependencies
    gcc \
    g++ \
    # VPN dependencies
    openvpn \
    wireguard-tools \
    openssh-client \
    net-tools \
    iptables \
    iproute2 \
    # System utilities
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory in container
WORKDIR /app

# Copy requirements first (for better Docker caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Create directories for VPN
RUN mkdir -p /etc/vpn-ca/production /tmp/vpn_configs

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port (Render will use this)
EXPOSE 8000

# Command to run when container starts
CMD ["gunicorn", "proxy_project.wsgi:application", "--bind", "0.0.0.0:8000"]