"""Application errors rendered as {"error": {"code": ..., "message": ...}} (docs/CONTRACTS.md section 1)."""


class AppError(Exception):
    """Raise from services or routers for an expected, user-facing error.

    Example: raise AppError("window_closed", "The 24h WhatsApp window is closed.", status_code=409)
    """

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, what: str = "resource") -> None:
        super().__init__("not_found", f"{what} not found", status_code=404)
