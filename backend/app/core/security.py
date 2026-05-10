from fastapi import Depends


def optional_auth_placeholder() -> None:
    """Reserved for JWT/API-key authentication in a later release."""
    return None


OptionalAuth = Depends(optional_auth_placeholder)
