# Security Policy & Guidelines

## Reporting a Vulnerability

If you discover a security vulnerability within Campus Vision, please report it privately to the system administrators or the information security team. Please do not disclose vulnerabilities in public issue trackers.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Recommendations for Deployment

1. **Environment Variables:**
   - Always run the application with `DEBUG=False` in production.
   - Set a strong, randomly generated `DJANGO_SECRET_KEY`.
   - Never commit database passwords, API keys, or secret tokens directly to version control.
   - Use `.env` files or cloud secret managers (e.g. Google Secret Manager / AWS Secrets Manager).

2. **Access Control:**
   - Enforce authentication on all administrative endpoints (`/upload/`, `/settings/`, `/usermanager/`, etc.).
   - Limit admin access to authorized operators only.

3. **HTTPS / TLS:**
   - Serve the application exclusively over HTTPS with valid SSL/TLS certificates.
   - Enable HSTS and Secure cookie flags.

4. **File Uploads:**
   - Enforce strict file size limits (recommended max 50MB for video/image).
   - Validate file MIME types and disable script execution in media/upload directories.

For a complete Information Security Risk Assessment and mitigation roadmap, see [docs/SEGURANCA_DA_INFORMACAO.md](docs/SEGURANCA_DA_INFORMACAO.md).
