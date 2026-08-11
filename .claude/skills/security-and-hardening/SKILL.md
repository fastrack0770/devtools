---
name: security-and-hardening
description: Hardens code against vulnerabilities. Use when the change touches untrusted input, authentication, authorization, secrets, webhooks, file uploads, server-side URL fetches, payment or regulated data, privileged actions, LLM-powered features, or adds/upgrades dependencies. Not needed for pure UI styling, refactors that don't cross a trust boundary, or documentation unrelated to security.
---

# Security and Hardening

Treat every external input as hostile, every secret as sacred, and every authorization check as mandatory. Security is a constraint on each line that touches user data, auth, or external systems — not a phase.

## Threat model first (five minutes, not a ceremony)

Controls bolted on without a threat model are guesses:

1. **Map trust boundaries** — where untrusted data enters: HTTP requests, uploads, webhooks, third-party APIs, message queues, and **LLM output**.
2. **Name the assets** worth stealing or breaking: credentials, PII, payment data, admin actions, money movement.
3. **Run STRIDE over each boundary** as a quick lens: spoofing → authentication; tampering → integrity checks and parameterized queries; repudiation → audit logs; information disclosure → encryption and field allowlists; DoS → rate limits and size caps; elevation → authorization checks.
4. **Write abuse cases next to use cases** — "how would I misuse this?" becomes the first test.

If you can't name a feature's trust boundaries, you're not ready to secure it (OWASP A04: Insecure Design).

## Hard rules

These are consequence-based and non-negotiable:

- Never commit secrets. If one ever lands in git, **rotate it first**, then purge history — deletion alone means it's already compromised.
- Never log passwords, tokens, or full card numbers; never expose stack traces or internals to users.
- Never construct queries, shell commands, or markup by interpolating untrusted data — parameterize / encode instead.
- Validate external input at the boundary against its intended use (type, range, size, format), not just "is it a string".
- Every protected endpoint checks authorization (resource ownership / role), not just authentication; verify signatures on inbound webhooks.
- Passwords are stored only as bcrypt/scrypt/argon2 hashes; external communication goes over HTTPS.
- Client-side validation is UX, never a security boundary.
- Treat LLM output as untrusted input — never pass it raw into eval, SQL, a shell, `innerHTML`, or a file path.

## Surface and confirm threat-model changes

Changing auth flows, storing new categories of sensitive data (PII, payments), new external integrations or origins, file upload handlers, or granting elevated roles all change the threat model. If the user explicitly asked for the work, name the new risk and proceed; if the change is a side effect of something else, confirm before building.

## Judgment areas

Use context, not blanket bans:

- Rendering user HTML is sometimes the feature (editors, previews) — sanitize (DOMPurify or equivalent) and isolate; prefer framework auto-escaping everywhere else.
- Where a session token lives depends on the XSS/CSRF tradeoff for your architecture; default to httpOnly/secure/sameSite cookies unless you have a reason and a mitigation.
- Not every dependency-audit finding blocks release: critical/high + reachable in production → fix now; dev-only or unreachable → schedule it; always document deferrals with a review date.
- Audits catch known CVEs, not typosquats or malicious packages — when adding or upgrading a dependency, review it (maintenance, downloads, install scripts), commit the lockfile, and use reproducible installs in CI (`npm ci` or the ecosystem equivalent).
- Security headers (CSP, HSTS, etc.) and restricted CORS are the default for web services; deviate only with a reason.

## LLM features

An app that calls an LLM inherits new attack surface (OWASP LLM Top 10):

- Prompts can be hijacked by any untrusted text in the context window; the system prompt is not a security boundary — enforce permissions in code.
- Keep secrets and other users' data out of prompts; anything in context can be echoed back.
- Scope agent tools to the minimum; require confirmation for destructive actions; validate every tool argument.
- Cap tokens, request rate, and loop depth so crafted input can't run up cost.
- In RAG, partition embeddings per tenant and validate documents before indexing.

## References

`references/security-checklist.md` holds the detailed material. Load the relevant section when implementing a specific control (injection, XSS, access control, SSRF with its DNS-rebind caveat, headers/CORS, uploads, rate limiting, secrets layout, safe LLM output handling, dependency triage). Load its review checklist before declaring security-relevant work complete.

## Verification

Proportional to what you touched: scan staged changes for secrets (a dedicated scanner like gitleaks beats grep); run the dependency audit if dependencies changed; walk the review checklist sections for the trust boundaries you crossed. Evidence, not "looks safe".
