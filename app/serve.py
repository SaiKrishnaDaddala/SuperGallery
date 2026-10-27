"""Serve existing LAN HTTP plus TLS. MFA is accepted only on the TLS listener.

Use TLS_CERT_FILE/TLS_KEY_FILE for a trusted certificate. Otherwise generate a
NAS-local certificate; its trust must be confirmed by the device owner.
"""
import datetime
import ipaddress
import os
import threading
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from .config import CONFIG_DIR


def certificate():
    supplied_cert, supplied_key = os.getenv("TLS_CERT_FILE"), os.getenv("TLS_KEY_FILE")
    if supplied_cert or supplied_key:
        if not supplied_cert or not supplied_key:
            raise RuntimeError("Set both TLS_CERT_FILE and TLS_KEY_FILE")
        return supplied_cert, supplied_key
    folder = CONFIG_DIR / "tls"
    folder.mkdir(mode=0o700, exist_ok=True)
    cert, keyfile = folder / "server.crt", folder / "server.key"
    if cert.exists() and keyfile.exists():
        return str(cert), str(keyfile)
    if cert.exists() or keyfile.exists():
        raise RuntimeError("Incomplete TLS certificate pair; restore both /config/tls files")
    key = ec.generate_private_key(ec.SECP256R1())
    names = []
    for name in os.getenv("TLS_HOSTS", "localhost,127.0.0.1").split(","):
        name = name.strip()
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            names.append(x509.DNSName(name))
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SuperGallery NAS")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certdata = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
                .not_valid_after(now + datetime.timedelta(days=365)).add_extension(x509.SubjectAlternativeName(names), critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True).sign(key, hashes.SHA256()))
    fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert.write_bytes(certdata.public_bytes(serialization.Encoding.PEM))
    return str(cert), str(keyfile)


def main():
    cert, key = certificate()
    # Run startup once; the HTTP compatibility listener shares the application.
    https = uvicorn.Server(uvicorn.Config("app.main:app", host="0.0.0.0", port=int(os.getenv("HTTPS_PORT", "8843")), ssl_certfile=cert, ssl_keyfile=key, proxy_headers=False, loop="asyncio", http="h11", ws="none"))
    http = uvicorn.Server(uvicorn.Config("app.main:app", host="0.0.0.0", port=8800, lifespan="off", proxy_headers=False, loop="asyncio", http="h11", ws="none"))
    threading.Thread(target=http.run, daemon=True, name="http-compatibility").start()
    https.run()
    http.should_exit = True


if __name__ == "__main__":
    main()
