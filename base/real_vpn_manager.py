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
    
    def create_wireguard_config(self, server, user):
        """Generate WireGuard configuration"""
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
{user.private_key}
</key>
"""
        return config

    def create_south_africa_openvpn_config(self, server, user):
        """Specialized config for South Africa servers"""
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
dhcp-option DNS 1.1.1.1
dhcp-option DNS 1.0.0.1

# South Africa optimization
sndbuf 393216
rcvbuf 393216
push "sndbuf 393216"
push "rcvbuf 393216"

<ca>
-----BEGIN CERTIFICATE-----
# Add actual CA certificate for South Africa server
MIID...  # You need real certificates
-----END CERTIFICATE-----
</ca>
<cert>
-----BEGIN CERTIFICATE-----
# Add actual client certificate
MIIE...  # You need real certificates  
-----END CERTIFICATE-----
</cert>
<key>
-----BEGIN PRIVATE KEY-----
# Add actual private key
MIIE...  # You need real certificates
-----END PRIVATE KEY-----
</key>
"""
        return config

    def create_south_africa_wireguard_config(self, server, user):
        """WireGuard config optimized for South Africa"""
        config = f"""[Interface]
PrivateKey = {user.wireguard_private_key}
Address = 10.7.0.2/24
DNS = 1.1.1.1, 1.0.0.1
MTU = 1420

[Peer]
PublicKey = {server.public_key}
Endpoint = {server.endpoint}:{server.port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 21

# South Africa specific optimizations
PreUp = echo "Connecting to South Africa server"
PostUp = iptables -I OUTPUT ! -o %i -m addrtype ! --src-type LOCAL -j REJECT
PreDown = iptables -D OUTPUT ! -o %i -m addrtype ! --src-type LOCAL -j REJECT
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
            
            # Wait for connection
            timeout = 10
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
                            'type': 'wireguard'
                        }
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
                '--auth-nocache',
                '--redirect-gateway', 'def1',
                '--dhcp-option', 'DNS', '1.1.1.1'
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor connection status
            def monitor_connection():
                for line in process.stdout:
                    if "Initialization Sequence Completed" in line:
                        self.vpn_processes[user.id]['connected'] = True
                        break
            
            monitor_thread = threading.Thread(target=monitor_connection)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            self.vpn_processes[user.id] = {
                'process': process,
                'config_file': config_file,
                'type': 'openvpn',
                'connected': False
            }
            
            # Wait for connection
            timeout = 15
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.vpn_processes[user.id].get('connected'):
                    return True
                time.sleep(1)
            
            raise Exception("OpenVPN connection timeout")
            
        except Exception as e:
            self.cleanup_connection(user.id)
            raise Exception(f"OpenVPN connection failed: {str(e)}")
    
    def start_socks5_connection(self, server, user):
        """Start SOCKS5 proxy connection"""
        try:
            # Create SSH tunnel for SOCKS5
            cmd = [
                'ssh', '-o', 'StrictHostKeyChecking=no',
                '-D', '1080',  # SOCKS proxy on port 1080
                '-N', '-f',  # Background, no command
                f'user@{server.ip_address}',  # Replace with actual credentials
                '-p', str(server.port)
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.vpn_processes[user.id] = {
                'process': process,
                'type': 'socks5',
                'local_port': 1080
            }
            
            # Verify connection
            time.sleep(2)
            if process.poll() is None:  # Still running
                return True
            else:
                raise Exception("SOCKS5 tunnel failed")
                
        except Exception as e:
            self.cleanup_connection(user.id)
            raise Exception(f"SOCKS5 connection failed: {str(e)}")
    
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
                    session_data['process'].wait(timeout=5)
                
                elif session_data['type'] == 'socks5':
                    # Kill SSH tunnel
                    session_data['process'].terminate()
                
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
        
        elif session_data['type'] == 'socks5':
            # Check SSH tunnel
            return session_data['process'].poll() is None
        
        return False
    
    def _generate_client_ip(self, server):
        """Generate client IP address for VPN"""
        # Simple IP generation - in production use proper IPAM
        base_ip = "10.8.0."
        client_id = hash(str(server.id)) % 254 + 2
        return f"{base_ip}{client_id}/24"