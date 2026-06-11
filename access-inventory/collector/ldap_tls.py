from __future__ import annotations

import os
import ssl

from ldap3 import Server, Tls

# Bundled Deltek internal CA chain: DeltekSubCA2 + DeltekUSRoot
# Extracted from dltkdc1.ads.deltek.com:636 TLS handshake + AIA fetch.
_BUNDLE = os.path.join(os.path.dirname(__file__), "deltek_ldap_ca.pem")


def build_server(host: str, port: int, use_ssl: bool, ca_cert: str = "") -> Server:
    """Build an ldap3 Server with TLS certificate verification.

    Uses the bundled Deltek internal CA chain (DeltekSubCA2 + DeltekUSRoot).
    The ca_cert parameter is accepted for API compatibility but the bundle
    file takes precedence since the provided leaf cert alone cannot verify
    the chain.
    """
    if not use_ssl:
        return Server(host, port=port)

    if os.path.exists(_BUNDLE):
        tls = Tls(
            ca_certs_file=_BUNDLE,
            validate=ssl.CERT_REQUIRED,
            version=ssl.PROTOCOL_TLS_CLIENT,
        )
    else:
        # Bundle file missing — fall back to system trust store
        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            version=ssl.PROTOCOL_TLS_CLIENT,
        )

    return Server(host, port=port, use_ssl=True, tls=tls)
