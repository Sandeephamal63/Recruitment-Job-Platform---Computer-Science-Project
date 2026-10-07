from .applications import applications_bp
from .auth import auth_bp
from .jobs import jobs_bp
from .matching import matching_bp

__all__ = ["auth_bp", "jobs_bp", "applications_bp", "matching_bp"]