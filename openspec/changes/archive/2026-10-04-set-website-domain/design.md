## Context

The site launched at https://cinemetric.dev (served by Coolify from `website/`). The page's social tags
were left with a relative image path and a commented-out `og:url` until the domain was known. Several
link-preview services ignore relative image paths, so previews currently show no image.

## Goals / Non-Goals

**Goals:**
- Correct, complete link previews for https://cinemetric.dev.
- One canonical address for search engines.
- README points to the live site.

**Non-Goals:**
- Changing the plugin manifests' `homepage` (that would be a manifest change needing a version bump;
  the GitHub repository remains the plugin's homepage).
- Making any of the site's own asset links absolute.

## Decisions

- **Full addresses only in the head tags.** `og:url`, `og:image`, `twitter:image` and `canonical`
  use `https://cinemetric.dev/...`; everything else stays relative so the folder still works from disk
  or a preview host. Alternative considered: a `<base href>` tag. Rejected: it would change how every
  relative link resolves, including when opening the file from disk.
- **Describe the image.** Add `og:image:width` (1200), `og:image:height` (630) and
  `og:image:alt`, so services can lay out the card before downloading the image and screen-reader
  users of those apps get a description.
- **Trailing slash.** Use `https://cinemetric.dev/` (with the slash) consistently for the page
  address, which is how browsers report the root URL.

## Risks / Trade-offs

- [Domain changes later] → The address appears in four tags in one place in `index.html`; a future
  change edits them together.
- [Preview services cache old cards] → Nothing to do in the repo; services refresh on their own
  schedule or via their debug tools.
