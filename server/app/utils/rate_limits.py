# Per-route rate limits. Upload (M3) and matching (M4) are the expensive routes
# (CV parsing + NLP inference); they get the tight limits. Applied as
# @limiter.limit(...) decorators on the route handlers in those modules.
UPLOAD_LIMIT = "10 per minute"
MATCHING_LIMIT = "20 per minute"