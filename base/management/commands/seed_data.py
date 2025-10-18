from django.core.management.base import BaseCommand
from base.models import ProxyServer
import random

class Command(BaseCommand):
    help = 'Seed the database with initial proxy servers'

    def handle(self, *args, **options):
        # Create sample proxy servers including South Africa
        servers_data = [
            # South Africa servers
            {'name': 'SA Johannesburg Server', 'country': 'South Africa', 'city': 'Johannesburg', 'ip_address': '196.43.235.10', 'port': 8080, 'protocol': 'http'},
            {'name': 'SA Cape Town Server', 'country': 'South Africa', 'city': 'Cape Town', 'ip_address': '196.43.235.11', 'port': 8080, 'protocol': 'https'},
            {'name': 'SA Durban Server', 'country': 'South Africa', 'city': 'Durban', 'ip_address': '196.43.235.12', 'port': 8080, 'protocol': 'socks5'},
            
            # Other countries
            {'name': 'US East Server', 'country': 'USA', 'city': 'New York', 'ip_address': '192.168.1.10', 'port': 8080, 'protocol': 'http'},
            {'name': 'US West Server', 'country': 'USA', 'city': 'Los Angeles', 'ip_address': '192.168.1.11', 'port': 8080, 'protocol': 'http'},
            {'name': 'Germany Server', 'country': 'Germany', 'city': 'Frankfurt', 'ip_address': '192.168.1.12', 'port': 8080, 'protocol': 'socks5'},
            {'name': 'Japan Server', 'country': 'Japan', 'city': 'Tokyo', 'ip_address': '192.168.1.13', 'port': 8080, 'protocol': 'https'},
            {'name': 'Singapore Server', 'country': 'Singapore', 'city': 'Singapore', 'ip_address': '192.168.1.14', 'port': 8080, 'protocol': 'http'},
            {'name': 'Brazil Server', 'country': 'Brazil', 'city': 'São Paulo', 'ip_address': '192.168.1.15', 'port': 8080, 'protocol': 'socks5'},
            {'name': 'UK Server', 'country': 'United Kingdom', 'city': 'London', 'ip_address': '192.168.1.16', 'port': 8080, 'protocol': 'https'},
            {'name': 'Canada Server', 'country': 'Canada', 'city': 'Toronto', 'ip_address': '192.168.1.17', 'port': 8080, 'protocol': 'http'},
            {'name': 'Australia Server', 'country': 'Australia', 'city': 'Sydney', 'ip_address': '192.168.1.18', 'port': 8080, 'protocol': 'https'},
            {'name': 'France Server', 'country': 'France', 'city': 'Paris', 'ip_address': '192.168.1.19', 'port': 8080, 'protocol': 'socks5'},
            {'name': 'Netherlands Server', 'country': 'Netherlands', 'city': 'Amsterdam', 'ip_address': '192.168.1.20', 'port': 8080, 'protocol': 'http'},
        ]

        for server_data in servers_data:
            server, created = ProxyServer.objects.get_or_create(
                name=server_data['name'],
                defaults={
                    'country': server_data['country'],
                    'city': server_data['city'],
                    'ip_address': server_data['ip_address'],
                    'port': server_data['port'],
                    'protocol': server_data['protocol'],
                    'load': random.uniform(0.1, 0.7),
                    'latency': random.randint(20, 150),
                    'max_users': 100,
                    'current_users': random.randint(0, 80),
                    'location_data': {
                        'latitude': random.uniform(-90, 90),
                        'longitude': random.uniform(-180, 180),
                    }
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created server: {server.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Server already exists: {server.name}'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded database with proxy servers'))