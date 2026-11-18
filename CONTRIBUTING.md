# Contributing

Bug reports, documentation improvements, and focused pull requests are welcome.

## Report an issue

Search existing issues first. Include your checkout revision, Python and resolved
package versions, relevant settings with secrets removed, expected/actual results,
and the smallest reproducible request. For XMPP delivery problems include whether
the client was connected and whether a full or bare JID was used.

Never include credentials, bearer tokens, verification codes, private JIDs, or
uploaded user content in a public report. Discuss sensitive reports privately with
the maintainers through an existing trusted contact channel; no dedicated security
response address or response-time commitment is currently published here.

## Develop and submit

1. Follow [installation](docs/installation.md) in an isolated environment with a
   dedicated test XMPP account and disposable database/media directory.
2. Create a branch and keep the change focused. Explain the problem and resulting behavior.
3. Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`,
   and `python manage.py test`. The repository currently has no application test suite;
   a successful test command alone is not evidence of functional coverage. See
   [known schema-check findings](docs/operations.md#schema-and-framework-checks)
   for the current pre-existing migration drift.
4. Exercise affected HTTP/XMPP behavior and describe what you verified in the PR.
   Add meaningful regression coverage for behavior changes where practical.
5. Update the installation/API documentation when changing configuration or protocol behavior.

Changes to authentication, authorization, deletion, quotas, or public-file serving
should explain their impact on existing clients and deployments. Do not commit local
settings, databases, media, secrets, or virtual environments.

Contributions are made under the repository's [AGPL-3.0 license](LICENSE).
