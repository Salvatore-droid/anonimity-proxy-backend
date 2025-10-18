# management/commands/load_real_servers.py
from django.core.management.base import BaseCommand
from proxyapp.models import ProxyServer
import uuid

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Real VPN servers (replace with actual servers)
        real_servers = [
            {
                'name': 'Mullvad Sweden',
                'country': 'Sweden',
                'city': 'Stockholm',
                'ip_address': '193.138.218.782',  # Example
                'port': 51820,
                'protocol': 'wireguard',
                'vpn_type': 'wireguard',
                'public_key': 'real_public_key_here',
            },
            {
                'name': 'ExpressVPN UK',
                'country': 'United Kingdom',
                'city': 'London',
                'ip_address': '185.159.157.22',  # Example
                'port': 1194,
                'protocol': 'openvpn',
                'vpn_type': 'openvpn',
            },
            # Add more real servers...
        ]
        
        for server_data in real_servers:
            ProxyServer.objects.update_or_create(
                name=server_data['name'],
                defaults=server_data
            )