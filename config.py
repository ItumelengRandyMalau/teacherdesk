
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGO_URI = os.getenv("MONGO_URI")

    # Prevent JavaScript from accessing the session cookie.
    SESSION_COOKIE_HTTPONLY = True

    # Restrict when browsers send session cookies cross-site.
    SESSION_COOKIE_SAMESITE = "Lax"

    # Require HTTPS for session cookies on Render.
    SESSION_COOKIE_SECURE = os.getenv("RENDER", "").lower() == "true"
