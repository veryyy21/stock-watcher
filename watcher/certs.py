"""Make Python trust the same certificates Windows trusts.

Antivirus suites that scan HTTPS (Norton, Avast, Kaspersky...) re-sign traffic
with their own root certificate. Windows trusts it, but Python's bundled list
(certifi) doesn't, so every download fails with "unable to get local issuer
certificate". We build a combined bundle: certifi + the Windows root stores.
"""
import os
import ssl
from pathlib import Path

import certifi

BUNDLE = Path(__file__).resolve().parent.parent / "data" / "ca-bundle.pem"


def build_bundle() -> str:
    BUNDLE.parent.mkdir(exist_ok=True)
    pems = [Path(certifi.where()).read_text(encoding="utf-8")]
    if hasattr(ssl, "enum_certificates"):  # Windows only
        for store in ("ROOT", "CA"):
            for cert, encoding, trust in ssl.enum_certificates(store):
                if encoding == "x509_asn" and (trust is True or "1.3.6.1.5.5.7.3.1" in trust):
                    pems.append(ssl.DER_cert_to_PEM_cert(cert))
    BUNDLE.write_text("\n".join(pems), encoding="utf-8")
    # requests (Discord) and the stdlib read these.
    os.environ["REQUESTS_CA_BUNDLE"] = str(BUNDLE)
    os.environ["SSL_CERT_FILE"] = str(BUNDLE)
    return str(BUNDLE)
