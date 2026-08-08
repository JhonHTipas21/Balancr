from balancr.api.app import app
from balancr.api.router import router

# Register API routes
app.include_router(router)

__all__ = ["app"]
