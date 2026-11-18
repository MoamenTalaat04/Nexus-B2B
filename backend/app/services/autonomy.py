"""Autonomy levels (CONTRACTS section 9, P3-3): how much the owner trusts the agent to send on its own.

approve_all          → every outbound message waits for the owner's approval (the default)
approve_first_touch  → only first touches wait; follow-ups go out on their own
autopilot            → nothing waits (the daily cap, quiet hours and opt-outs still apply)

Assisted messages (first_touch_mode="assisted") never need approval: the owner sends them personally.
"""

from app.models.enums import AutonomyMode, OutreachPurpose
from app.models.tenants import BusinessSettings


def needs_approval(settings: BusinessSettings, purpose: OutreachPurpose) -> bool:
    mode = AutonomyMode(settings.autonomy_mode)
    if mode == AutonomyMode.APPROVE_ALL:
        return True
    if mode == AutonomyMode.APPROVE_FIRST_TOUCH:
        return purpose == OutreachPurpose.FIRST_TOUCH
    return False
