import requests
import json
from typing import Optional, Dict, Any, List
from .config import (
    AUTH0_DOMAIN,
    AUTH0_M2M_CLIENT_ID,
    AUTH0_M2M_CLIENT_SECRET,
    AUTH0_AUDIENCE,
    AUTH0_TOKEN_URL,
    AUTH0_MANAGEMENT_API_URL,
)


class Auth0ManagementClient:
    """Client for Auth0 Management API"""
    
    def __init__(self):
        self.domain = AUTH0_DOMAIN
        self.client_id = AUTH0_M2M_CLIENT_ID
        self.client_secret = AUTH0_M2M_CLIENT_SECRET
        self.base_url = AUTH0_MANAGEMENT_API_URL
        self.token = None
        self.token_expires_at = 0
    
    def _get_management_token(self) -> str:
        """Get M2M access token for Management API"""
        try:
            response = requests.post(
                AUTH0_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "audience": self.base_url,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )
            response.raise_for_status()
            
            data = response.json()
            self.token = data.get("access_token")
            
            if not self.token:
                raise Exception("No access token in response")
            
            print("✅ Auth0 Management API token obtained")
            return self.token
            
        except Exception as e:
            print(f"❌ Error getting Auth0 Management token: {str(e)}")
            raise
    
    def _get_headers(self) -> dict:
        """Get headers with valid access token"""
        if not self.token:
            self._get_management_token()
        
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email
        
        Args:
            email: User email address
            
        Returns:
            User data dict or None if not found
        """
        try:
            headers = self._get_headers()
            url = f"{self.base_url}users-by-email"
            
            response = requests.get(
                url,
                headers=headers,
                params={"email": email},
                timeout=10,
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            users = response.json()
            
            return users[0] if users else None
            
        except Exception as e:
            print(f"❌ Error getting user by email: {str(e)}")
            raise
    
    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user by ID
        
        Args:
            user_id: Auth0 user ID
            
        Returns:
            User data dict
        """
        try:
            headers = self._get_headers()
            url = f"{self.base_url}users/{user_id}"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            print(f"❌ Error getting user: {str(e)}")
            raise
    
    def create_user(
        self,
        email: str,
        password: str,
        given_name: str,
        family_name: str,
        user_metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Create a new user
        
        Args:
            email: User email
            password: User password
            given_name: First name
            family_name: Last name
            user_metadata: Additional user metadata
            
        Returns:
            Created user data
        """
        try:
            headers = self._get_headers()
            url = f"{self.base_url}users"
            
            data = {
                "email": email,
                "password": password,
                "given_name": given_name,
                "family_name": family_name,
                "connection": "Username-Password-Authentication",
                "email_verified": False,
                "user_metadata": user_metadata or {},
            }
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            
            user = response.json()
            print(f"✅ User created: {email}")
            return user
            
        except Exception as e:
            print(f"❌ Error creating user: {str(e)}")
            raise
    
    def update_user(
        self,
        user_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update user
        
        Args:
            user_id: Auth0 user ID
            data: Data to update
            
        Returns:
            Updated user data
        """
        try:
            headers = self._get_headers()
            url = f"{self.base_url}users/{user_id}"
            
            response = requests.patch(
                url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            
            user = response.json()
            print(f"✅ User updated: {user_id}")
            return user
            
        except Exception as e:
            print(f"❌ Error updating user: {str(e)}")
            raise
    
    def assign_role_to_user(
        self,
        user_id: str,
        role_id: str,
    ) -> None:
        """
        Assign role to user
        
        Args:
            user_id: Auth0 user ID
            role_id: Auth0 role ID
        """
        try:
            headers = self._get_headers()
            url = f"{self.base_url}users/{user_id}/roles"
            
            data = {
                "roles": [role_id],
            }
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            
            print(f"✅ Role assigned to user: {user_id}")
            
        except Exception as e:
            print(f"❌ Error assigning role: {str(e)}")
            raise
    
    def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get user roles
        
        Args:
            user_id: Auth0 user ID
            
        Returns:
            List of role objects
        """
        try:
            headers = self._get_headers()
            url = f"{self.base_url}users/{user_id}/roles"
            
            response = requests.get(
                url,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            print(f"❌ Error getting user roles: {str(e)}")
            raise
    
    def delete_user(self, user_id: str) -> None:
        """
        Delete user
        
        Args:
            user_id: Auth0 user ID
        """
        try:
            headers = self._get_headers()
            url = f"{self.base_url}users/{user_id}"
            
            response = requests.delete(
                url,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            
            print(f"✅ User deleted: {user_id}")
            
        except Exception as e:
            print(f"❌ Error deleting user: {str(e)}")
            raise


# Global client instance
_auth0_client = None


def get_auth0_client() -> Auth0ManagementClient:
    """Get or create Auth0 Management client"""
    global _auth0_client
    if _auth0_client is None:
        _auth0_client = Auth0ManagementClient()
    return _auth0_client
