"""Short reference codes for lead-initiated chats (CONTRACTS section 5).

Stand-in written in P3-3 (the assisted-mode assistant link ends with "#<ref_code>"). P0-2 owns this file.
"""

import secrets

# No look-alikes: no 0/O, 1/I/L.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 6


def new_ref_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
