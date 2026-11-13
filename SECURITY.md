# Security Policy

chart-scrub handles patient-adjacent text, so a masking miss is a security issue, not just a bug.

## Reporting a vulnerability

Please report privately through GitHub: the repository's **Security** tab, then **Report a vulnerability**. Do not open a public issue for a masking bypass or a way to leak the alias database.

When you report, **use invented data only**. Never attach real patient records, real names or a real alias database (`*.db`) to a report.

## What counts

- A realistic input shape that the rules or the residue check let through silently.
- Any path where the alias store or real names are printed, logged or sent somewhere they should not be.

Ordinary gaps in coverage that are already listed under "Known limitations" in the README are not vulnerabilities, but a report that sharpens them is welcome.

## Supported versions

Only the latest release receives fixes.
