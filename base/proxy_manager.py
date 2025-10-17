import random
from django.utils import timezone
from .models import ProxyServer, UserSession, ConnectionLog

class ProxyManager:
    @staticmethod
    def get_optimal_server(country=None):
        """Get the best server based on load, latency, and country preference"""
        queryset = ProxyServer.objects.filter(is_active=True)
        
        if country and country != 'Automatic':
            queryset = queryset.filter(country__iexact=country)
        
        # Filter servers with load < 80%
        queryset = queryset.filter(load__lt=0.8)
        
        # Return server with lowest load and latency
        return queryset.order_by('load', 'latency').first()

    @classmethod
    def create_session(cls, user, server_id=None, country=None, security_level='high', 
                      client_ip=None, config=None):
        """Create a new proxy session"""
        
        # Get or select server
        if server_id:
            try:
                server = ProxyServer.objects.get(id=server_id, is_active=True)
            except ProxyServer.DoesNotExist:
                raise Exception("Selected server not available")
        else:
            server = cls.get_optimal_server(country=country)
            if not server:
                raise Exception("No available servers for the selected location")

        # Check server capacity
        if server.current_users >= server.max_users:
            raise Exception("Server is at full capacity")

        # End any existing session for this user
        UserSession.objects.filter(user=user, is_active=True).update(
            is_active=False, 
            end_time=timezone.now()
        )

        # Create new session
        session = UserSession.objects.create(
            user=user,
            proxy_server=server,
            original_ip=client_ip,
            is_active=True,
            session_config={
                'security_level': security_level,
                'kill_switch': config.get('enable_kill_switch', True) if config else True,
                'dns_protection': config.get('enable_dns_protection', True) if config else True,
                'config': config or {}
            }
        )

        # Update server user count
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
                'security_level': security_level,
                'client_ip': client_ip
            }
        )

        return session

    @staticmethod
    def end_session(session):
        """End a proxy session"""
        session.is_active = False
        session.end_time = timezone.now()
        session.save()

        # Update server user count
        server = session.proxy_server
        server.current_users = max(0, server.current_users - 1)
        server.update_load()
        server.save()

        # Update user data usage
        session.user.data_used += session.data_used
        session.user.save()

        # Log disconnection
        ConnectionLog.objects.create(
            session=session,
            event_type='disconnect',
            details={
                'data_used': session.data_used,
                'duration': str(session.duration()) if session.duration() else None
            }
        )

    @staticmethod
    def update_server_stats():
        """Periodically update server statistics"""
        servers = ProxyServer.objects.filter(is_active=True)
        for server in servers:
            # Simulate latency changes
            server.latency = random.randint(10, 150)
            server.save()