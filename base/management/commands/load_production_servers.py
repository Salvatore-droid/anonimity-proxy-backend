# management/commands/load_production_servers.py
import json
import os
from django.core.management.base import BaseCommand
from base.models import ProxyServer
import uuid

class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("🚀 Loading PRODUCTION VPN servers with REAL South Africa IPs...")
        
        # Load production certificate data
        cert_file = '/etc/vpn-ca/production/production_certificates.json'
        
        if not os.path.exists(cert_file):
            self.stdout.write(
                self.style.ERROR('❌ Production certificates not found. Run certificate generator first.')
            )
            self.stdout.write(
                self.style.WARNING('💡 Run: python scripts/production_certificate_generator.py')
            )
            return
        
        with open(cert_file, 'r') as f:
            production_data = json.load(f)
        
        # Load production servers - ONLY using fields that exist in your model
        production_servers = self.get_production_servers(production_data)
        
        success_count = 0
        for server_data in production_servers:
            try:
                server_id = server_data.pop('id')
                server, created = ProxyServer.objects.update_or_create(
                    id=server_id,
                    defaults=server_data
                )
                
                status = "✅ ADDED" if created else "↻ UPDATED"
                self.stdout.write(
                    self.style.SUCCESS(f'{status}: {server.name} | {server.ip_address}:{server.port}')
                )
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ FAILED: {server_data["name"]} - {str(e)}')
                )
        
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f'🎉 SUCCESS: Loaded {success_count} PRODUCTION VPN servers!')
        )
        
        # Show South Africa server count
        sa_servers = ProxyServer.objects.filter(country='South Africa').count()
        self.stdout.write(
            self.style.SUCCESS(f'🇿🇦 South Africa servers: {sa_servers}')
        )
    
    def get_production_servers(self, production_data):
        """Get production servers using ONLY fields that exist in ProxyServer model"""
        servers = []
        
        for server_name, server_data in production_data['servers'].items():
            server_info = server_data['server_info']
            cert_info = server_data['certificate_info']
            
            # ONLY include fields that exist in your ProxyServer model
            server_config = {
                'id': uuid.uuid4(),
                'name': f"{server_info['provider']} {server_info['city']}",
                'country': server_info['country'],
                'city': server_info['city'],
                'ip_address': server_info['ip_address'],  # REAL IP
                'port': server_info['port'],
                'protocol': server_info['protocol'],
                'vpn_type': 'openvpn',
                'is_active': True,
                'load': self.calculate_initial_load(server_info['provider']),
                'latency': self.calculate_initial_latency(server_info['country']),
                'max_users': 1000,
                'current_users': self.calculate_initial_users(server_info['provider']),
                'location_data': self.get_location_data(server_info['city']),
                'encryption': 'AES-256-GCM',
                'handshake': 'RSA-4096',
                'endpoint': server_info['domain'],
                
                # Certificate fields that EXIST in your model
                'ca_certificate': production_data['ca_certificate'],
                'server_certificate': cert_info['server_crt'],  # REAL certificate
                'server_key': cert_info['server_key'],  # REAL private key
                'dh_params': production_data['dh_params'],
                
                # VPN config
                'vpn_config': server_data['openvpn_config'],
                
                # REMOVED: 'provider', 'tls_auth' - these don't exist in your model
                # REMOVED: 'tls_version', 'data_cipher', 'auth_digest'
            }
            servers.append(server_config)
        
        return servers
    
    def calculate_initial_load(self, provider):
        """Calculate initial server load based on provider"""
        load_map = {
            'ExpressVPN': 0.25,
            'NordVPN': 0.30,
            'Surfshark': 0.35,
            'Private Internet Access': 0.28,
            'CyberGhost': 0.32,
            'ProtonVPN': 0.20,
            'Windscribe': 0.25
        }
        return load_map.get(provider, 0.3)
    
    def calculate_initial_latency(self, country):
        """Calculate initial latency based on country"""
        latency_map = {
            'South Africa': 45,
            'Netherlands': 25,
            'Switzerland': 35,
        }
        return latency_map.get(country, 30)
    
    def calculate_initial_users(self, provider):
        """Calculate initial user count based on provider popularity"""
        user_map = {
            'ExpressVPN': 125,
            'NordVPN': 180,
            'Surfshark': 140,
            'Private Internet Access': 126,
            'CyberGhost': 176,
            'ProtonVPN': 100,
            'Windscribe': 100
        }
        return user_map.get(provider, 100)
    
    def get_location_data(self, city):
        """Get coordinates for cities"""
        locations = {
            'Johannesburg': {'latitude': -26.2041, 'longitude': 28.0473},
            'Cape Town': {'latitude': -33.9249, 'longitude': 18.4241},
            'Zurich': {'latitude': 47.3769, 'longitude': 8.5417},
            'Amsterdam': {'latitude': 52.3676, 'longitude': 4.9041},
        }
        return locations.get(city, {'latitude': 0, 'longitude': 0})