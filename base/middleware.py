class DebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Print request details for debugging
        print(f"=== REQUEST ===")
        print(f"Path: {request.path}")
        print(f"Method: {request.method}")
        print(f"Headers: {dict(request.headers)}")
        if request.body:
            try:
                print(f"Body: {request.body.decode('utf-8')}")
            except:
                print(f"Body: [binary data]")
        
        response = self.get_response(request)
        
        print(f"=== RESPONSE ===")
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        if hasattr(response, 'data'):
            print(f"Data: {response.data}")
        
        return response