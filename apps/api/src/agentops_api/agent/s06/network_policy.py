"""Pure destination policy; no network execution."""

import ipaddress
import re

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, urljoin

from .errors import AcquisitionError, ErrorCode


LABEL = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)

DENIED_V6 = tuple(
    ipaddress.ip_network(value)
    for value in (
        "64:ff9b::/96",
        "64:ff9b:1::/48",
        "2001::/32",
        "2002::/16",
        "2001:db8::/32",
        "3fff::/20",
        "fec0::/10",
    )
)


@dataclass(frozen=True, slots=True)
class Destination:
    url: str
    scheme: str
    host: str
    port: int


@dataclass(frozen=True, slots=True)
class BoundDestination:
    destination: Destination
    ip: str


def deny():
    raise AcquisitionError(
        ErrorCode.UNSAFE_DESTINATION
    )


def public_ip(value: str) -> str:
    if type(value) is not str or "%" in value:
        deny()

    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        deny()

    if (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    ):
        deny()

    if isinstance(address, ipaddress.IPv6Address):
        if (
            address.ipv4_mapped is not None
            or address.is_site_local
            or any(address in net for net in DENIED_V6)
        ):
            deny()

    return str(address)


def validate_url(value: str) -> Destination:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 2048
        or not value.isascii()
        or any(
            ord(c) <= 32 or ord(c) == 127
            for c in value
        )
        or chr(92) in value
    ):
        deny()

    try:
        parts = urlsplit(value)
        scheme = parts.scheme.lower()

        if scheme not in {"http", "https"}:
            deny()

        if (
            not parts.netloc
            or "@" in parts.netloc
            or "%" in parts.netloc
            or parts.username is not None
            or parts.password is not None
        ):
            deny()

        host = parts.hostname

        if not host or host.endswith("."):
            deny()

        expected_port = 443 if scheme == "https" else 80
        port = parts.port

        if port is not None and port != expected_port:
            deny()

        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None

        if literal is not None:
            host = public_ip(host)
            authority = (
                f"[{host}]"
                if ":" in host else host
            )
        else:
            if (
                len(host) > 253
                or "." not in host
                or any(
                    not LABEL.fullmatch(label)
                    for label in host.split(".")
                )
                or not host.split(".")[-1][0].isalpha()
                or host.endswith(
                    (
                        ".localhost",
                        ".local",
                        ".internal",
                        ".home.arpa",
                        ".onion",
                    )
                )
            ):
                deny()

            authority = host

        # Reject ambiguous or malformed authorities.
        allowed = {
            authority,
            f"{authority}:{expected_port}",
        }

        if parts.netloc.lower() not in allowed:
            deny()

        canonical = urlunsplit((
            scheme,
            authority,
            parts.path or "/",
            parts.query,
            "",
        ))

        return Destination(
            canonical,
            scheme,
            host,
            expected_port,
        )

    except (ValueError, UnicodeError, IndexError):
        deny()


def bind_destination(url: str, resolver):
    destination = validate_url(url)

    try:
        literal = ipaddress.ip_address(destination.host)
    except ValueError:
        literal = None

    if literal is not None:
        answers = (str(literal),)
    else:
        try:
            answers = resolver(destination.host)
        except AcquisitionError:
            raise
        except Exception:
            raise AcquisitionError(
                ErrorCode.DNS_FAILURE
            ) from None

    if (
        type(answers) not in (tuple, list)
        or not 1 <= len(answers) <= 16
    ):
        raise AcquisitionError(
            ErrorCode.DNS_FAILURE
        )

    validated = tuple(
        public_ip(answer)
        for answer in answers
    )

    return BoundDestination(
        destination,
        validated[0],
    )


def redirect_url(source: Destination, location: str):
    if (
        type(location) is not str
        or not 1 <= len(location) <= 2048
        or not location.isascii()
        or any(
            ord(c) <= 32 or ord(c) == 127
            for c in location
        )
        or chr(92) in location
    ):
        deny()

    try:
        result = validate_url(
            urljoin(source.url, location)
        )
    except ValueError:
        deny()

    if (
        source.scheme == "https"
        and result.scheme != "https"
    ):
        deny()

    return result
