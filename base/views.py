from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q, Count
from django.utils import timezone
from .models import User, ProxyServer, UserSession, ConnectionLog
from .serializers import *
from .proxy_manager import ProxyManager
from .authentication import create_jwt_token, create_refresh_token, verify_refresh_token
import uuid

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Create tokens using our custom JWT functions
        access_token = create_jwt_token(user)
        refresh_token = create_refresh_token(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access': access_token,
            'refresh': refresh_token,
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_user(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Create tokens using our custom JWT functions
        access_token = create_jwt_token(user)
        refresh_token = create_refresh_token(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access': access_token,
            'refresh': refresh_token,
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def refresh_token(request):
    """Refresh access token using refresh token"""
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response(
            {'error': 'Refresh token is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = verify_refresh_token(refresh_token)
        access_token = create_jwt_token(user)
        
        return Response({
            'access': access_token,
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )

class ProxyServerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProxyServerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = ProxyServer.objects.filter(is_active=True)
        
        # Filter by country if provided
        country = self.request.query_params.get('country')
        if country and country != 'Automatic':
            queryset = queryset.filter(country__iexact=country)
        
        return queryset.order_by('load', 'latency')

    @action(detail=False, methods=['get'])
    def countries(self, request):
        countries = ProxyServer.objects.filter(
            is_active=True
        ).values_list('country', flat=True).distinct()
        return Response(list(countries))

    @action(detail=False, methods=['get'])
    def optimal(self, request):
        country = request.query_params.get('country')
        server = ProxyManager.get_optimal_server(country=country)
        if server:
            serializer = self.get_serializer(server)
            return Response(serializer.data)
        return Response({'error': 'No servers available'}, status=status.HTTP_404_NOT_FOUND)

class UserSessionViewSet(viewsets.ModelViewSet):
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user).order_by('-start_time')

    def create(self, request):
        serializer = ConnectionRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                proxy_manager = ProxyManager()
                session = proxy_manager.create_session(
                    user=request.user,
                    server_id=serializer.validated_data.get('server_id'),
                    country=serializer.validated_data.get('country'),
                    security_level=serializer.validated_data.get('security_level', 'high'),
                    client_ip=self.get_client_ip(request),
                    config={
                        'enable_kill_switch': serializer.validated_data.get('enable_kill_switch', True),
                        'enable_dns_protection': serializer.validated_data.get('enable_dns_protection', True),
                    }
                )
                session_serializer = UserSessionSerializer(session)
                return Response(session_serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        try:
            session = self.get_object()
            proxy_manager = ProxyManager()
            proxy_manager.end_session(session)
            return Response({'status': 'disconnected'})
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def active(self, request):
        active_session = UserSession.objects.filter(
            user=request.user, 
            is_active=True
        ).first()
        if active_session:
            serializer = self.get_serializer(active_session)
            return Response(serializer.data)
        return Response({'detail': 'No active session'}, status=status.HTTP_404_NOT_FOUND)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['get'])
    def profile(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        total_sessions = UserSession.objects.filter(user=request.user).count()
        active_session = UserSession.objects.filter(user=request.user, is_active=True).exists()
        total_data = request.user.data_used
        
        return Response({
            'total_sessions': total_sessions,
            'is_connected': active_session,
            'total_data_used': total_data,
            'subscription_tier': request.user.subscription_tier
        })