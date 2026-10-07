## Context

`playback-check` already reads every movie's and episode's audio and subtitle tracks from
`/library/metadata/{ids}`, 100 titles per request, and groups episodes by show. This skill reads the
same data and asks a different question: can the people watching understand what's said?

Before writing this, a real server was checked (read-only, 2026-10-07; about 2,000 movies and 19,000
episodes, first 500 of each sampled):

- `/:/prefs` has **no** default audio or subtitle language. The only language setting is
  `LanguageInCloud` ("Use language preferences from plex.tv"): each person's preferred languages live
  on their plex.tv account, not on the server. `openspec/ideas.md` assumed otherwise.
- Each library section has a `language` attribute, its metadata language (here `en-US` on every
  library).
- Every audio and subtitle track had `languageCode` (three letters, for example `eng`, `fra`, `zho`)
  and `languageTag` (two letters, sometimes with a region: `en`, `en-US`, `en-GB`), plus `language`
  (a name such as "English"). 3 of about 700 movie audio tracks had no language at all.
- Audio tracks carry `selected` on every file sampled (the signed-in account's choice) and `default`
  on most. A few carry `original` (25 of about 700), too few to rely on.
- Subtitle tracks carry `forced` (about 2%), `hearingImpaired`, `dub` and `original` on some tracks.
  No separate subtitle files (tracks with a `key`) were on that server, but Plex lists them the same
  way, so they need no special handling.
- 145 of 500 movies had more than one audio track; 80 of 500 had no subtitles at all.

A rough prototype of the findings was then run over the whole server, with English as the user's
language, to check the skill is worth having:

| Library | Files | Foreign, no subtitles | Main audio foreign but English subtitles | Forced-only English | Language not set | No English subtitles |
|---|---|---|---|---|---|---|
| Movies | 1,970 | 9 | 43 | 11 | 16 | 461 |
| TV | 18,921 | 54 | 113 | 154 | 526 | 3,910 |

- Real finds: Parasite (Korean audio, only a forced English track), several Studio Ghibli and Godzilla
  films with Japanese audio, Squid Game episodes with Korean audio and only forced English, The
  Grandmaster with only French subtitles.
- Probably wrong-language copies: 9 Ozark episodes and 3 And Then There Were None episodes whose only
  audio is labelled German or Italian. The skill can't tell a mislabel from a dubbed copy, but either
  is worth knowing, and it reports the labels as they are.
- One false alarm fixed in the spec: 16 Trailer Park Boys episodes had audio labelled `unk`, which the
  prototype read as a foreign language. Codes meaning "no particular language" (`und`, `unk`, `mul`,
  `mis`, `zxx`) now count as no language.
- `no_subtitles` is large, as expected, which supports keeping a separate list for each finding.

## Goals / Non-Goals

**Goals:**
- List files people probably can't follow (foreign audio, no subtitles in their language), files
  missing subtitles in a language the user names, and tracks with no language set.
- Give a short language summary per library.
- Reuse `playback-check`'s reading pattern and main audio track rule so the two skills agree.

**Non-Goals:**
- Contacting plex.tv to read each person's language preferences (a new destination for a small gain).
- Judging subtitle quality, timing or completeness, or reading subtitle text.
- Spotting short scenes in another language inside a film that's mostly in the user's language.
- Suggesting downloads, remuxes or replacements (facts only, as everywhere).
- A dashboard section. Easy to add later if someone asks.

## Decisions

**A separate skill, not part of `playback-check`.** `playback-check` answers "will this play
smoothly?"; this answers "can people understand it?". Mixing them would make one report long and
muddle both. The cost is a copied main-track rule, which is a few lines; the tests use made-up files
to keep the two in step (see the testing spec).

**The user's language: `--language`, otherwise each library's metadata language.** Alternatives:
- *Read plex.tv account preferences:* the real answer for the owner, but adds a destination to the
  security spec and still says nothing about other viewers. Rejected.
- *Always require `--language`:* safe but tedious; most people's library language is their language.
- *Library language (chosen):* right for most servers, and the report says where the language came
  from so Claude can mention it and offer `--language`. A library with no usable language gets
  `language_problem` instead of a guess.

**Matching languages by the tag's first part or the three-letter code.** Plex gives both, and people
type both ("en", "eng"). Dropping the region means `en-US` and `en-GB` audio both count as English.
A small fixed table turns the ISO 639-2 bibliographic codes people sometimes type (`fre`, `ger`,
`chi`, `dut`, `cze`, `gre`, `rum`, `per`, `arm`, `baq`, `bur`, `geo`, `ice`, `mac`, `mao`, `may`,
`slo`, `tib`, `wel`, `alb`) into the terminology codes Plex uses (`fra`, `deu`, `zho`, ...). No full
language list is shipped; names for the report come from the tracks themselves (`language_names`).

**Forced tracks don't count as subtitles.** A forced track normally covers only signs or a few lines
in another language. Counting it would hide exactly the films this skill is for. `forced_only` keeps
them visible, and `forced_subtitle_languages` shows them per file so Claude can say "it has forced
English subtitles, which usually only cover a few lines".

**"Any audio track in your language" clears `foreign_no_subtitles`, not just the main track.** A
Japanese film with an English dub is watchable: Plex picks the dub when the account prefers English.
The main track is still shown per file, so Claude can mention the original audio.

**Audio with no language can't be foreign.** If no audio track has a language, the script can't
tell, so the file is reported under `unknown_language` instead of guessed into
`foreign_no_subtitles`.

**Separate lists per finding.** `no_subtitles` can be large on an English library (80 of 500 movies
on the test server) while `foreign_no_subtitles` is usually short and matters most. One combined,
sorted list would let the long one crowd out the short one at `--limit 25`. Each finding gets its own
list and `more` count.

**No Tautulli.** Nothing here depends on watch history, so Tautulli is never contacted, even when set
up. Fewer moving parts and one destination.

**Sorting.** Movies by title (no finding is "worse" for one movie than another); shows by how many
episodes are affected, since a show with 40 affected episodes matters more than one with 1.

## Risks / Trade-offs

- [Language labels are wrong] Tracks are sometimes labelled English when they aren't, or left
  "undetermined". → The report says it goes by labels (`limits`), and unlabelled tracks are their own
  finding.
- [Library language isn't the viewer's language] Someone with an English metadata library may watch
  in Spanish. → `language` with `source: "library"` is in the report, and SKILL.md tells Claude to say
  which language was assumed and offer `--language`.
- [Large libraries] About 19,000 episodes means about 190 detail requests, the same as
  `playback-check`. → Same batching; acceptable, and SKILL.md suggests `--library` for a quicker run.
- [Two-letter vs three-letter codes for rarer languages] Some languages have no two-letter code, so
  `languageTag` may be three letters. → Matching accepts either form, and the summary uses whatever
  the track's language key is.
- [Copied main-track rule drifts] → Shared made-up fixtures in tests (task 4.3).

## Open Questions

- Should hearing-impaired (SDH) tracks be shown separately in the per-file details? Left out for
  now: they count as full subtitles, which is what matters for these findings.
- Should a later version add a dashboard section ("12 films with no subtitles you can read")? Only if
  someone asks.
