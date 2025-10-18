# cloud_vpn_manager.py
import subprocess
import tempfile
import os
import psutil
import threading
import time
from pathlib import Path
import socket
from django.conf import settings

class CloudVPNManager:
    def __init__(self):
        self.vpn_processes = {}
        self.config_dir = getattr(settings, 'VPN_CONFIG_DIR', '/tmp/vpn_configs')
        os.makedirs(self.config_dir, exist_ok=True)
        self._verify_installation()
    
    def _verify_installation(self):
        """Verify OpenVPN and WireGuard are installed in the container"""
        print("🔧 Verifying VPN dependencies in cloud environment...")
        
        try:
            # Check OpenVPN
            result = subprocess.run(['openvpn', '--version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ OpenVPN is installed and working")
            else:
                raise Exception("OpenVPN not functioning properly")
        except Exception as e:
            print(f"❌ OpenVPN check failed: {e}")
            raise Exception("OpenVPN not available in container. Check Dockerfile installation.")
        
        try:
            # Check WireGuard
            result = subprocess.run(['wg', '--version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ WireGuard is installed and working")
            else:
                print("⚠️ WireGuard not functioning properly")
        except Exception as e:
            print(f"⚠️ WireGuard check failed: {e}")
    
    def create_openvpn_config(self, server, user):
        """Generate production OpenVPN configuration for cloud"""
        config = f"""# Production OpenVPN Configuration
# Server: {server.name} - {server.country}
# Cloud Deployment: Render

client
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
auth-nocache
mute-replay-warnings

# Cloud optimization
tun-mtu 1500
fragment 1300
mssfix

# DNS for cloud
dhcp-option DNS 1.1.1.1
dhcp-option DNS 1.0.0.1

# Security
tls-version-min 1.2
reneg-sec 0

# Server certificates
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
    
    def start_openvpn_connection(self, server, user):
        """Start OpenVPN connection in cloud environment"""
        try:
            config = self.create_openvpn_config(server, user)
            
            # Create config file
            config_file = Path(self.config_dir) / f"ovpn_{user.id}_{server.id}.conf"
            with open(config_file, 'w') as f:
                f.write(config)
            
            print(f"🔗 Starting OpenVPN connection to {server.ip_address}:{server.port}")
            
            # Start OpenVPN with cloud-appropriate settings
            cmd = [
                'openvpn',
                '--config', str(config_file),
                '--auth-nocache',
                '--daemon'  # Run in background for cloud
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor connection in background thread
            connected = threading.Event()
            error_occurred = threading.Event()
            
            def monitor_connection():
                try:
                    for line in process.stdout:
                        line = line.strip()
                        print(f"OpenVPN: {line}")
                        
                        if "Initialization Sequence Completed" in line:
                            print("✅ OpenVPN connected successfully")
                            connected.set()
                            break
                        elif any(error in line for error in ['ERROR', 'Exiting', 'failed']):
                            print(f"❌ OpenVPN error: {line}")
                            error_occurred.set()
                            break
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    error_occurred.set()
            
            monitor_thread = threading.Thread(target=monitor_connection)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            self.vpn_processes[str(user.id)] = {
                'process': process,
                'config_file': config_file,
                'type': 'openvpn',
                'connected': connected,
                'error_occurred': error_occurred
            }
            
            # Wait for connection with cloud-appropriate timeout
            timeout = 30  # Longer timeout for cloud
            if connected.wait(timeout):
                return True
            elif error_occurred.is_set():
                # Get error details
                stderr_output = process.stderr.read()
                raise Exception(f"OpenVPN connection failed: {stderr_output}")
            else:
                raise Exception("OpenVPN connection timeout in cloud environment")
                
        except Exception as e:
            self.cleanup_connection(str(user.id))
            raise Exception(f"Cloud OpenVPN connection failed: {str(e)}")
    
    def start_wireguard_connection(self, server, user):
        """Start WireGuard connection in cloud"""
        try:
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
"""
            
            config_file = Path(self.config_dir) / f"wg_{user.id}_{server.id}.conf"
            with open(config_file, 'w') as f:
                f.write(config)
            
            print(f"🔗 Starting WireGuard connection to {server.ip_address}:{server.port}")
            
            # Start WireGuard
            interface = f"wg{user.id[:8]}"
            cmd = ['wg-quick', 'up', str(config_file)]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for connection
            timeout = 15
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    result = subprocess.run(
                        ['wg', 'show', interface],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        self.vpn_processes[str(user.id)] = {
                            'process': process,
                            'interface': interface,
                            'config_file': config_file,
                            'type': 'wireguard'
                        }
                        print("✅ WireGuard connected successfully")
                        return True
                except subprocess.TimeoutExpired:
                    continue
                except Exception:
                    continue
                time.sleep(1)
            
            raise Exception("WireGuard connection timeout in cloud")
            
        except Exception as e:
            self.cleanup_connection(str(user.id))
            raise Exception(f"Cloud WireGuard connection failed: {str(e)}")
    
    def stop_connection(self, user_id):
        """Stop VPN connection in cloud"""
        try:
            if user_id in self.vpn_processes:
                session_data = self.vpn_processes[user_id]
                
                if session_data['type'] == 'wireguard':
                    config_file = session_data['config_file']
                    subprocess.run([
                        'wg-quick', 'down', str(config_file)
                    ], capture_output=True, timeout=10)
                
                elif session_data['type'] == 'openvpn':
                    session_data['process'].terminate()
                    try:
                        session_data['process'].wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        session_data['process'].kill()
                
                # Cleanup config file
                if 'config_file' in session_data:
                    try:
                        os.unlink(session_data['config_file'])
                    except:
                        pass
                
                del self.vpn_processes[user_id]
                print(f"🔌 Disconnected VPN for user {user_id}")
                return True
                
        except Exception as e:
            print(f"Error stopping VPN in cloud: {e}")
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
        """Check if VPN connection is active in cloud"""
        if user_id not in self.vpn_processes:
            return False
        
        session_data = self.vpn_processes[user_id]
        
        if session_data['type'] == 'wireguard':
            try:
                result = subprocess.run(
                    ['wg', 'show', session_data['interface']],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0
            except:
                return False
        
        elif session_data['type'] == 'openvpn':
            return session_data['process'].poll() is None
        
        return False