"""Structured API errors and Flask error handlers.

Every error returned to a client has the shape::

    {"error": {"code": "...", "message": "...", "details": {...}}}

Internal exception details and tracebacks are logged server-side only.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ArtifactError(RuntimeError):
    """Raised during startup when a required model/data artifact is invalid."""


class ApiError(Exception):
    """An expected, client-facing API error."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict:
        payload: dict = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


_HTTP_ERROR_MAP = {
    400: ("BAD_REQUEST", "The request could not be understood."),
    404: ("NOT_FOUND", "The requested resource was not found."),
    405: ("METHOD_NOT_ALLOWED", "The HTTP method is not allowed for this endpoint."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "The request media type is not supported."),
}

_INTERNAL_MESSAGE = "An unexpected server error occurred. The details were logged server-side."


def register_error_handlers(app: Flask) -> None:
    logger = logging.getLogger("enervision.errors")

    @app.errorhandler(ApiError)
    def _handle_api_error(error: ApiError):
        if error.status_code >= 500:
            logger.error("API error %s: %s", error.code, error.message)
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def _handle_http_error(error: HTTPException):
        code, message = _HTTP_ERROR_MAP.get(
            error.code or 500,
            ("HTTP_ERROR", error.description or "The request failed."),
        )
        return jsonify({"error": {"code": code, "message": message}}), error.code or 500

    @app.errorhandler(Exception)
    def _handle_unexpected_error(error: Exception):
        logger.exception("Unhandled backend exception: %s", error)
        return (
            jsonify({"error": {"code": "INTERNAL_ERROR", "message": _INTERNAL_MESSAGE}}),
            500,
        )
