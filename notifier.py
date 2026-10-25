#!/usr/bin/env python3
"""
Desktop Notification Module
Cross-platform notification wrapper (Linux, macOS, Windows).
"""

from system_compat import send_notification as _compat_notify

def send_notification(title: str, message: str, urgency: str = "normal", expire_ms: int = 4000, icon: str = "video-x-generic"):
    """
    Sends a native desktop notification across Linux (notify-send),
    macOS (AppleScript / Notification Center), and Windows (PowerShell Toast).
    """
    _compat_notify(title=title, message=message, urgency=urgency, expire_ms=expire_ms)
