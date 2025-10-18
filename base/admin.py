from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ProxyServer, UserSession, ConnectionLog

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'subscription_tier', 'data_used', 'is_active', 'created_at')
    list_filter = ('subscription_tier', 'is_active', 'is_staff', 'created_at')
    search_fields = ('username', 'email', 'mobile_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('id', 'username', 'password')}),
        ('Personal info', {'fields': ('email', 'mobile_id')}),
        ('Subscription', {'fields': ('subscription_tier', 'data_used')}),
        ('VPN Keys', {'fields': ('wireguard_private_key', 'wireguard_public_key', 'client_certificate', 'client_private_key')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'mobile_id', 'subscription_tier'),
        }),
    )

@admin.register(ProxyServer)
class ProxyServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'city', 'ip_address', 'port', 'vpn_type', 'is_active', 'load_percentage', 'current_users', 'created_at')
    list_filter = ('country', 'vpn_type', 'is_active', 'protocol', 'created_at')
    search_fields = ('name', 'country', 'city', 'ip_address')
    readonly_fields = ('id', 'created_at')
    list_editable = ('is_active',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Info', {'fields': ('id', 'name', 'country', 'city', 'ip_address', 'port', 'protocol')}),
        ('VPN Configuration', {'fields': ('vpn_type', 'vpn_config', 'endpoint', 'encryption', 'handshake')}),
        ('WireGuard Keys', {'fields': ('public_key', 'private_key')}),
        ('Certificates', {'fields': ('ca_certificate', 'server_certificate', 'server_key', 'dh_params')}),
        ('Server Status', {'fields': ('is_active', 'load', 'latency', 'max_users', 'current_users')}),
        ('Location Data', {'fields': ('location_data',)}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    
    def load_percentage(self, obj):
        return f"{obj.load * 100:.1f}%"
    load_percentage.short_description = 'Load'

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'proxy_server', 'original_ip', 'start_time', 'end_time', 'data_used_mb', 'is_active', 'is_routing')
    list_filter = ('is_active', 'is_routing', 'start_time', 'proxy_server__country')
    search_fields = ('user__username', 'proxy_server__name', 'original_ip', 'assigned_ip')
    readonly_fields = ('id', 'start_time', 'duration_display')
    ordering = ('-start_time',)
    
    fieldsets = (
        ('Session Info', {'fields': ('id', 'user', 'proxy_server', 'original_ip', 'assigned_ip')}),
        ('Timing', {'fields': ('start_time', 'end_time', 'duration_display')}),
        ('Status', {'fields': ('is_active', 'is_routing', 'data_used')}),
        ('Technical Details', {'fields': ('vpn_pid', 'interface', 'session_config', 'vpn_config_file')}),
    )
    
    def data_used_mb(self, obj):
        return f"{obj.data_used / (1024 * 1024):.2f} MB"
    data_used_mb.short_description = 'Data Used'
    
    def duration_display(self, obj):
        duration = obj.duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}h {minutes}m {seconds}s"
        return "Active"
    duration_display.short_description = 'Duration'

@admin.register(ConnectionLog)
class ConnectionLogAdmin(admin.ModelAdmin):
    list_display = ('session_user', 'event_type', 'timestamp', 'short_details')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('session__user__username', 'session__proxy_server__name', 'details')
    readonly_fields = ('id', 'timestamp')
    ordering = ('-timestamp',)
    
    fieldsets = (
        ('Log Info', {'fields': ('id', 'session', 'event_type', 'timestamp')}),
        ('Details', {'fields': ('details',)}),
    )
    
    def session_user(self, obj):
        return obj.session.user.username
    session_user.short_description = 'User'
    
    def short_details(self, obj):
        details_str = str(obj.details)
        return details_str[:50] + '...' if len(details_str) > 50 else details_str
    short_details.short_description = 'Details'

# Optional: Custom admin site header
admin.site.site_header = "Anonimity VPN Administration"
admin.site.site_title = "Anonimity VPN Admin"
admin.site.index_title = "Welcome to Anonimity VPN Admin Portal"