## Context

`dashboard.py` builds its page from the JSON of other report scripts, which it runs as subprocesses in
a thread pool (`SOURCES` and `collect()`). Each report gets a section rendered by fixed rules; a
failed report becomes a short "Couldn't load ..." note, and its error goes into `sections_missing`.
A saved "hide names" preference removes viewer names from the watch section.

`users_and_shares.py` (0.8.0) prints `people`, `libraries`, `totals`, `worth_a_look` and
`unavailable`. For a non-owner it fails with `OWNER_ONLY`. It reads last played dates from Tautulli
when set up, otherwise one small watch history request per accepted person, so it adds little time.

## Goals / Non-Goals

**Goals:**
- One Sharing section that answers "who can reach my server, and is anything worth a look?" at a
  glance, consistent with the other sections.
- Hidden names stay hidden everywhere, including the share list.
- No new network behavior: the dashboard still only runs the report scripts.

**Non-Goals:**
- Showing everything the `users-and-shares` skill can say (download and restriction details for every
  person). The skill is the place for detail; the dashboard links nothing and shows a summary.
- Changing `users_and_shares.py` or adding options for the dashboard.
- Making sharing items affect the overall status pill.

## Decisions

**Run it as a fourth source, with default options.** Added to `SOURCES` as `sharing`, with no extra
arguments (90-day inactive threshold, the same as asking the skill). The thread pool grows from 3 to
`len(SOURCES)` workers so it runs alongside the others rather than after them. Alternative considered:
importing the script's functions. Rejected because every source is a subprocess today, which keeps
each script self-contained and gives exactly its read-only behavior.

**Its own section, not "Needs a look".** The server card's "Needs a look" list drives the overall
status ("Healthy", "Mostly fine", "Needs attention"). Sharing items are facts the owner may well have
chosen ("all libraries" for family, downloads for a friend who travels), so putting them there would
make many healthy servers look "Mostly fine". They're listed inside the Sharing section with a neutral
style. Alternative considered: adding them as "info" items to "Needs a look". Rejected for the same
reason, and because "Needs a look" has no neutral level today.

**Layout.** A wide card after the library section, matching the existing wide watch and library
cards: a row of small counts (people, Plex Home, managed, friends, pending), a compact library table
(library name, number of people), the worth-a-look sentences, then the people list when names are
shown. The people list is capped at 20 rows, sorted the way the report sorts them (Plex Home,
managed, friends, then name), with "and N more" after, so a server shared with many friends doesn't
produce a huge page.

**Hidden names: counts only.** When names are hidden, the people list is left out and each
worth-a-look sentence uses a count ("3 people haven't played anything in 90+ days"). Library rows are
counts in both modes, so they never carry names.

**Friendly failure text.** Errors from report scripts are shown as they are today. For this source,
the leading `OWNER_ONLY: ` / `NOT_CONFIGURED: ` code is stripped before display, since the message
after it is already plain English. `sections_missing` keeps the full error so Claude can recognize it.

**SKILL.md.** The first-time online publishing note already offers to hide viewer names; it now says
the page also lists the people the server is shared with. The summary step can mention sharing items
in one line, without treating them as problems.

**Website screenshot.** The dashboard demo must be a screenshot of the real page made from invented
data. The existing invented data set gets a matching made-up `users-and-shares` report (the same names
as the website demos: sam, jordan, alex, riley and so on), and the screenshot is retaken.

## Risks / Trade-offs

- [The share list is personal, and the page may be published online] → Same protection as viewer
  names: the hide-names preference covers it, and SKILL.md mentions it before the first publish.
- [A slow plex.tv makes the dashboard slower] → It runs in parallel with the library report, which is
  usually the slowest source, and the existing 30-minute limit still applies.
- [Non-owners always see a failed Sharing section] → The note says plainly that only the owner can see
  this, so it doesn't read as a fault.
- [The page grows] → One card; the people list is capped at 20.

## Migration Plan

Additive. Existing saved preferences (destination, online page, hide names) keep working; the next
build simply has one more section. Rollback is reverting `dashboard.py` and `SKILL.md`.

## Open Questions

- Should the Sharing section show per-person download and restriction details? Left out to keep the
  card compact; easy to add if wanted.
