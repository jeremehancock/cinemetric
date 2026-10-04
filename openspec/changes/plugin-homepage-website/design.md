## Context

The website launched at https://cinemetric.dev. Both manifests have a `homepage` field that pointed to
the GitHub repository because there was no website yet. `plugin.json` also has a separate `repository`
field.

## Goals / Non-Goals

**Goals:**
- Point the plugin's homepage at the website, keep the repository link for the source.
- Follow the one-version-number rule.

**Non-Goals:**
- Any script, skill or README behavior change.

## Decisions

- **Homepage → website, repository → GitHub.** The two fields have different jobs: `homepage` is where
  a person learns about the plugin, `repository` is where the code lives. Alternative considered:
  keeping GitHub as the homepage. Rejected because the website is the better introduction and it
  links to GitHub everywhere.
- **No trailing slash** (`https://cinemetric.dev`), matching the style of the existing GitHub URLs in
  the manifests.
- **Patch bump to 0.4.1.** The conventions spec requires every version to move together on a release,
  and a manifest change is a release. Nothing functional changes, so it's a patch, not a minor bump.

## Risks / Trade-offs

- [Website is down] → People following the homepage link would hit an error. The website footer and
  README both link GitHub, and `repository` still points there.
