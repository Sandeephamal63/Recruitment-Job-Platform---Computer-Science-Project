from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config

jwt = JWTManager()

# Rate limiting. Memory-backed in dev; swap to a distributed storage (Redis) in
# prod/M6. Named per-route limits live in utils/rate_limits.py — upload (M3)
# and matching (M4) are the expensive routes and get the tight limits there.
# Defined before the blueprints import so route modules can use @limiter.limit.
limiter = Limiter(key_func=get_remote_address, default_limits=["240 per hour"])

from .blueprints.applications import applications_bp
from .blueprints.auth import auth_bp
from .blueprints.jobs import jobs_bp
from .blueprints.matching import matching_bp
from .blueprints.profile import profile_bp
from .blueprints.skills import skills_bp
from .db import ensure_indexes, get_db, ping_db
from .repositories.application_repository import ApplicationRepository
from .repositories.avatar_repository import AvatarRepository
from .repositories.candidate_recommendation_repository import (
    CandidateRecommendationRepository,
)
from .repositories.cv_repository import CVRepository
from .repositories.job_repository import JobRepository
from .repositories.logo_repository import LogoRepository
from .repositories.match_result_repository import MatchResultRepository
from .repositories.refresh_token_repository import RefreshTokenRepository
from .repositories.user_repository import UserRepository
from .services.application_service import ApplicationService
from .services.auth_service import AuthService
from .services.job_service import JobService
from .services.match_service import MatchService
from .services.profile_service import ProfileService
from .services.recommendation_service import RecommendationService
from .utils.errors import register_error_handlers


def create_app(config: type[Config] = Config) -> Flask:
    """Build the Flask application. Every extension is bound inside the
    factory so the app object is never a global."""
    app = Flask(__name__)
    app.config.from_object(config)

    # Only the Vite dev origin may call the API cross-origin (bare-metal dev;
    # the compose path is single-origin through the Vite proxy).
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    jwt.init_app(app)
    limiter.init_app(app)
    register_error_handlers(app, jwt)

    # Blueprint URL space is fixed from M0 so later modules extend, not reorganize.
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(applications_bp, url_prefix="/api/applications")
    app.register_blueprint(matching_bp, url_prefix="/api/matching")
    app.register_blueprint(skills_bp, url_prefix="/api/skills")

    # Domain services are created once per factory and reached by blueprints
    # through ``current_app.extensions`` — routes never construct repositories.
    with app.app_context():
        db = get_db()
        job_repo = JobRepository(db)
        application_repo = ApplicationRepository(db)
        match_result_repo = MatchResultRepository(db)
        user_repo = UserRepository(db)
        cv_repo = CVRepository(db)
        logo_repo = LogoRepository(db)
        avatar_repo = AvatarRepository(db)
        job_service = JobService(job_repo, user_repo, application_repo, match_result_repo)
        app.extensions["services"] = {
            "auth": AuthService(user_repo, RefreshTokenRepository(db)),
            "profile": ProfileService(
                user_repo, cv_repo, job_repo, logo_repo, application_repo, avatar_repo
            ),
            "jobs": job_service,
            "applications": ApplicationService(
                application_repo,
                job_repo,
                cv_repo,
                match_result_repo,
                user_repo,
                db,
            ),
            "matching": MatchService(application_repo, job_repo, match_result_repo, user_repo),
            # The proactive recommender shares the per-application matcher's
            # blueprint and scorer, and reuses JobService's public employer join
            # rather than growing a second one.
            "recommendations": RecommendationService(
                job_repo,
                user_repo,
                CandidateRecommendationRepository(db),
                job_service,
            ),
        }

    @app.get("/api/health")
    def health():
        """Report service + DB status. Never hard-fails on a missing DB so the
        API stays observable during MongoDB downtime."""
        try:
            ping_db()
            db_status = "connected"
        except Exception:
            db_status = "unavailable"
        return jsonify(
            {
                "status": "ok",
                "service": app.config["SERVICE_NAME"],
                "version": app.config["VERSION"],
                "db": db_status,
            }
        )

    _ensure_indexes(app)
    return app


def _ensure_indexes(app: Flask) -> None:
    """Best-effort index creation; a missing DB must not break the factory
    (CI's create_app() smoke runs without Mongo)."""
    with app.app_context():
        try:
            ensure_indexes()
        except Exception:
            app.logger.warning("Skipping index creation: database unavailable")