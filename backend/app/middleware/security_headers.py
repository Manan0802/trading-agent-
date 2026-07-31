"""Response headers a browser enforces on our behalf.

This is an API, not a site: it serves JSON, never HTML, and the frontend is a
separate static origin. So the header set is deliberately small. A long CSP
copied from a frontend guide would be theatre here -- there is no document for
it to govern.

What is left is the part that still applies to a JSON endpoint: do not let a
browser guess a content type, do not let the app be framed, do not leak the
referrer to third parties, and require HTTPS once we are actually on it.
"""
from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_HEADERS = {
    # A JSON response sniffed as HTML is how a reflected value becomes XSS.
    "X-Content-Type-Options": "nosniff",
    # Nothing here is meant to be embedded.
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # No API response needs a camera, a microphone or a location.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    # There is no document to govern, so everything is denied rather than
    # allowed narrowly. This matters for the error pages a browser may render.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

# Two years, which is the minimum for preload lists. Only sent over HTTPS: on
# plain HTTP it is ignored by browsers anyway, and sending it in development
# would pin localhost to HTTPS in the developer's browser for two years.
_HSTS = "max-age=63072000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, production: bool) -> None:
        super().__init__(app)
        self._production = production

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in _HEADERS.items():
            response.headers.setdefault(header, value)
        if self._production and request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", _HSTS)
        return response
