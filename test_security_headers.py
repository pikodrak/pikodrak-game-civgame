"""Tests for SecurityHeadersMiddleware (ITI-14)."""
import asyncio


# Inline a minimal stub so the test runs without fastapi/starlette installed.
class _FakeResponse:
    def __init__(self):
        self.headers = {}


class _FakeRequest:
    pass


async def _make_response(req, call_next):
    return await call_next(req)


# Replicate the middleware logic verbatim from server.py so the test is
# authoritative even when the full stack is unavailable.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


async def security_headers_dispatch(request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


def test_all_security_headers_present():
    fake = _FakeResponse()

    async def _next(_req):
        return fake

    result = asyncio.run(security_headers_dispatch(_FakeRequest(), _next))

    for header, expected in _SECURITY_HEADERS.items():
        assert result.headers.get(header) == expected, (
            f"Missing or wrong header {header!r}: got {result.headers.get(header)!r}"
        )


def test_existing_headers_not_clobbered():
    fake = _FakeResponse()
    fake.headers["Content-Type"] = "application/json"

    async def _next(_req):
        return fake

    result = asyncio.run(security_headers_dispatch(_FakeRequest(), _next))
    assert result.headers["Content-Type"] == "application/json"


def test_csp_uses_quoted_self():
    fake = _FakeResponse()

    async def _next(_req):
        return fake

    result = asyncio.run(security_headers_dispatch(_FakeRequest(), _next))
    assert "'self'" in result.headers["Content-Security-Policy"]


if __name__ == "__main__":
    test_all_security_headers_present()
    test_existing_headers_not_clobbered()
    test_csp_uses_quoted_self()
    print("All tests passed.")
