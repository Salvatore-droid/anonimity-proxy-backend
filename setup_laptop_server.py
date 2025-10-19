#!/usr/bin/env python3
import os
import django
import sys

# Add your project to path - UPDATE THIS PATH
sys.path.append('/home/salvatore-droid/Desktop/python/django/anonimity-proxy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proxy_project.settings')  # UPDATE THIS
django.setup()

from base.models import ProxyServer
import uuid
import requests

def setup_laptop_server():
    """Add your laptop server to the database"""
    
    # Get your public IP
    try:
        public_ip = requests.get('https://api.ipify.org', timeout=5).text
        print(f"🌐 Your public IP: {public_ip}")
    except:
        public_ip = input("🌐 Enter your public IP: ")
    
    # Create laptop server entry - WITHOUT 'provider' field
    laptop_server, created = ProxyServer.objects.get_or_create(
        name='laptop-home-server',
        defaults={
            'id': uuid.uuid4(),
            'country': 'Kenya',  # Changed to your actual country
            'city': 'Rongo',   # Changed to your actual city
            'ip_address': public_ip,
            'port': 1194,
            'protocol': 'openvpn',
            'vpn_type': 'openvpn',
            'is_active': True,
            'max_users': 5,
            'encryption': 'AES-256-GCM',
            'handshake': 'RSA-2048',
            # Removed 'provider' field since it doesn't exist in your model
        }
    )
    
    if created:
        print(f"✅ Laptop server added: {public_ip}:1194")
    else:
        laptop_server.ip_address = public_ip
        laptop_server.is_active = True
        laptop_server.save()
        print(f"✅ Laptop server updated: {public_ip}:1194")

if __name__ == "__main__":
    setup_laptop_server()