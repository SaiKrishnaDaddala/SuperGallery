# Security policy

## Supported release

Security fixes target the latest published release. Earlier private development versions are not supported public releases. Install updates deliberately after reading migration notes and backing up configuration.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/SaiKrishnaDaddala/SuperGallery/security/advisories/new). Include the affected version, a minimal reproduction using synthetic data, expected impact and relevant redacted output. Do not open a public issue with an exploit, credentials or private media. No response-time guarantee or bug-bounty program is offered.

## Security boundaries

- One shared application login grants access to the mounted library. This is not a multi-tenant service. Owner filters and feature switches are not user permissions.
- HTTPS is required for authenticator enrollment and verification. Remote access requires MFA and an explicitly configured external origin.
- Proxy trust is restricted to configured exact peer IPs. The optional HTTPS-only gateway setting relies on that gateway enforcing TLS; configure it only after verifying the edge behavior.
- Sessions use HttpOnly cookies, secure cookies over HTTPS and SameSite protection. Mutating API requests validate Origin; non-browser clients explicitly set `X-SG-Request: 1` and must authenticate.
- Password verification, login throttling, one-time authenticator/recovery codes and reauthentication protect security-sensitive operations. Keep recovery codes offline.
- A read-only library mount is the recommended first-run boundary. A writable mount permits file changes and cleanup. The default container user is root for NAS compatibility; scope mounts tightly.

Do not publish plaintext port 8800 directly to the Internet, trust arbitrary proxy ranges, use wildcard allowed hosts, mount the Docker socket, or expose the whole NAS to users who should see only one folder. Local-only mode controls configured hostnames and peer addresses; combine it with NAS/router firewall policy for strict network isolation.

The code has automated security regression checks but has not undergone an independent penetration test or formal certification. Dependency scanning checks known advisories and cannot prove absence of vulnerabilities.
