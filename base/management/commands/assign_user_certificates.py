from django.core.management.base import BaseCommand
from base.models import User
import subprocess
import tempfile
from pathlib import Path

class Command(BaseCommand):
    help = 'Assign OpenVPN and WireGuard certificates to existing users'

    def handle(self, *args, **options):
        users = User.objects.all()
        
        for user in users:
            self.stdout.write(f"🔐 Assigning certificates to {user.username}...")
            
            # Generate OpenVPN certificates if missing
            if not user.client_certificate or not user.client_private_key:
                self.generate_openvpn_certificates(user)
            
            # Generate WireGuard keys if missing
            if not user.wireguard_private_key or not user.wireguard_public_key:
                self.generate_wireguard_keys(user)
            
            user.save()
            self.stdout.write(f"✅ Certificates assigned to {user.username}")

    def generate_openvpn_certificates(self, user):
        """Generate OpenVPN client certificates"""
        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Generate client private key
                key_file = temp_path / f"{user.username}.key"
                subprocess.run([
                    'openssl', 'genrsa', '-out', str(key_file), '4096'
                ], check=True, capture_output=True)
                
                # Generate certificate request
                csr_file = temp_path / f"{user.username}.csr"
                subprocess.run([
                    'openssl', 'req', '-new',
                    '-key', str(key_file),
                    '-out', str(csr_file),
                    '-subj', f'/C=ZA/ST=Gauteng/L=Johannesburg/O=AnonimityVPN/CN={user.username}'
                ], check=True, capture_output=True)
                
                # Sign certificate (using your CA - adjust paths as needed)
                crt_file = temp_path / f"{user.username}.crt"
                # Note: You'll need to adjust this to use your actual CA
                subprocess.run([
                    'openssl', 'x509', '-req', '-days', '365',
                    '-in', str(csr_file),
                    '-CA', '/tmp/vpn-ca/production/ca.crt',  # Adjust path
                    '-CAkey', '/tmp/vpn-ca/production/ca.key',  # Adjust path
                    '-CAcreateserial',
                    '-out', str(crt_file)
                ], check=True, capture_output=True)
                
                # Read and assign to user
                with open(crt_file, 'r') as f:
                    user.client_certificate = f.read()
                with open(key_file, 'r') as f:
                    user.client_private_key = f.read()
                    
        except Exception as e:
            self.stdout.write(f"❌ Error generating OpenVPN certs for {user.username}: {e}")

    def generate_wireguard_keys(self, user):
        """Generate WireGuard key pair"""
        try:
            # Generate private key
            result = subprocess.run([
                'wg', 'genkey'
            ], capture_output=True, text=True, check=True)
            private_key = result.stdout.strip()
            
            # Generate public key from private key
            result = subprocess.run([
                'wg', 'pubkey'
            ], input=private_key, capture_output=True, text=True, check=True)
            public_key = result.stdout.strip()
            
            user.wireguard_private_key = private_key
            user.wireguard_public_key = public_key
            
        except Exception as e:
            self.stdout.write(f"❌ Error generating WireGuard keys for {user.username}: {e}")