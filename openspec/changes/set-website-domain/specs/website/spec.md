## ADDED Requirements

### Requirement: Live address and link previews
The page SHALL declare `https://cinemetric.dev/` as its address: a `canonical` link and an `og:url` tag
with that value. Its social preview image SHALL be given as a full address,
`https://cinemetric.dev/og-image.png`, in both `og:image` and `twitter:image`, with the image's width,
height and alt text. These are the only full addresses to the site itself; links between the site's
own files SHALL stay relative.

#### Scenario: Sharing the link
- **WHEN** someone pastes `https://cinemetric.dev` into a chat or social app
- **THEN** the app finds the title, description and a full-address preview image in the page's tags
  and can show a link card

#### Scenario: Serving from somewhere else
- **WHEN** the `website/` folder is opened from disk or served from another address
- **THEN** the page still loads its styles, script and images, because those links are relative
