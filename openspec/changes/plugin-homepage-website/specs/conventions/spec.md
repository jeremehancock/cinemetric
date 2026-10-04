## ADDED Requirements

### Requirement: Plugin links
`plugin.json` and `marketplace.json` SHALL give `https://cinemetric.dev` as the plugin's `homepage`.
`plugin.json` SHALL give `https://github.com/jeremehancock/cinemetric` as its `repository`.

#### Scenario: Checking the manifests
- **WHEN** someone reads `plugin.json` or `marketplace.json`
- **THEN** `homepage` is `https://cinemetric.dev`, and `plugin.json`'s `repository` is the GitHub
  repository
