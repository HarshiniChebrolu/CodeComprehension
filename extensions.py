from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

# Global Flask-Limiter instance with configured defaults
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[Config.RATELIMIT_DEFAULT],
    storage_uri="memory://",
    strategy="fixed-window"
)
