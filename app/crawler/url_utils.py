from urllib.parse import urljoin, urlsplit, urlunsplit

from app.models.seed_source import SeedSource


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Resolve and normalize an HTTP(S) URL, removing its fragment.

    Invalid or unsupported URLs raise ``ValueError`` so callers can decide
    whether to reject user input or skip a discovered link.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must not be empty.")
    if any(character.isspace() or ord(character) < 32 for character in url):
        raise ValueError("URL must not contain whitespace or control characters.")

    candidate = urljoin(base_url, url) if base_url is not None else url
    try:
        parsed = urlsplit(candidate)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL is malformed.") from error

    if scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported.")
    if hostname is None or not parsed.netloc:
        raise ValueError("URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not supported.")

    normalized_hostname = hostname.lower()
    if ":" in normalized_hostname:
        normalized_hostname = f"[{normalized_hostname}]"
    if port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        normalized_hostname = f"{normalized_hostname}:{port}"

    return urlunsplit(
        (
            scheme,
            normalized_hostname,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )


def is_url_in_scope(url: str, source: SeedSource) -> bool:
    """Check exact hostname and at least one configured URL path prefix.

    The configured start URL is always allowed, even when its path is broader
    than the prefixes used to limit links discovered from that page.
    """
    try:
        normalized_url = normalize_url(url)
        normalized_start = normalize_url(source.start_url)
    except ValueError:
        return False

    parsed_url = urlsplit(normalized_url)
    if (parsed_url.hostname or "").lower() != source.domain.lower():
        return False
    if normalized_url == normalized_start:
        return True

    for raw_prefix in source.allowed_url_prefixes:
        try:
            prefix = urlsplit(normalize_url(raw_prefix))
        except ValueError:
            continue

        if (
            parsed_url.scheme != prefix.scheme
            or parsed_url.netloc != prefix.netloc
        ):
            continue

        prefix_path = prefix.path.rstrip("/") or "/"
        if prefix_path == "/":
            return True
        if (
            parsed_url.path == prefix_path
            or parsed_url.path.startswith(f"{prefix_path}/")
        ):
            return True
    return False
