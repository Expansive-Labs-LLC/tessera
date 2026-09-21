# Security Policy

## Security Model

Tessera is designed with a **local-first, privacy-preserving architecture**:

- **All AI inference runs locally** on your GPU — no data ever leaves your machine.
- The **only network activity** is optional model weight downloads from configured URLs during initial setup (see [Model Weight Management](https://expansive-labs-llc.github.io/tessera/)).
- **No telemetry, analytics, or crash reporting** is collected — your data stays on your hardware.

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in Tessera, please report it responsibly.

### Preferred: GitHub Security Advisories

1. Navigate to the [Security tab](https://github.com/Expansive-Labs-LLC/tessera/security) of this repository.
2. Click **"Report a vulnerability"** under **Advisories**.
3. Fill out the advisory form with as much detail as possible.

This method ensures your report remains private until a fix is available.

### Fallback: Email

If you cannot use GitHub Security Advisories, email **security@tessera.dev** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact assessment

### Response Timeline

- **Acknowledgment:** ≤ 5 business days
- **Initial assessment:** ≤ 10 business days
- **Fix timeline:** Communicated in the initial assessment

### Credit

Reporters will receive credit in the security advisory unless they prefer to remain anonymous. Please indicate your preference when reporting.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x.x   | ✅ Supported |

## Disclosure Policy

- Vulnerabilities will be disclosed publicly **after a fix is available**.
- Patches will be released as a new version following [semantic versioning](https://semver.org/).
- CVE identifiers will be requested for vulnerabilities with CVSS ≥ 7.0.
