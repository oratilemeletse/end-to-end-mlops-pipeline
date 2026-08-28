# Dependency Security

## Active Exception: PYSEC-2026-3552

| Field | Value |
|---|---|
| Package | `cryptography==49.0.0` |
| Advisory | `PYSEC-2026-3552` / `GHSA-g6cj-pr64-35w5` |
| Fixed version | `50.0.0` |
| Blocking dependency | `mlflow==3.15.1` requires `cryptography<50` |
| Review trigger | A compatible MLflow release that permits `cryptography>=50` |
| Scope | CI ignores only `PYSEC-2026-3552`; every other advisory remains blocking |

The advisory affects PKCS#7 EnvelopedData decryption and can expose a
Bleichenbacher oracle when an application decrypts attacker-controlled
EnvelopedData and reveals distinguishable errors or timing.

This project does not call `pkcs7_decrypt_der`, `pkcs7_decrypt_pem`,
`pkcs7_decrypt_smime`, or expose any PKCS#7 decryption service. Its use of
`cryptography` is transitive through MLflow and Azure authentication.
Therefore, the affected code path is not reachable in the documented training,
registration, deployment, or scoring workflows.

`cryptography==49.0.0` is intentionally pinned because earlier compatible
versions have additional known advisories. `msal==1.38.0` is also pinned so
Azure Identity resolves a version compatible with cryptography 49. CI keeps
`pip-audit` in strict mode and exempts only this specific ID. Do not add
another ignored advisory without its own reachability analysis, owner, and
removal condition.

Remove the exception by:

1. Upgrading to the first tested MLflow release that allows
   `cryptography>=50`.
2. Pinning the fixed cryptography version.
3. Removing `--ignore-vuln PYSEC-2026-3552` from the CI workflow.
4. Running the full test, container, and dependency-audit gates.

References:

- [PyPA advisory record](https://github.com/pypa/advisory-database/blob/main/vulns/cryptography/PYSEC-2026-3552.yaml)
- [Upstream cryptography advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5)
