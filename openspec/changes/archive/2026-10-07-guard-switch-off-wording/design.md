## Context

The guard refuses three routes Claude could use to switch it off: `/cinemetric-mods guard off` when
the request didn't come from the user, another plugin's `config.set`, and `Bash`/`Write`/`Edit` calls
that name a Claude Code settings file and mention `read_only_guard`. The last one is a text match. An
escaped key (`read_only_guard` in JSON), an edit split across two calls, or a script that builds
the key name and rewrites the file all get past it. The user-facing text says "only you can turn it
off, never Claude", which is stronger than that.

## Goals / Non-Goals

**Goals:**
- Every user-facing sentence about switching the guard off matches what the code does.
- Keep it short and plain; it's still worth saying that Claude's usual ways are refused.

**Non-Goals:**
- Tightening the settings-file check. See the decision below.
- Changing the refusal messages Claude sees, or the `/cinemetric-mods` reply. Those state the rule
  to Claude ("only the user can switch the guard off") and are accurate for the routes they refuse.

## Decisions

**Fix the wording, not the check.** Considered:
1. *Tighten the check*: decode JSON escapes before matching, and compare the whole settings file
   before and after an edit instead of the edit's text. This closes the escaped-key and split-edit
   cases, but not a program Claude writes and runs, which the guard can never see inside (the same
   limit the read-only rules already state). The promise would still be too strong, and the check
   would need to read and simulate settings files.
2. *Reword* (chosen). "Meant to be switched off only by you; Claude's usual ways are refused" is
   true today and stays true. It matches how the rest of the guard is already described: a safety
   net, not a guarantee.

**Wording used.** The website card's caveat ends with "It's meant to be turned off only by you." The
switching text and README say the guard is the exception, meant to be turned off only by the user,
that Cinemetric refuses Claude's usual ways of turning it off so Claude can't casually switch off its
own safety net, and (README and SECURITY.md) that like the rest of the guard this is a safety net,
not a lock. The `plugin.json` description ends with "Meant to be switched off only by you."

## Risks / Trade-offs

- [Softer wording makes the guard sound weaker] → It's the accurate description; overstating it is
  the worse risk for a security feature.
