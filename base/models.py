from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mobile_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    subscription_tier = models.CharField(
        max_length=20, 
        choices=[('free', 'Free'), ('premium', 'Premium')],
        default='free'
    )
    data_used = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Fix the groups and user_permissions conflict
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='proxyapp_user_set',
        related_query_name='proxyapp_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='proxyapp_user_set',
        related_query_name='proxyapp_user',
    )

    def __str__(self):
        return f"{self.username} ({self.subscription_tier})"

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = uuid.uuid4()
        super().save(*args, **kwargs)

class ProxyServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField()
    protocol = models.CharField(
        max_length=10, 
        choices=[('http', 'HTTP'), ('socks5', 'SOCKS5'), ('https', 'HTTPS')]
    )
    is_active = models.BooleanField(default=True)
    load = models.FloatField(default=0.0)  # Server load 0-1
    latency = models.IntegerField(default=0)  # in ms
    max_users = models.IntegerField(default=100)
    current_users = models.IntegerField(default=0)
    location_data = models.JSONField(default=dict)  # GPS coordinates, etc.
    created_at = models.DateTimeField(auto_now_add=True)
    vpn_config = models.TextField(blank=True)  # OpenVPN/WireGuard config
    vpn_type = models.CharField(
        max_length=20,
        choices=[('openvpn', 'OpenVPN'), ('wireguard', 'WireGuard'), ('socks5', 'SOCKS5')],
        default='openvpn'
    )
    public_key = models.TextField(blank=True)  # For WireGuard
    private_key = models.TextField(blank=True)  # For WireGuard (encrypted)
    endpoint = models.CharField(max_length=255, blank=True)  # Server endpoint
    
    # Encryption settings
    encryption = models.CharField(max_length=50, default='AES-256-GCM')
    handshake = models.CharField(max_length=50, default='RSA-2048')

    class Meta:
        indexes = [
            models.Index(fields=['country', 'is_active']),
            models.Index(fields=['load', 'latency']),
        ]

    def update_load(self):
        self.load = min(self.current_users / self.max_users, 1.0)
        self.save()

    def __str__(self):
        return f"{self.name} ({self.country}) - {self.load*100:.1f}%"

class UserSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    proxy_server = models.ForeignKey(ProxyServer, on_delete=models.CASCADE, related_name='sessions')
    original_ip = models.GenericIPAddressField()
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    data_used = models.BigIntegerField(default=0)  # in bytes
    is_active = models.BooleanField(default=True)
    session_config = models.JSONField(default=dict)  # Security level, kill switch, etc.
    vpn_pid = models.IntegerField(null=True, blank=True)  # VPN process ID
    interface = models.CharField(max_length=20, blank=True)  # Network interface
    assigned_ip = models.GenericIPAddressField(null=True, blank=True)
    vpn_config_file = models.TextField(blank=True)  # Generated config
    is_routing = models.BooleanField(default=False)

    def duration(self):
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def __str__(self):
        status = "Active" if self.is_active else "Ended"
        return f"{self.user.username} -> {self.proxy_server.name} ({status})"

class ConnectionLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=50, choices=[
        ('connect', 'Connect'),
        ('disconnect', 'Disconnect'),
        ('location_change', 'Location Change'),
        ('error', 'Error'),
        ('data_usage', 'Data Usage')
    ])
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.session.user.username} - {self.event_type} at {self.timestamp}"