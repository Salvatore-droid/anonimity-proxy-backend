from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, ProxyServer, UserSession, ConnectionLog

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'subscription_tier', 'data_used', 'created_at')
        read_only_fields = ('id', 'created_at')

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    mobile_id = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'mobile_id', 'subscription_tier')
        extra_kwargs = {
            'username': {'validators': []},  # Disable automatic unique validation
            'mobile_id': {'validators': []}  # Disable automatic unique validation
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            mobile_id=validated_data['mobile_id'],
            subscription_tier=validated_data.get('subscription_tier', 'free')
        )
        return user

    def validate(self, data):
        # Manual unique validation
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({'username': 'Username already exists'})
        
        if data.get('mobile_id') and User.objects.filter(mobile_id=data['mobile_id']).exists():
            raise serializers.ValidationError({'mobile_id': 'Mobile ID already registered'})
        
        return data

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    mobile_id = serializers.CharField(required=False)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        
        data['user'] = user
        return data

class ProxyServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProxyServer
        fields = '__all__'

class UserSessionSerializer(serializers.ModelSerializer):
    proxy_server = ProxyServerSerializer(read_only=True)
    proxy_server_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = UserSession
        fields = '__all__'
        read_only_fields = ('id', 'start_time', 'end_time', 'data_used', 'is_active')

class ConnectionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionLog
        fields = '__all__'

class ConnectionRequestSerializer(serializers.Serializer):
    server_id = serializers.UUIDField(required=False)
    country = serializers.CharField(required=False)
    security_level = serializers.ChoiceField(
        choices=['basic', 'standard', 'high', 'maximum'],
        default='high'
    )
    enable_kill_switch = serializers.BooleanField(default=True)
    enable_dns_protection = serializers.BooleanField(default=True)