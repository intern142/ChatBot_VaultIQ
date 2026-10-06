from app.main import app
print('Backend routes:')
for route in app.routes:
    if hasattr(route, 'methods'):
        print(f'  {route.methods} {getattr(route, "path", str(route))}')