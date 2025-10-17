from rest_framework import authentication, exceptions
from django.contrib.auth import get_user_model
import jwt
from django.conf import settings
import datetime
import json

User = get_user_model()

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return None

        try:
            # Extract token from "Bearer <token>"
            prefix, token = auth_header.split(' ')
            if prefix.lower() != 'bearer':
                return None
        except ValueError:
            return None

        try:
            # Decode and verify JWT token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            
            # Check if token is expired
            if 'exp' in payload:
                exp_timestamp = payload['exp']
                current_timestamp = datetime.datetime.now(datetime.timezone.utc).timestamp()
                if exp_timestamp < current_timestamp:
                    raise exceptions.AuthenticationFailed('Token has expired')
            
            # Get user from token
            user_id = payload.get('user_id')
            if not user_id:
                raise exceptions.AuthenticationFailed('Invalid token')
            
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise exceptions.AuthenticationFailed('User not found')
                
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except Exception as e:
            print(f"JWT Authentication error: {e}")
            raise exceptions.AuthenticationFailed('Authentication failed')

def create_jwt_token(user):
    """Create JWT token for user"""
    payload = {
        'user_id': str(user.id),  # Ensure user_id is string for UUID
        'username': user.username,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
        'iat': datetime.datetime.now(datetime.timezone.utc)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token

def create_refresh_token(user):
    """Create refresh token for user"""
    payload = {
        'user_id': str(user.id),  # Ensure user_id is string for UUID
        'type': 'refresh',
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        'iat': datetime.datetime.now(datetime.timezone.utc)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token

def verify_refresh_token(token):
    """Verify refresh token and return user"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        
        if payload.get('type') != 'refresh':
            raise exceptions.AuthenticationFailed('Invalid token type')
            
        user_id = payload.get('user_id')
        if not user_id:
            raise exceptions.AuthenticationFailed('Invalid token')
            
        user = User.objects.get(id=user_id)
        return user
        
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed('Refresh token has expired')
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailed('Invalid refresh token')
    except User.DoesNotExist:
        raise exceptions.AuthenticationFailed('User not found')