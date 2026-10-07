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
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`, `playback-check`,
`changes`, `year-in-review` and `dashboard`. For each one it SHALL say what the skill reports or does
and give at least one example of what to ask Claude. Each skill SHALL have a demo panel showing what
the user really gets, and nothing else: for `setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`, `playback-check`
and `changes`, a Claude Code terminal conversation that follows that skill's `SKILL.md` presentation
order; for `dashboard` and `year-in-review`, only a screenshot of the real page built by that skill's
script, with no terminal conversation and no tabs. The site SHALL NOT show designed graphics as if
they were a skill's output. Demo data (names, titles, numbers) SHALL be made up, never real server
data.

#### Scenario: A visitor reads the features
- **WHEN** a visitor scrolls through the features section
- **THEN** they see all twelve skills, each with a description, an example request and a demo panel
  in the skill's real output format

#### Scenario: Dashboard demo
- **WHEN** a visitor reaches the dashboard section, with or without JavaScript
- **THEN** the demo panel shows the dashboard screenshot and its caption, and there is no tab bar or
  terminal conversation

#### Scenario: Year in review demo
- **WHEN** a visitor reaches the year-in-review section, with or without JavaScript
- **THEN** the demo panel shows a screenshot of a whole-server recap built from made-up data, with no
  names on it, and there is no tab bar or terminal conversation

### Requirement: Shows how to set up
The site SHALL include a setup guide covering: requirements (Claude Code, Python 3.8+, network access to
the Plex server), the two install commands, connecting with Sign in with Plex, optionally adding
Tautulli, the manual-setup fallback, and how to revoke access. It SHALL say that Cinemetric works
best in Claude Code in a terminal. Each command SHALL have a button that copies it. The guide SHALL link to the README for full details.

#### Scenario: Copying an install command
- **WHEN** a visitor clicks the copy button next to `/plugin marketplace add jeremehancock/cinemetric`
- **THEN** that exact command is placed on their clipboard and the button briefly confirms it was copied

#### Scenario: Wanting more detail
- **WHEN** a visitor needs more than the short setup steps
- **THEN** the setup section links to the README on GitHub

#### Scenario: Choosing where to run it
- **WHEN** a visitor reads the setup section
- **THEN** they learn that Cinemetric works best in Claude Code in a terminal

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

### Requirement: Links without underlines
Links SHALL NOT be underlined. Links inside text SHALL stand apart from the text around them by color
and weight.

#### Scenario: A link in a paragraph
- **WHEN** a visitor reads a paragraph that contains a link
- **THEN** the link shows in the accent color and a heavier weight, with no underline

### Requirement: Footer credit and link
The footer SHALL link to the GitHub repository at `https://github.com/jeremehancock/cinemetric` and SHALL
name Jereme Hancock as the creator, with the name linking to `https://jeremehancock.com`. It SHALL also
link to the repository's GitHub issues, so visitors can report bugs and share ideas.

#### Scenario: Footer contents
- **WHEN** a visitor looks at the footer
- **THEN** it shows "Created by Jereme Hancock" with the name linking to jeremehancock.com, a
  working link to the GitHub repository, and an "Issues" link to GitHub issues

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

### Requirement: Shows the mods
The site SHALL have a Mods section placed right after the dashboard section and before the privacy
section. It SHALL say plainly that mods come with Cinemetric (no extra install) and that they work
only in Claude Code (the terminal and the desktop app's Code tab). For each mod it SHALL say what the
mod does in plain words, its short name (for example `guard`, `status` or `now`), and whether it
starts on or off. The Now Playing card SHALL also say that it checks the server only while its panel
is open. The section SHALL say that some versions of the
desktop app can't show the status line or the Now Playing panel, and SHALL link to the README for
what to do when the mods don't show up. The "Shows every skill" count and
headings SHALL stay about skills only.

#### Scenario: A visitor reaches the mods
- **WHEN** a visitor scrolls past the dashboard section
- **THEN** they see the Mods section, the read-only guard described in it as on by default, the
  library status line and Now Playing described as off by default, and a note that mods work only in
  Claude Code

#### Scenario: Reading the Now Playing card
- **WHEN** a visitor reads the Now Playing card
- **THEN** they learn it shows who is streaming right now, that it's opened with `/cinemetric-now`,
  and that it checks the server only while it's open

#### Scenario: Wondering how to get them
- **WHEN** a visitor reads the Mods section
- **THEN** they learn the mods come with the normal install, with nothing extra to run

#### Scenario: Without JavaScript
- **WHEN** a visitor opens the page with JavaScript turned off
- **THEN** the Mods section, including how to switch mods, is still visible and readable

#### Scenario: Mods not showing up
- **WHEN** a visitor's mods don't show up
- **THEN** the Mods section links them to the README's fixes

### Requirement: The setup guide points to the mods
The setup guide SHALL keep its four steps and SHALL mention the mods in a collapsible "Mods
(optional)" extra beside the other optional extras, not as a step. It SHALL say the mods come with
Cinemetric, that the read-only guard is already on and other mods start off, give `/cinemetric-mods`
with a copy button, state that mods need Claude Code 2.1.260 or newer, and link to the Mods section.

#### Scenario: Reading the setup guide
- **WHEN** a visitor opens "Mods (optional)" under the setup steps
- **THEN** they see that nothing more needs installing, the `/cinemetric-mods` command, and a link to
  the Mods section, and the guide still says it takes four steps

### Requirement: Explains how to switch mods on and off
The Mods section SHALL explain both ways to switch a mod:
- typing `/cinemetric-mods` to see every mod and whether it's on, and
  `/cinemetric-mods <name> on` or `off` to switch one, shown with the status line as the example
  (`/cinemetric-mods status on`);
- the config menu, opened with `/config`, where each mod has a switch.

Each command shown SHALL have a copy button, using the same copy behavior as the setup guide. The
section SHALL say that the guard is meant to be switched off only by the user and that Cinemetric
refuses Claude's usual ways of switching it off, and why in one sentence (so Claude can't casually
turn off its own safety net). It SHALL NOT promise that Claude can never switch the guard off. It
SHALL NOT describe a way to ask Claude to switch mods until the plugin has one.

#### Scenario: Turning a mod on
- **WHEN** a visitor wants to know how to turn a mod on
- **THEN** the Mods section shows `/cinemetric-mods status on` with a copy button, and mentions the
  config menu as the other way

#### Scenario: Seeing what's on
- **WHEN** a visitor wants to check which mods are on
- **THEN** the Mods section tells them to type `/cinemetric-mods`

#### Scenario: Copying a mods command
- **WHEN** a visitor clicks the copy button next to `/cinemetric-mods status on`
- **THEN** that exact command is placed on their clipboard and the button briefly confirms it was
  copied

#### Scenario: Reading who can switch the guard off
- **WHEN** a visitor reads the Mods section
- **THEN** it says the guard is meant to be switched off only by them and that Claude's usual ways
  are refused, without saying Claude can never do it

### Requirement: The privacy section mentions the guard
The "Look, don't touch" section's intro SHALL mention that the read-only guard, on by default, can also stop
Claude from running its own commands that would change the server, and keeps Claude from seeing or
passing on the user's Plex token and Tautulli API key. The cards SHALL stay as they were, so they keep similar lengths.
The wording SHALL call it an extra safety net and SHALL NOT claim it catches everything.

#### Scenario: Reading the privacy section
- **WHEN** a visitor reads "Look, don't touch"
- **THEN** they see a short mention of the guard, covering both changes to the server and the token,
  that links to the Mods section

### Requirement: The guard's card mentions token protection
The read-only guard's card in the Mods section SHALL say, in plain words, that the guard also hides
the user's Plex token and Tautulli API key from what Claude sees, and stops Claude from putting
them in files, issues or pages. It SHALL NOT claim the token can never be seen, and SHALL keep the
card's length close to the other mod cards.

#### Scenario: Reading the guard's card
- **WHEN** a visitor reads the read-only guard's card
- **THEN** they learn it protects both the server and the token, worded as a safety net

