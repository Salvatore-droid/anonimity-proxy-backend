# proxy_manager.py - Updated for cloud
from .cloud_vpn_manager import CloudVPNManager
from django.utils import timezone
from .models import ProxyServer, UserSession, ConnectionLog

class ProxyManager:
    def __init__(self):
        self.real_vpn = CloudVPNManager()  # Use cloud manager
    
    @staticmethod
    def get_optimal_server(country=None):
        """Get the best server based on real metrics"""
        queryset = ProxyServer.objects.filter(is_active=True)
        
        if country and country != 'Automatic':
            queryset = queryset.filter(country__iexact=country)
        
        queryset = queryset.filter(load__lt=0.8)
        return queryset.order_by('load', 'latency').first()
    
    def create_session(self, user, server_id=None, country=None, security_level='high', 
                      client_ip=None, config=None):
        """Create real VPN session in cloud"""
        
        # Get or select server
        if server_id:
            try:
                server = ProxyServer.objects.get(id=server_id, is_active=True)
            except ProxyServer.DoesNotExist:
                raise Exception("Selected server not available")
        else:
            server = self.get_optimal_server(country=country)
            if not server:
                raise Exception("No available servers for the selected location")

        # Verify user has required cloud certificates
        if server.vpn_type == 'openvpn':
            if not user.client_certificate or not user.client_private_key:
                raise Exception("User missing OpenVPN certificates for cloud deployment")
        elif server.vpn_type == 'wireguard':
            if not user.wireguard_private_key:
                raise Exception("User missing WireGuard private key for cloud deployment")

        # End any existing session
        UserSession.objects.filter(user=user, is_active=True).update(
            is_active=False, 
            end_time=timezone.now()
        )
        
        # Stop any running VPN connection
        self.real_vpn.stop_connection(str(user.id))

        # Start real VPN connection in cloud
        try:
            print(f"☁️ Starting {server.vpn_type} connection in cloud...")
            
            if server.vpn_type == 'wireguard':
                success = self.real_vpn.start_wireguard_connection(server, user)
            elif server.vpn_type == 'openvpn':
                success = self.real_vpn.start_openvpn_connection(server, user)
            else:
                raise Exception(f"Unsupported VPN type in cloud: {server.vpn_type}")
            
            if not success:
                raise Exception("Failed to establish VPN connection in cloud")
                
        except Exception as e:
            raise Exception(f"Cloud VPN connection failed: {str(e)}")

        # Create session record
        session = UserSession.objects.create(
            user=user,
            proxy_server=server,
            original_ip=client_ip,
            is_active=True,
            session_config={
                'security_level': security_level,
                'kill_switch': config.get('enable_kill_switch', True) if config else True,
                'dns_protection': config.get('enable_dns_protection', True) if config else True,
                'vpn_type': server.vpn_type,
                'cloud_deployment': True,
                'config': config or {}
            }
        )

        # Update server stats
        server.current_users += 1
        server.update_load()
        server.save()

        # Log connection
        ConnectionLog.objects.create(
            session=session,
            event_type='connect',
            details={
                'server': server.name,
                'location': f"{server.country}, {server.city}",
                'protocol': server.protocol,
                'vpn_type': server.vpn_type,
                'security_level': security_level,
                'client_ip': client_ip,
                'cloud_deployment': True,
                'real_connection': True
            }
        )

        return session

    def end_session(self, session):
        """End real VPN session in cloud"""
        self.real_vpn.stop_connection(str(session.user.id))
        
        session.is_active = False
        session.end_time = timezone.now()
        session.save()

        server = session.proxy_server
        server.current_users = max(0, server.current_users - 1)
        server.update_load()
        server.save()

        session.user.data_used += session.data_used
        session.user.save()

        ConnectionLog.objects.create(
            session=session,
            event_type='disconnect',
            details={
                'data_used': session.data_used,
                'duration': str(session.duration()) if session.duration() else None,
                'cloud_deployment': True
            }
        )