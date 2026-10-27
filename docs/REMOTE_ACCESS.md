# Remote access

New installations allow configured local addresses only. SuperGallery does not open router ports, register domains, create tunnels or change UGREENlink. Use a gateway you control, and enable authenticator verification before allowing the external address.

## Configure from your local HTTPS address

1. Set up a public HTTPS gateway or reverse proxy that reaches this instance. Keep a working local access route.
2. Enable two-step verification in Settings → Security.
3. Open Settings → Remote access → Configure remote access. Enter the exact external HTTPS origin, without a path or wildcard.
4. For HTTP forwarding behind a TLS-terminating proxy, enter only its exact internal source IP. The proxy must preserve `Host` and send `X-Forwarded-Proto: https`. Avoid broad proxy trust and never use a wildcard host allowlist.
5. Some HTTPS-only gateways, including observed UGREENlink deployments, report their internal HTTP connection as `X-Forwarded-Proto: http`. Only after verifying that the gateway redirects all public HTTP traffic to HTTPS, enable **Gateway enforces HTTPS at its public address**. This explicitly trusts the listed proxy peers to enforce external TLS. It applies only to the configured public origin. Do not enable it for a gateway that accepts plaintext public traffic.
6. Enable remote access, enter your current password and authenticator/recovery code, and save. Verify from a separate remote browser session.

When disabled, the configured external origin is rejected even for an existing session. Change this setting through the local NAS address; it is intentionally read-only from remote sessions. MFA cannot be disabled while remote access is enabled.

The switch controls the app's configured external hostname, not physical Wi-Fi membership. A VPN or proxy that presents a local hostname and private source IP can look like local traffic. For strict LAN-only operation also disable the external NAS gateway for this app and enforce your router/firewall policy. Do not forward the app's local hostname through an untrusted proxy.

## UGREEN addresses and custom names

UGREEN allocates its Docker application domains. SuperGallery cannot mint a `supergallery-...` name under a domain owned by UGREEN. A NAS-wide UGREENlink ID may be customizable in UGOS, but changing it can affect other apps. For a name you control, use your own domain with DNS and an HTTPS reverse proxy. SuperGallery accepts the resulting exact origin; it does not purchase or configure that domain.

UGREEN documentation: [UGREENlink remote access](https://support.ugnas.com/detail/article/en-US/86). Actual hostname controls vary by firmware.

## Operator configuration

The settings are stored in `/config/network.json`, deliberately outside app-index backup restore. With no such file, these environment variables provide bootstrap values:

| Variable | Default | Purpose |
| --- | --- | --- |
| `REMOTE_ACCESS_ENABLED` | off | Set `1` only for an already configured gateway |
| `PUBLIC_URL` | empty | Exact HTTPS external origin |
| `TRUSTED_PROXIES` | empty | Comma-separated exact proxy IPs |
| `GATEWAY_HTTPS_ONLY` | off | Set `1` only for a verified HTTPS-only gateway whose protocol header is unsuitable |
| `ALLOWED_HOSTS` | localhost/loopback | Exact local NAS hostnames or IPs, without ports |
| `FRAME_ANCESTORS` | self only | Optional comma-separated exact desktop origins permitted to embed the app |

Settings saved through the UI take precedence over these bootstrap variables. Protect and back up `network.json` as private operator configuration. Keep `proxy_headers=False` in the server: SuperGallery validates the explicit peer and origin itself. `X-Forwarded-For` is not trusted for rate limiting; gateway users share a conservative rate-limit bucket.

The default Compose publishes HTTPS only. If a local gateway requires port 8800, add the required mapping in a private Compose override and restrict it to that gateway with the host firewall. Do not expose plaintext port 8800 directly to the Internet.
