# Summary

Describe the change and the campaign, module, script, or doc surface it touches.

# Public Safety

- [ ] No secrets, tokens, credentials, signed URLs, private installer links, license files, or accepted-license records.
- [ ] No private biological data, unpublished sequences, generated structures, raw maps, raw cryo-EM movies, model weights, archives, or large generated outputs.
- [ ] No private tracker URLs, concrete provider IDs, private volume IDs, local workstation paths, or private operator notes.
- [ ] Scientific conclusions stay tied to the outputs and validation actually present.

# Validation

- [ ] `make release-check`
- [ ] `make public-switch-check` for release-facing changes
- [ ] `make public-contract-check`
- [ ] Additional campaign-specific checks:
