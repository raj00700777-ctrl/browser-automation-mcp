import re


# ============================================================
# ACTION CATEGORIES
# ============================================================

# Actions that can create an external or irreversible effect.
CONFIRMATION_ACTIONS = [
    "purchase",
    "buy",
    "checkout",
    "payment",
    "transfer money",
    "send message",
    "send email",
    "publish",
    "post",
    "change password",
    "change email",
    "delete",
    "remove account",
]


# Actions that should be blocked by the safety layer.
# These are intentionally limited; normal browser automation
# should remain unrestricted.
BLOCKED_ACTIONS = [
    "disable security",
    "bypass authentication",
    "bypass 2fa",
    "bypass two factor",
    "steal password",
    "steal credentials",
]


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize(text):
    """
    Normalize action text before matching.
    """

    if not isinstance(text, str):
        return ""

    text = text.lower().strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


# ============================================================
# MATCHING
# ============================================================

def _contains_phrase(text, phrase):
    """
    Match a meaningful phrase without accidentally matching
    unrelated words.

    Example:
        'delete account' -> matches
        'delete my account permanently' -> matches
    """

    text = _normalize(text)
    phrase = _normalize(phrase)

    if not text or not phrase:
        return False

    pattern = (
        r"(?<!\w)"
        + re.escape(phrase)
        + r"(?!\w)"
    )

    return re.search(
        pattern,
        text,
    ) is not None


# ============================================================
# SAFETY CHECK
# ============================================================

def safety_check(action: str):
    """
    Evaluate whether an action requires confirmation.

    Returns:

        {
            "safe": True,
            "requires_confirmation": False,
            ...
        }

    Normal browser actions are allowed.

    Consequential actions require confirmation.

    Explicitly dangerous security-bypass actions are blocked.
    """

    if not isinstance(action, str):

        return {
            "safe": False,
            "requires_confirmation": True,
            "blocked": True,
            "action": str(action),
            "matched_rules": [],
            "message": (
                "Invalid action. "
                "A valid action description is required."
            ),
        }

    normalized_action = _normalize(action)

    if not normalized_action:

        return {
            "safe": False,
            "requires_confirmation": True,
            "blocked": True,
            "action": action,
            "matched_rules": [],
            "message": (
                "Empty action cannot be executed."
            ),
        }

    # ========================================================
    # BLOCKED ACTIONS
    # ========================================================

    blocked_matches = []

    for rule in BLOCKED_ACTIONS:

        if _contains_phrase(
            normalized_action,
            rule,
        ):
            blocked_matches.append(rule)

    if blocked_matches:

        return {
            "safe": False,
            "requires_confirmation": False,
            "blocked": True,
            "action": action,
            "matched_rules": blocked_matches,
            "message": (
                "This action is blocked by the "
                "browser safety policy."
            ),
        }

    # ========================================================
    # CONFIRMATION ACTIONS
    # ========================================================

    confirmation_matches = []

    for rule in CONFIRMATION_ACTIONS:

        if _contains_phrase(
            normalized_action,
            rule,
        ):
            confirmation_matches.append(rule)

    if confirmation_matches:

        return {
            "safe": False,
            "requires_confirmation": True,
            "blocked": False,
            "action": action,
            "matched_rules": confirmation_matches,
            "message": (
                "This action can have an external, "
                "financial, account, communication, "
                "publication, or irreversible effect. "
                "User confirmation is required before "
                "execution."
            ),
        }

    # ========================================================
    # NORMAL ACTION
    # ========================================================

    return {
        "safe": True,
        "requires_confirmation": False,
        "blocked": False,
        "action": action,
        "matched_rules": [],
        "message": (
            "No confirmation-required action detected."
        ),
    }


# ============================================================
# CONVENIENCE HELPERS
# ============================================================

def is_safe(action: str):
    """
    Return True when the action can proceed without
    confirmation or blocking.
    """

    result = safety_check(action)

    return (
        result["safe"]
        and not result.get("blocked", False)
    )


def requires_confirmation(action: str):
    """
    Return True when user confirmation is required.
    """

    result = safety_check(action)

    return result.get(
        "requires_confirmation",
        False,
    )


def is_blocked(action: str):
    """
    Return True when the action is explicitly blocked.
    """

    result = safety_check(action)

    return result.get(
        "blocked",
        False,
    )


__all__ = [
        "CONFIRMATION_ACTIONS",
    "BLOCKED_ACTIONS",
    "safety_check",
    "is_safe",
    "requires_confirmation",
    "is_blocked",
]