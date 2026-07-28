from types import SimpleNamespace

from apps.api.app.security import RateLimitMiddleware


def request(peer: str | None, forwarded: str | None):
    headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
    return SimpleNamespace(client=SimpleNamespace(host=peer) if peer else None, headers=headers)


def middleware(hops: int) -> RateLimitMiddleware:
    return RateLimitMiddleware(app=lambda *_args, **_kwargs: None, trusted_proxy_hops=hops)


def test_forwarded_for_is_ignored_without_trusted_proxy() -> None:
    assert middleware(0)._client_key(request("10.0.0.1", "203.0.113.7")) == "10.0.0.1"


def test_trusted_proxy_hops_selects_client_entry() -> None:
    assert middleware(1)._client_key(request("10.0.0.1", "203.0.113.7")) == "203.0.113.7"
    assert middleware(2)._client_key(request("10.0.0.10", "203.0.113.7, 10.0.0.9")) == "203.0.113.7"


def test_short_forwarded_chain_falls_back_to_peer() -> None:
    assert middleware(3)._client_key(request("10.0.0.1", "203.0.113.7")) == "10.0.0.1"
