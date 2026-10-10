## MODIFIED Requirements

### Requirement: Shows every skill
The site SHALL describe each of the plugin's skills: `setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`, `playback-check`,
`changes`, `year-in-review`, `title-lookup`, `subtitles-and-languages`, `show-progress`, `collections-and-playlists`, `watch-mix`, `export` and `dashboard`. For each one it SHALL say what the skill reports or does
and give at least one example of what to ask Claude. Each skill SHALL have a demo panel showing what
the user really gets, and nothing else: for `setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`, `playback-check`,
`changes`, `title-lookup`, `subtitles-and-languages`, `show-progress`, `collections-and-playlists` and `watch-mix`, a Claude Code terminal conversation that follows that skill's `SKILL.md` presentation
order; for `dashboard` and `year-in-review`, only a screenshot of the real page built by that skill's
script, with no terminal conversation and no tabs; for `export`, only a screenshot of a real workbook
built by that skill's script, open on its `Movies` tab in a spreadsheet program, with no terminal
conversation. The site SHALL NOT show designed graphics as if
they were a skill's output. Demo data (names, titles, numbers) SHALL be made up, never real server
data.

#### Scenario: A visitor reads the features
- **WHEN** a visitor scrolls through the features section
- **THEN** they see all eighteen skills, each with a description, an example request and a demo panel
  in the skill's real output format

#### Scenario: Export demo
- **WHEN** a visitor reaches the export section, with or without JavaScript
- **THEN** the demo panel shows a screenshot of a workbook built from made-up titles, open on its
  `Movies` tab with the other tabs visible along the bottom, and there is no terminal conversation

#### Scenario: Dashboard demo
- **WHEN** a visitor reaches the dashboard section, with or without JavaScript
- **THEN** the demo panel shows the dashboard screenshot and its caption, and there is no tab bar or
  terminal conversation

#### Scenario: Year in review demo
- **WHEN** a visitor reaches the year-in-review section, with or without JavaScript
- **THEN** the demo panel shows a screenshot of a whole-server recap built from made-up data, with no
  names on it, and there is no tab bar or terminal conversation
