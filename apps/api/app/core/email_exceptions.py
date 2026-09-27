from __future__ import annotations

from app.core.exceptions import AppError


class EmailDeliveryUnavailable(AppError):
    code = "EMAIL_DELIVERY_UNAVAILABLE"
    status_code = 503
    message = "Transactional email delivery is unavailable."
