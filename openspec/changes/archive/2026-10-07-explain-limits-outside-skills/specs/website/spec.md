## MODIFIED Requirements

### Requirement: Matches the project's promises
The site's claims SHALL match the README and specs: every skill is read-only, credentials never pass
through the chat, Tautulli is optional. The site SHALL show that Cinemetric is not affiliated with,
endorsed by or sponsored by Plex, Inc. or Anthropic, and the caution that AI-written reports can contain
mistakes. That caution SHALL also say, in one sentence, that Cinemetric only controls what its own
skills do, so if the user asks Claude to change something on their server they should read each
command Claude Code shows them before approving it. It SHALL NOT describe ways to get around the
guard. It SHALL NOT use Plex's or Anthropic's logos. The hero background MAY show real posters, taken
from the owner's own Plex server with the owner's agreement, saved as small local images with no
server address or token in them, and shown blurred and dimmed as decoration.

#### Scenario: Trademark notice
- **WHEN** a visitor reaches the bottom of the page
- **THEN** they see the not-affiliated notice alongside the footer

#### Scenario: Plex-like look without Plex's logo
- **WHEN** the page is styled to feel like Plex
- **THEN** it uses its own Cinemetric mark and colors in the same spirit, not the Plex logo or wordmark

#### Scenario: Asking Claude to change things
- **WHEN** a visitor reads "AI can make mistakes"
- **THEN** they learn Cinemetric only controls its own skills, and to read the commands Claude Code
  shows them before approving any change to their server
