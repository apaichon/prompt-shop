"""Fixed-origin HTTP collector. Never saves cookie/CSRF/password/raw error values."""
from dataclasses import dataclass
import http.cookiejar
import ipaddress
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from .contracts import require, number


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class Response:
    status: int
    body: object
    headers: dict
    duration_ms: float
    error: str | None = None


class Client:
    def __init__(self, origin, *, local=False, insecure_tls=False, pace=1.05):
        parsed = urllib.parse.urlsplit(origin)
        loopback = parsed.hostname == "localhost"
        try:
            loopback |= ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            pass
        require(parsed.scheme in ("https", "http") and parsed.netloc and not parsed.username and not parsed.password and parsed.path in ("", "/") and not parsed.query and not parsed.fragment, "use a credential-free candidate origin")
        require(parsed.scheme == "https" or local and loopback, "HTTP is limited to explicitly declared local loopback")
        require(not insecure_tls or local and loopback and parsed.scheme == "https", "insecure TLS is limited to explicit local fixtures")
        require(number(pace) and pace >= 0 and (local or pace >= 1.05), "deployed request pacing must respect 60/min admission")
        self.origin = origin.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        context = ssl._create_unverified_context() if insecure_tls else ssl.create_default_context()
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(self.cookies), urllib.request.HTTPSHandler(context=context))
        self.pace, self.last = pace, 0.0
        self.environment = "local_fixture" if local else "deployed"

    def request(self, method, path, body=None, headers=None):
        require(path.startswith("/") and not path.startswith("//") and not urllib.parse.urlsplit(path).netloc, "fixed relative route required")
        wait = self.pace-(time.monotonic()-self.last)
        if wait > 0:
            time.sleep(wait)
        raw = json.dumps(body, allow_nan=False).encode() if body is not None else None
        values = {"Accept": "application/json", "Origin": self.origin}
        if raw is not None:
            values["Content-Type"] = "application/json"
        if headers:
            require(not any(k.lower() in ("host", "authorization", "proxy-authorization") for k in headers), "host/credential override forbidden")
            values.update(headers)
        request = urllib.request.Request(self.origin+path, data=raw, method=method, headers=values)
        start = time.monotonic()
        self.last = start
        try:
            response = self.opener.open(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        except (urllib.error.URLError, TimeoutError, OSError):
            return Response(0, None, {}, (time.monotonic()-start)*1000, "transport_unavailable")
        with response:
            # Read at most 1MB. Content/cookie headers are intentionally not returned.
            try:
                data = response.read(1_000_001)
            except (TimeoutError, OSError):
                return Response(response.status, None, {}, (time.monotonic()-start)*1000, "transport_unavailable")
            headers_out = {"request_id": response.headers.get("X-Request-ID", ""), "retry_after": response.headers.get("Retry-After", "")}
            if not re.fullmatch(r"[A-Za-z0-9_-]{0,128}", headers_out["request_id"]):
                headers_out["request_id"] = ""
            if not re.fullmatch(r"[0-9]{0,6}", headers_out["retry_after"]):
                headers_out["retry_after"] = ""
            try:
                value = json.loads(data) if len(data) <= 1_000_000 else None
            except (ValueError, UnicodeDecodeError):
                value = None
            return Response(response.status, value, headers_out, (time.monotonic()-start)*1000, None if value is not None or response.status == 204 else "invalid_json")

    def cookie_attributes(self, name):
        cookie = next((c for c in self.cookies if c.name == name), None)
        if cookie is None:
            return None
        attributes = {str(k).lower(): v for k, v in cookie._rest.items()}
        return {"name": cookie.name, "secure": cookie.secure, "http_only": "httponly" in attributes,
                "same_site": attributes.get("samesite"), "path": cookie.path, "host_only": not cookie.domain_specified,
                "absolute_expiry_present": cookie.expires is not None}
