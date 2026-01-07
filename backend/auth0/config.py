import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "evoqueacademia.us.auth0.com")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "https://erp-api.evoquefitness.com.br")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET", "")
AUTH0_REQUIRE_EMAIL_VERIFIED = os.getenv("AUTH0_REQUIRE_EMAIL_VERIFIED", "False").lower() in ("true", "1", "yes")

# Generate dynamic AUTH0_CALLBACK_URL based on frontend URL
_frontend_url = os.getenv("FRONTEND_URL", "").strip()
_production_domain = os.getenv("PRODUCTION_DOMAIN", "").strip()

if _frontend_url:
    AUTH0_CALLBACK_URL = f"{_frontend_url}/auth/callback"
elif _production_domain:
    AUTH0_CALLBACK_URL = f"https://{_production_domain}/auth/callback"
else:
    AUTH0_CALLBACK_URL = "http://localhost:3005/auth/callback"

# Machine-to-Machine (M2M) Credentials for Management API
AUTH0_M2M_CLIENT_ID = os.getenv("AUTH0_M2M_CLIENT_ID", "")
AUTH0_M2M_CLIENT_SECRET = os.getenv("AUTH0_M2M_CLIENT_SECRET", "")

# Auth0 URLs
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"
AUTH0_JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
AUTH0_TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"
AUTH0_MANAGEMENT_API_URL = f"https://{AUTH0_DOMAIN}/api/v2/"

# Validate configuration
print(f"\n[AUTH0-CONFIG] 🔧 Auth0 Configuration Loaded:")
print(f"[AUTH0-CONFIG] Domain: {AUTH0_DOMAIN}")
print(f"[AUTH0-CONFIG] Audience: {AUTH0_AUDIENCE}")
print(f"[AUTH0-CONFIG] Callback URL: {AUTH0_CALLBACK_URL}")
print(f"[AUTH0-CONFIG] Client ID: {AUTH0_CLIENT_ID[:20] + '...' if AUTH0_CLIENT_ID else '❌ NOT SET'}")
print(f"[AUTH0-CONFIG] Client Secret: {'✓ SET' if AUTH0_CLIENT_SECRET else '❌ NOT SET'}")
print(f"[AUTH0-CONFIG] M2M Client ID: {'✓ SET' if AUTH0_M2M_CLIENT_ID else '❌ NOT SET'}")
print(f"[AUTH0-CONFIG] M2M Secret: {'✓ SET' if AUTH0_M2M_CLIENT_SECRET else '❌ NOT SET'}\n")

if not AUTH0_M2M_CLIENT_ID or not AUTH0_M2M_CLIENT_SECRET:
    print("⚠️  WARNING: Auth0 M2M credentials not configured. Management API operations will fail.")
