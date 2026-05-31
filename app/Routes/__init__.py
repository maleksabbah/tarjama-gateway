from app.Routes.AuthRoutes import router as auth_router
from app.Routes.UserRoutes import router as user_router
from app.Routes.JobRoutes import router as job_router
from app.Routes.FileRoutes import router as file_router

__all__ = [
    "auth_router",
    "user_router",
    "job_router",
    "file_router",
]