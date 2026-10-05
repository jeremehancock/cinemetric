# website Specification

## Purpose

The public landing page for Cinemetric: a static site in `website/` that shows what each skill does,
in its real output format with made-up sample data, and how to install and set it up. It is not part
of the plugin and never ships with it.
## Requirements
### Requirement: Static site in its own folder
The website SHALL live entirely in the top-level `website/` folder, with `index.html` at its root, so a
static host (such as Coolify) can serve that folder as-is. All links between the site's own files SHALL
be relative, so the site works whether it is served from a domain root or a sub-path.

#### Scenario: Serving the folder
- **WHEN** a static web server is pointed at `website/`
- **THEN** visiting the root address shows the full landing page with its styles, script and images,
  with no build or install step first

#### Scenario: Opening the file directly
- **WHEN** `website/index.html` is opened straight from disk in a browser
- **THEN** the page renders with its styles and images and all content is readable

### Requirement: No frameworks or build step
The site SHALL be written in plain HTML, CSS and JavaScript. It SHALL NOT use a JavaScript or CSS
framework, a bundler, a package manager or any generated files. It SHALL NOT load scripts, styles or
fonts from other servers; everything it needs is in `website/`.

#### Scenario: Checking dependencies
- **WHEN** the files in `website/` are inspected
- **THEN** there is no `package.json`, no framework library, and no `<script>` or `<link>` pointing at
  another domain

### Requirement: Works without JavaScript
All content SHALL be present in the HTML. JavaScript SHALL only add enhancements (animations, copy
buttons, header effects). If scripts are turned off or fail, every section and command SHALL
still be visible and readable.

#### Scenario: Scripts disabled
- **WHEN** the page is loaded with JavaScript turned off
- **THEN** every section, feature description and setup command is visible, and nothing is stuck
  hidden waiting for an animation

### Requirement: Shows every skill
The site SHALL describe each of the plugin's skills: `setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch` and `dashboard`. For each one it
SHALL say what the skill reports or does and give at least one example of what to ask Claude. Each
skill SHALL have a demo panel showing what the user really gets, and nothing else: for `setup`,
`library-report`, `server-health`, `watch-activity`, `users-and-shares`, `unwatched` and
`what-to-watch`, a Claude Code terminal conversation that follows that skill's `SKILL.md` presentation
order; for `dashboard`, only a screenshot of the real dashboard page built by the dashboard script,
with no terminal conversation and no tabs. The site SHALL NOT show designed graphics as if they were a
skill's output. Demo data (names, titles, numbers) SHALL be made up, never real server data.

#### Scenario: A visitor reads the features
- **WHEN** a visitor scrolls through the features section
- **THEN** they see all eight skills, each with a description, an example request and a demo panel in
  the skill's real output format

#### Scenario: Dashboard demo
- **WHEN** a visitor reaches the dashboard section, with or without JavaScript
- **THEN** the demo panel shows the dashboard screenshot and its caption, and there is no tab bar or
  terminal conversation

### Requirement: Shows how to set up
The site SHALL include a setup guide covering: requirements (Claude Code, Python 3.8+, network access to
the Plex server), the two install commands, connecting with Sign in with Plex, optionally adding
Tautulli, the manual-setup fallback, and how to revoke access. Each command SHALL have a button that
copies it. The guide SHALL link to the README for full details.

#### Scenario: Copying an install command
- **WHEN** a visitor clicks the copy button next to `/plugin marketplace add jeremehancock/cinemetric`
- **THEN** that exact command is placed on their clipboard and the button briefly confirms it was copied

#### Scenario: Wanting more detail
- **WHEN** a visitor needs more than the short setup steps
- **THEN** the setup section links to the README on GitHub

### Requirement: Matches the project's promises
The site's claims SHALL match the README and specs: every skill is read-only, credentials never pass
through the chat, Tautulli is optional. The site SHALL show that Cinemetric is not affiliated with,
endorsed by or sponsored by Plex, Inc. or Anthropic, and the caution that AI-written reports can contain
mistakes. It SHALL NOT use Plex's or Anthropic's logos. The hero background MAY show real posters, taken
from the owner's own Plex server with the owner's agreement, saved as small local images with no
server address or token in them, and shown blurred and dimmed as decoration.

#### Scenario: Trademark notice
- **WHEN** a visitor reaches the bottom of the page
- **THEN** they see the not-affiliated notice alongside the footer

#### Scenario: Plex-like look without Plex's logo
- **WHEN** the page is styled to feel like Plex
- **THEN** it uses its own Cinemetric mark and colors in the same spirit, not the Plex logo or wordmark

### Requirement: Links without underlines
Links SHALL NOT be underlined. Links inside text SHALL stand apart from the text around them by color
and weight.

#### Scenario: A link in a paragraph
- **WHEN** a visitor reads a paragraph that contains a link
- **THEN** the link shows in the accent color and a heavier weight, with no underline

### Requirement: Footer credit and link
The footer SHALL link to the GitHub repository at `https://github.com/jeremehancock/cinemetric` and SHALL
name Jereme Hancock as the creator, with the name linking to `https://jeremehancock.com`.

#### Scenario: Footer contents
- **WHEN** a visitor looks at the footer
- **THEN** it shows "Created by Jereme Hancock" with the name linking to jeremehancock.com, and a
  working link to the GitHub repository

### Requirement: Outside links open in a new tab
Every link that leaves the site SHALL open in a new tab and SHALL use `rel="noopener noreferrer"` (or
`noopener`) so the opened page can't control the site's tab.

#### Scenario: Clicking the GitHub link
- **WHEN** a visitor clicks any link to GitHub, Tautulli or jeremehancock.com
- **THEN** it opens in a new tab and the site stays open in the original tab

### Requirement: Accessible and responsive
The page SHALL work from phone width (360px) to large desktop without horizontal scrolling, SHALL be
usable with a keyboard alone (visible focus, a skip link), SHALL give images and icons text
alternatives or hide purely decorative ones from screen readers, and SHALL keep text contrast at WCAG AA
or better. When the visitor's system asks for reduced motion, animations SHALL be turned off.

Every header link SHALL stay reachable at every width. At phone width (640px and narrower) the header
SHALL show a menu button that opens and closes a panel holding the section links and the GitHub link.
The button SHALL report whether the menu is open to screen readers, and the menu SHALL close when a
link in it is chosen, when Escape is pressed (returning focus to the button), or when the visitor taps
outside it. Without JavaScript there SHALL be no menu button, and the header links SHALL be shown
directly in the header instead.

#### Scenario: Reduced motion
- **WHEN** the visitor's operating system has "reduce motion" turned on
- **THEN** content appears without scroll-in or background animations

#### Scenario: Phone width
- **WHEN** the page is viewed 360px wide
- **THEN** all sections stack into one column, code blocks wrap or scroll within themselves, and the
  page itself never scrolls sideways

#### Scenario: Opening the phone menu
- **WHEN** a visitor on a phone taps the menu button
- **THEN** a panel opens listing Skills, Privacy, Setup, Support and GitHub, and the button is marked
  as expanded

#### Scenario: Choosing a link from the phone menu
- **WHEN** a visitor taps Setup in the open phone menu
- **THEN** the page scrolls to the setup section and the menu closes

#### Scenario: Closing the phone menu by keyboard
- **WHEN** the phone menu is open and the visitor presses Escape
- **THEN** the menu closes and focus returns to the menu button

#### Scenario: Phone menu without JavaScript
- **WHEN** the page is viewed at phone width with JavaScript turned off
- **THEN** there is no menu button and the Skills, Privacy, Setup, Support and GitHub links are visible
  in the header

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

