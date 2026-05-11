"""
Milk Tea Shop Management System
Controller layer - application logic, permissions, and session management.
"""

from datetime import datetime, timedelta
from utils import SESSION_TIMEOUT_SECONDS, ROLE_PERMISSIONS, ROLE_ACTIONS

# ─────────────────────────────────────────────
#  CONTROLLER UTILITY FUNCTIONS
# ─────────────────────────────────────────────

def get_allowed_sections(current_user):
    """Get list of sections allowed for the current user based on their role."""
    if not current_user:
        return []
    return ROLE_PERMISSIONS.get(current_user.get("role", ""), [])


def can_access_section(current_user, key):
    """Check if the current user can access a specific section."""
    return key in get_allowed_sections(current_user)


def has_permission(current_user, action):
    """Check if the current user has permission to perform a specific action."""
    if not current_user:
        return False
    perms = ROLE_ACTIONS.get(current_user.get("role", ""), [])
    return "all" in perms or action in perms


def check_session_expired(last_activity_time):
    """Check if session has expired based on last activity time."""
    return datetime.now() - last_activity_time > timedelta(seconds=SESSION_TIMEOUT_SECONDS)


def get_session_remaining_seconds(last_activity_time):
    """Get remaining seconds before session expires."""
    elapsed = datetime.now() - last_activity_time
    remaining = SESSION_TIMEOUT_SECONDS - int(elapsed.total_seconds())
    return max(0, remaining)
