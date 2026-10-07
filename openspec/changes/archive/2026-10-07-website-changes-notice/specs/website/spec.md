## MODIFIED Requirements

### Requirement: Matches the project's promises
The site's claims SHALL match the README and specs: every skill is read-only, credentials never pass
through the chat, Tautulli is optional. The site SHALL show that Cinemetric is not affiliated with,
endorsed by or sponsored by Plex, Inc. or Anthropic, and the caution that AI-written reports can contain
mistakes. Beside that caution, a notice of its own headed "Changes are up to you" SHALL say that
Cinemetric only reads but Claude can do more than run its skills; that if the user asks Claude to
change something on their server, Claude Code shows each command first, so they should read it
before approving; and that switching off Allow media deletion in Plex (Settings, Library) stops Plex
deleting media files for any app. The two notices SHALL share the same card style, so neither looks selected. The new notice SHALL be worded as the user being in control, not as a warning,
and SHALL NOT describe ways to get around the guard. The site SHALL NOT use Plex's or Anthropic's
logos. The hero background MAY show real posters, taken from the owner's own Plex server with the
owner's agreement, saved as small local images with no server address or token in them, and shown
blurred and dimmed as decoration.

#### Scenario: Trademark notice
- **WHEN** a visitor reaches the bottom of the page
- **THEN** they see the not-affiliated notice alongside the footer

#### Scenario: Plex-like look without Plex's logo
- **WHEN** the page is styled to feel like Plex
- **THEN** it uses its own Cinemetric mark and colors in the same spirit, not the Plex logo or wordmark

#### Scenario: Asking Claude to change things
- **WHEN** a visitor skims the notices near the bottom of the page
- **THEN** they see "Changes are up to you" as its own heading, and learn Cinemetric only controls its
  own skills, to read the commands Claude Code shows them before approving a change, and how to stop
  Plex deleting media files

#### Scenario: On a phone
- **WHEN** the page is viewed at phone width
- **THEN** the two notices stack one above the other, with no sideways scrolling

### Requirement: Footer credit and link
The footer SHALL link to the GitHub repository at `https://github.com/jeremehancock/cinemetric` and SHALL
name Jereme Hancock as the creator, with the name linking to `https://jeremehancock.com`. It SHALL also
link to the repository's GitHub issues, so visitors can report bugs and share ideas.

#### Scenario: Footer contents
- **WHEN** a visitor looks at the footer
- **THEN** it shows "Created by Jereme Hancock" with the name linking to jeremehancock.com, a
  working link to the GitHub repository, and an "Issues" link to GitHub issues

### Requirement: Text doesn't end on a lonely word
Paragraphs, list items and captions SHALL NOT end with a single word alone on their last line, at any
width from phone to large desktop. Short text (three lines or fewer, such as feature bullets, intros,
"Ask Claude" lines and card text) SHALL wrap into lines of roughly even length, so its last line is
not a word or two under a full line. Longer paragraphs, such as the notices near the bottom of the
page, SHALL fill the width of their container. This SHALL be done with CSS line wrapping, not by
changing the wording. In browsers that don't support `text-wrap: pretty`, a script SHALL keep the last
two words of each paragraph, list item and caption together, unless together they are longer than 24
characters.

#### Scenario: A short feature bullet
- **WHEN** a visitor at any width reads "Who's watching right now, on which device, and how far along
  they are."
- **THEN** if it wraps, its two lines are of similar length rather than a full line followed by
  "they are."

#### Scenario: A long paragraph
- **WHEN** a paragraph of four or more lines wraps
- **THEN** its last line has at least two words

#### Scenario: Notices side by side
- **WHEN** a visitor views the two notices side by side
- **THEN** the text in each fills its card's width, rather than one being wrapped into shorter lines

#### Scenario: Firefox
- **WHEN** the page is viewed in a browser without `text-wrap: pretty` support, with JavaScript on
- **THEN** each paragraph, list item and caption's last two words stay on the same line, unless they
  are longer than 24 characters together

#### Scenario: Wording unchanged
- **WHEN** the page is viewed with JavaScript turned off
- **THEN** all text reads exactly as written in the HTML, only its line breaks differ
