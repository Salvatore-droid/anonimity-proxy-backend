import subprocess
import tempfile
import os
import psutil
import threading
import time
from pathlib import Path
import socket
import select
from django.conf import settings

class RealVPNManager:
    def __init__(self):
        self.vpn_processes = {}
        self.config_dir = getattr(settings, 'VPN_CONFIG_DIR', '/tmp/vpn_configs')
        os.makedirs(self.config_dir, exist_ok=True)
    
    def is_laptop_server(self, server_ip):
        """Check if server is your laptop"""
        laptop_ips = [
            '192.168.1.131',  # ← REPLACE WITH YOUR ACTUAL IP
            '192.168.1.100',   # Your laptop's local IP
            '10.0.0.100'       # Alternative local IP
        ]
        return server_ip in laptop_ips or 'laptop' in server_ip.lower()
    
    def create_wireguard_config(self, server, user):
        """Generate WireGuard configuration"""
        # Special config for laptop server
        if self.is_laptop_server(server.ip_address):
            config = f"""[Interface]
PrivateKey = {user.wireguard_private_key}
Address = 10.8.0.2/24
DNS = 1.1.1.1, 1.0.0.1
MTU = 1420

[Peer]
PublicKey = {server.public_key}
Endpoint = {server.ip_address}:{server.port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25

# Laptop server optimization
PreUp = echo "Connecting to laptop server"
"""
        else:
            config = f"""[Interface]
PrivateKey = {user.wireguard_private_key}
Address = {self._generate_client_ip(server)}
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = {server.public_key}
Endpoint = {server.ip_address}:{server.port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
        return config
    
    def create_openvpn_config(self, server, user):
        """Generate OpenVPN configuration"""
        # Special config for laptop server
        if self.is_laptop_server(server.ip_address):
            config = f"""client
dev tun
proto udp
remote {server.ip_address} {server.port}
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher {server.encryption}
auth SHA256
verb 3
redirect-gateway def1

# Laptop server optimization
connect-retry 5
connect-retry-max 10

<ca>
{server.ca_certificate}
</ca>
<cert>
{user.client_certificate}
</cert>
<key>
{user.client_private_key}
</key>
"""
        else:
            config = f"""client
dev tun
proto udp
remote {server.ip_address} {server.port}
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher {server.encryption}
auth SHA256
verb 3
<ca>
{server.ca_certificate}
</ca>
<cert>
{user.client_certificate}
</cert>
<key>
{user.client_private_key}
</key>
"""
        return config

    def start_wireguard_connection(self, server, user):
        """Start real WireGuard VPN connection"""
        try:
            # Generate config
            config = self.create_wireguard_config(server, user)
            
            # Create config file
            config_file = Path(self.config_dir) / f"wg_{user.id}_{server.id}.conf"
            with open(config_file, 'w') as f:
                f.write(config)
            
            # Start WireGuard interface
            interface = f"wg{user.id[:8]}"
            cmd = [
                'wg-quick', 'up', str(config_file)
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Longer timeout for laptop server
            timeout = 20 if self.is_laptop_server(server.ip_address) else 10
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Test if interface is up
                    result = subprocess.run(
                        ['wg', 'show', interface],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        self.vpn_processes[user.id] = {
                            'process': process,
                            'interface': interface,
                            'config_file': config_file,
                            'type': 'wireguard',
                            'server_ip': server.ip_address,
                            'is_laptop': self.is_laptop_server(server.ip_address)
                        }
                        print(f"✅ WireGuard connected to {'laptop' if self.is_laptop_server(server.ip_address) else 'commercial'} server")
                        return True
                except:
                    pass
                time.sleep(1)
            
            raise Exception("WireGuard connection timeout")
            
        except Exception as e:
            self.cleanup_connection(user.id)
            raise Exception(f"WireGuard connection failed: {str(e)}")
    
    def start_openvpn_connection(self, server, user):
        """Start real OpenVPN connection"""
        try:
            config = self.create_openvpn_config(server, user)
            
            config_file = Path(self.config_dir) / f"ovpn_{user.id}_{server.id}.conf"
            with open(config_file, 'w') as f:
                f.write(config)
            
            # Start OpenVPN process
            cmd = [
                'openvpn',
                '--config', str(config_file),
                '--auth-nocache'
            ]
            
            # Add redirect-gateway for laptop server
            if self.is_laptop_server(server.ip_address):
                cmd.extend(['--redirect-gateway', 'def1'])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor connection status
            connected = threading.Event()
            
            def monitor_connection():
                for line in process.stdout:
                    line = line.strip()
                    print(f"OpenVPN: {line}")
                    if "Initialization Sequence Completed" in line:
                        connected.set()
                        break
            
            monitor_thread = threading.Thread(target=monitor_connection)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            self.vpn_processes[user.id] = {
                'process': process,
                'config_file': config_file,
                'type': 'openvpn',
                'connected': connected,
                'server_ip': server.ip_address,
                'is_laptop': self.is_laptop_server(server.ip_address)
            }
            
            # Wait for connection with appropriate timeout
            timeout = 30 if self.is_laptop_server(server.ip_address) else 15
            start_time = time.time()
            while time.time() - start_time < timeout:
                if connected.is_set():
                    print(f"✅ OpenVPN connected to {'laptop' if self.is_laptop_server(server.ip_address) else 'commercial'} server")
                    return True
                if process.poll() is not None:
                    # Process ended, check for errors
                    stderr_output = process.stderr.read()
                    raise Exception(f"OpenVPN process failed: {stderr_output}")
                time.sleep(1)
            
            raise Exception("OpenVPN connection timeout")
            
        except Exception as e:
            self.cleanup_connection(user.id)
            raise Exception(f"OpenVPN connection failed: {str(e)}")
    
    def stop_connection(self, user_id):
        """Stop VPN connection"""
        try:
            if user_id in self.vpn_processes:
                session_data = self.vpn_processes[user_id]
                
                if session_data['type'] == 'wireguard':
                    # Stop WireGuard interface
                    config_file = session_data['config_file']
                    subprocess.run([
                        'wg-quick', 'down', str(config_file)
                    ], capture_output=True)
                
                elif session_data['type'] == 'openvpn':
                    # Terminate OpenVPN process
                    session_data['process'].terminate()
                    try:
                        session_data['process'].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        session_data['process'].kill()
                
                # Cleanup config file
                if 'config_file' in session_data:
                    try:
                        os.unlink(session_data['config_file'])
                    except:
                        pass
                
                del self.vpn_processes[user_id]
                return True
                
        except Exception as e:
            print(f"Error stopping VPN: {e}")
            return False
    
    def cleanup_connection(self, user_id):
        """Cleanup failed connection"""
        try:
            if user_id in self.vpn_processes:
                session_data = self.vpn_processes[user_id]
                if session_data['process'].poll() is None:
                    session_data['process'].kill()
                
                if 'config_file' in session_data:
                    try:
                        os.unlink(session_data['config_file'])
                    except:
                        pass
                
                del self.vpn_processes[user_id]
        except:
            pass
    
    def get_connection_status(self, user_id):
        """Check if VPN connection is active"""
        if user_id not in self.vpn_processes:
            return False
        
        session_data = self.vpn_processes[user_id]
        
        if session_data['type'] == 'wireguard':
            # Check WireGuard interface
            try:
                result = subprocess.run(
                    ['wg', 'show', session_data['interface']],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            except:
                return False
        
        elif session_data['type'] == 'openvpn':
            # Check OpenVPN process
            return session_data['process'].poll() is None
        
        return False
    
    def _generate_client_ip(self, server):
        """Generate client IP address for VPN"""
        base_ip = "10.8.0."
        client_id = hash(str(server.id)) % 254 + 2
        return f"{base_ip}{client_id}/24"