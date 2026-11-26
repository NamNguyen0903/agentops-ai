"""Controlled DNS and HTTPS fixtures for S07 isolated verification.

Test-only infrastructure. Never import this module from application
runtime. All addresses are confined to a dedicated internal network.

The orchestration layer must enforce isolation before starting this
process. The synthetic addresses must never be routed externally.
"""

import argparse
import ipaddress
import json
import os
import signal
import socket
import socketserver
import ssl
import struct
import threading

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


PRIMARY_IP = "11.77.0.10"
SECONDARY_IP = "11.77.0.11"

DNS_PORT = 53
HTTPS_PORT = 443

PRIMARY_HOST = "source.s07.test"
SECONDARY_HOST = "redirect.s07.test"
MIXED_HOST = "mixed.s07.test"
REBIND_HOST = "rebind.s07.test"
WRONG_HOST = "wrong.s07.test"

CRLF = b"\r\n"
HEADER_END = CRLF * 2

MAX_REQUEST_BYTES = 16384
MAX_BODY_BYTES = 1048576

LOCK = threading.Lock()
COUNTERS = Counter()


def record(event):
    with LOCK:
        COUNTERS[event] += 1

        print(
            json.dumps(
                {"event": event, "count": COUNTERS[event]}
            ),
            flush=True,
        )


def require_fixture_scope():
    if os.environ.get("AGENTOPS_S07_NETWORK_FIXTURE") != "1":
        raise RuntimeError("isolated fixture scope required")

    if not Path("/.dockerenv").is_file():
        raise RuntimeError("container execution required")

    routes = Path("/proc/net/route").read_text().splitlines()

    for line in routes[1:]:
        columns = line.split()

        if len(columns) >= 2 and columns[1] == "00000000":
            raise RuntimeError("default IPv4 route forbidden")

    ipv6_routes = Path("/proc/net/ipv6_route")

    if ipv6_routes.exists():
        for line in ipv6_routes.read_text().splitlines():
            fields = line.split()

            if (
                len(fields) >= 10
                and fields[0] == "0" * 32
                and fields[1] == "00"
                and fields[-1] != "lo"
            ):
                raise RuntimeError(
                    "default IPv6 route forbidden"
                )


def make_certificates(directory):
    directory = Path(directory)

    directory.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o700,
    )

    now = datetime.now(timezone.utc)

    ca_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    ca_name = x509.Name([
        x509.NameAttribute(
            NameOID.COMMON_NAME,
            "S07 Temporary Test CA",
        )
    ])

    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = x509.Name([
        x509.NameAttribute(
            NameOID.COMMON_NAME,
            PRIMARY_HOST,
        )
    ])

    leaf = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(hours=4))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(PRIMARY_HOST),
                x509.DNSName(SECONDARY_HOST),
                x509.DNSName(REBIND_HOST),
            ]),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    for name, data in (
        (
            "ca.pem",
            ca.public_bytes(
                serialization.Encoding.PEM
            ),
        ),
        (
            "server.pem",
            leaf.public_bytes(
                serialization.Encoding.PEM
            ),
        ),
        (
            "server.key",
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        ),
    ):
        path = directory / name

        with path.open("xb") as handle:
            handle.write(data)

        path.chmod(0o600)

    # The CA private key is not persisted.
    record("certificates_created")


def read_question(packet):
    if len(packet) < 17 or len(packet) > 4096:
        raise ValueError("invalid DNS packet length")

    transaction, flags, questions, _, _, _ = struct.unpack(
        "!HHHHHH", packet[:12]
    )

    if flags & 0x8000 or questions != 1:
        raise ValueError("invalid DNS question")

    cursor = 12
    labels = []

    while True:
        if cursor >= len(packet):
            raise ValueError("invalid DNS label")

        size = packet[cursor]
        cursor += 1

        if size == 0:
            break

        if size > 63 or cursor + size > len(packet):
            raise ValueError("invalid DNS label")

        labels.append(
            packet[cursor:cursor+size].decode("ascii")
        )

        cursor += size

    if cursor + 4 > len(packet):
        raise ValueError("invalid DNS question")

    qtype, qclass = struct.unpack(
        "!HH", packet[cursor:cursor+4]
    )

    end = cursor + 4

    if qclass != 1:
        raise ValueError("unsupported DNS class")

    hostname = ".".join(labels).lower()

    return (
        transaction,
        hostname,
        qtype,
        packet[12:end],
    )


def dns_response(packet):
    transaction, host, qtype, question = (
        read_question(packet)
    )

    allowed = {
        PRIMARY_HOST,
        SECONDARY_HOST,
        MIXED_HOST,
        REBIND_HOST,
        WRONG_HOST,
    }

    record(f"dns_query:{host}:{qtype}")

    addresses = []
    rcode = 0

    if host not in allowed:
        rcode = 3  # NXDOMAIN

    elif qtype == 1:
        if host == MIXED_HOST:
            addresses = [
                PRIMARY_IP,
                "127.0.0.1",
            ]

        elif host == REBIND_HOST:
            with LOCK:
                COUNTERS["rebind_a_answers"] += 1
                sequence = COUNTERS["rebind_a_answers"]

            addresses = [
                PRIMARY_IP
                if sequence == 1
                else "127.0.0.1"
            ]

        elif host == SECONDARY_HOST:
            addresses = [SECONDARY_IP]

        else:
            addresses = [PRIMARY_IP]

    # AAAA queries receive a valid empty answer.
    records = []

    for ip in addresses:
        packed = ipaddress.IPv4Address(ip).packed

        records.append(
            b"\xc0\x0c"
            + struct.pack("!HHIH", 1, 1, 0, 4)
            + packed
        )

    flags = 0x8400 | rcode

    return (
        struct.pack(
            "!HHHHHH",
            transaction,
            flags,
            1,
            len(records),
            0,
            0,
        )
        + question
        + b"".join(records)
    )


class DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        packet, transport = self.request

        try:
            reply = dns_response(packet)
        except (ValueError, UnicodeError, struct.error):
            record("dns_malformed_rejected")
            return

        transport.sendto(
            reply,
            self.client_address,
        )


class DNSServer(socketserver.ThreadingUDPServer):
    daemon_threads = True
    allow_reuse_address = True


def response(status, headers, body=b""):
    return (
        CRLF.join([
            b"HTTP/1.1 " + status,
            *headers,
            b"Connection: close",
        ])
        + HEADER_END
        + body
    )


def page(body=b"s07-synthetic-page"):
    return response(
        b"200 OK",
        (
            b"Content-Type: text/plain",
            b"Content-Length: "
            + str(len(body)).encode("ascii"),
        ),
        body,
    )


def redirect(location):
    return response(
        b"302 Found",
        (
            b"Location: "
            + location.encode("ascii"),
            b"Content-Length: 0",
        ),
    )


def payload_for(path):
    if path == "/ok":
        return page()

    if path == "/safe-redirect":
        return redirect(
            f"https://{SECONDARY_HOST}/ok"
        )

    if path == "/unsafe-redirect":
        return redirect(
            f"https://{MIXED_HOST}/ok"
        )

    if path == "/rebind":
        return redirect(
            f"https://{REBIND_HOST}/ok"
        )

    if path == "/private-redirect":
        return redirect(
            "https://127.0.0.1/ok"
        )

    if path == "/downgrade":
        return redirect(
            f"http://{PRIMARY_HOST}/ok"
        )

    if path == "/loop":
        return redirect(
            f"https://{PRIMARY_HOST}/loop"
        )

    if path == "/duplicate":
        return response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 3",
                b"Content-Length: 4",
            ),
            b"abc",
        )

    if path == "/truncated":
        return response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 20",
            ),
            b"short",
        )

    if path == "/oversized-declared":
        return response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Length: 1048577",
            ),
        )

    if path == "/oversized-stream":
        return response(
            b"200 OK",
            (b"Content-Type: text/plain",),
            b"x" * (MAX_BODY_BYTES + 1),
        )

    if path == "/compressed":
        return response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Content-Encoding: gzip",
                b"Content-Length: 3",
            ),
            b"abc",
        )

    if path == "/chunked":
        return response(
            b"200 OK",
            (
                b"Content-Type: text/plain",
                b"Transfer-Encoding: chunked",
            ),
            b"3\r\nabc\r\n0\r\n\r\n",
        )

    return response(
        b"404 Not Found",
        (b"Content-Length: 0",),
    )


class HTTPSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        record("tcp_connection_accepted")

        secured = None

        try:
            self.request.settimeout(3)

            secured = self.server.context.wrap_socket(
                self.request,
                server_side=True,
            )

            record("tls_handshake_completed")

            secured.settimeout(3)

            data = bytearray()

            while HEADER_END not in data:
                chunk = secured.recv(4096)

                if not chunk:
                    return

                data.extend(chunk)

                if len(data) > MAX_REQUEST_BYTES:
                    record("oversized_request_rejected")
                    return

            line = bytes(data).split(CRLF, 1)[0]

            parts = line.decode("ascii").split(" ")

            if (
                len(parts) != 3
                or parts[0] != "GET"
                or parts[2] != "HTTP/1.1"
            ):
                record("invalid_request_rejected")
                return

            path = parts[1]

            record(f"http_request:{path}")

            secured.sendall(
                payload_for(path)
            )

        except ssl.SSLError:
            record("tls_or_ssl_failure")

        except (OSError, UnicodeError):
            record("connection_ended")

        finally:
            if secured is not None:
                secured.close()

            self.request.close()

            record("server_connection_closed")


class HTTPSServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, endpoint, context):
        self.context = context

        super().__init__(
            endpoint,
            HTTPSHandler,
        )


def serve(directory, address, enable_dns):
    require_fixture_scope()

    if address not in {
        PRIMARY_IP,
        SECONDARY_IP,
    }:
        raise RuntimeError("unapproved fixture address")

    directory = Path(directory)

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER
    )

    context.minimum_version = (
        ssl.TLSVersion.TLSv1_2
    )

    context.load_cert_chain(
        directory / "server.pem",
        directory / "server.key",
    )

    servers = [
        HTTPSServer(
            (address, HTTPS_PORT),
            context,
        )
    ]

    if enable_dns:
        servers.append(
            DNSServer(
                (address, DNS_PORT),
                DNSHandler,
            )
        )

    stop = threading.Event()

    def request_stop(*args):
        stop.set()

    signal.signal(
        signal.SIGTERM,
        request_stop,
    )

    signal.signal(
        signal.SIGINT,
        request_stop,
    )

    threads = []

    try:
        for server in servers:
            thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.1},
                daemon=True,
            )

            thread.start()
            threads.append(thread)

        record(f"fixture_ready:{address}")

        while not stop.wait(0.1):
            pass

    finally:
        for server in servers:
            server.shutdown()
            server.server_close()

        for thread in threads:
            thread.join(timeout=5)

        record(f"fixture_stopped:{address}")


def main():
    require_fixture_scope()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "mode",
        choices=("certificates", "serve"),
    )

    parser.add_argument(
        "--directory",
        required=True,
    )

    parser.add_argument(
        "--address",
        default=PRIMARY_IP,
    )

    parser.add_argument(
        "--dns",
        action="store_true",
    )

    args = parser.parse_args()

    if args.mode == "certificates":
        make_certificates(args.directory)

    else:
        serve(
            args.directory,
            args.address,
            args.dns,
        )


if __name__ == "__main__":
    main()
