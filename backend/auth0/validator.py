import requests
from functools import lru_cache
from jose import jwt, JWTError, jwk
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import (
    AUTH0_DOMAIN,
    AUTH0_AUDIENCE,
    AUTH0_ISSUER,
    AUTH0_JWKS_URL,
)

security = HTTPBearer()


@lru_cache(maxsize=1)
def get_jwks():
    """Fetch and cache JSON Web Key Set from Auth0"""
    try:
        response = requests.get(AUTH0_JWKS_URL, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching JWKS from Auth0: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch Auth0 public keys"
        )


def get_signing_key(kid: str) -> dict:
    """Get the signing key from JWKS by key ID"""
    jwks = get_jwks()
    
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    
    raise HTTPException(
        status_code=401,
        detail="Unable to find a signing key that matches"
    )


def verify_auth0_token(token: str) -> dict:
    """
    Verify and decode Auth0 JWT token

    Args:
        token: The JWT token from Authorization header

    Returns:
        dict: Decoded token payload

    Raises:
        HTTPException: If token is invalid
    """
    try:
        print(f"\n[JWT-VALIDATOR] Starting JWT verification...")
        print(f"[JWT-VALIDATOR] Token length: {len(token)}")
        print(f"[JWT-VALIDATOR] Token (first 50 chars): {token[:50]}...")

        # Get the unverified header to extract the key ID
        print(f"[JWT-VALIDATOR] Extracting unverified header...")
        unverified_header = jwt.get_unverified_header(token)
        print(f"[JWT-VALIDATOR] Unverified header: {unverified_header}")

        if "kid" not in unverified_header:
            print(f"[JWT-VALIDATOR] ❌ 'kid' not found in header")
            raise HTTPException(
                status_code=401,
                detail="Invalid token header"
            )

        # Get the signing key
        print(f"[JWT-VALIDATOR] Fetching signing key with kid: {unverified_header['kid']}")
        signing_key_dict = get_signing_key(unverified_header["kid"])
        print(f"[JWT-VALIDATOR] ✓ Signing key obtained")
        print(f"[JWT-VALIDATOR] Signing key data: {signing_key_dict.get('kty')}, kid={signing_key_dict.get('kid')}")

        # Build the key for verification using X.509 certificate
        print(f"[JWT-VALIDATOR] Converting JWK to RSA key...")
        try:
            # Try to extract public key from X.509 certificate (x5c[0])
            if "x5c" in signing_key_dict and signing_key_dict["x5c"]:
                cert_data = base64.b64decode(signing_key_dict["x5c"][0])
                cert = x509.load_der_x509_certificate(cert_data, default_backend())
                public_key = cert.public_key()
                # Convert to PEM format for python-jose
                key = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                print(f"[JWT-VALIDATOR] ✓ RSA key extracted from X.509 certificate")
            else:
                # Fallback: try to construct from JWK
                key = jwk.construct(signing_key_dict, 'RSA')
                print(f"[JWT-VALIDATOR] ✓ RSA key created successfully from JWK")
        except Exception as e:
            print(f"[JWT-VALIDATOR] ❌ Failed to construct RSA key: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Failed to construct RSA key from JWK"
            )

        # Decode and verify the token
        print(f"[JWT-VALIDATOR] Verifying token with:")
        print(f"[JWT-VALIDATOR]   - algorithms: RS256")
        print(f"[JWT-VALIDATOR]   - audience: {AUTH0_AUDIENCE}")
        print(f"[JWT-VALIDATOR]   - issuer: {AUTH0_ISSUER}")

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=AUTH0_ISSUER,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        print(f"[JWT-VALIDATOR] ✓ Token verified successfully!")
        print(f"[JWT-VALIDATOR] Payload keys: {list(payload.keys())}")
        print(f"[JWT-VALIDATOR] Email: {payload.get('email', 'NOT FOUND')}")
        print(f"[JWT-VALIDATOR] Email verified: {payload.get('email_verified', 'NOT FOUND')}")
        print(f"[JWT-VALIDATOR] Subject (sub): {payload.get('sub', 'NOT FOUND')}")

        return payload

    except JWTError as e:
        # Catch all JWT errors including claims validation
        error_msg = str(e).lower()
        print(f"\n[JWT-VALIDATOR] ❌ JWTError occurred")
        print(f"[JWT-VALIDATOR] Error type: {type(e).__name__}")
        print(f"[JWT-VALIDATOR] Error message: {str(e)}")

        if "claims" in error_msg or "aud" in error_msg or "iss" in error_msg:
            print(f"[JWT-VALIDATOR] ❌ Token claims validation failed")
            raise HTTPException(
                status_code=401,
                detail="Invalid token claims"
            )
        else:
            print(f"[JWT-VALIDATOR] ❌ JWT validation failed")
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
    except Exception as e:
        print(f"\n[JWT-VALIDATOR] ❌ Unexpected error during token verification")
        print(f"[JWT-VALIDATOR] Error type: {type(e).__name__}")
        print(f"[JWT-VALIDATOR] Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=401,
            detail="Token verification failed"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to verify Auth0 token in protected routes
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user": user}
    """
    token = credentials.credentials
    return verify_auth0_token(token)
