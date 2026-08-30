# Security And Data Policy

Do not open public issues or pull requests containing private biological, operational, provider, or customer data. Use Private vulnerability reporting for vulnerabilities, leaks, or security-sensitive release-process problems.

Never include:

- API keys, cloud credentials, SSH keys, tokens, signed URLs, registry auth, or license files
- private structures, unpublished sequences, private maps, raw reads, raw cryo-EM movies, or patient data
- provider pod IDs, network volume IDs, account IDs, billing records, or raw provider logs
- private workstation paths, private issue-tracker content, or internal run notes
- model weights, large public databases, checkpoints, or generated structure archives

Use synthetic examples or public accessions with source and transformation notes.

If you discover a security issue in the code or release process, report it privately to the repository owner through GitHub's Private vulnerability reporting flow rather than posting sensitive details publicly.

Run before publication:

```bash
make release-check
make public-switch-check
make secret-scan
```
