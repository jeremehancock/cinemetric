## Context

`claude plugin test` runs each `*.test.ts(x)` file under the plugin in Claude Code's own engine.
Run from a fresh clone with an empty home folder and no login, all 119 tests pass in under 10
seconds, so it can run on GitHub. The type files Claude Code writes beside a plugin
(`.claude-plugin/types/`, ignored by git) aren't needed to run the tests.

## Goals / Non-Goals

**Goals:**
- A change that breaks a mod fails the required check.
- A change to where the scripts keep settings or snapshots fails a test unless the hooks change too.

**Non-Goals:**
- Type-checking the hooks with `tsc` (the types come from the installed Claude Code and aren't in
  git).
- Running the mod tests on Windows or macOS.

## Decisions

**Install Claude Code from npm at a pinned version** (`@anthropic-ai/claude-code@2.1.293`, the
version the tests pass on now), on Node 22, which the package requires. Pinning means a new Claude
Code release can't turn the check red on an unrelated pull request; the pin is raised on purpose.
Alternative: the `curl | bash` installer. Rejected because npm pins the exact version in one line
and is easy to read in the workflow.

**Turn off nonessential network traffic** (`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`) in the job,
so the test run doesn't send telemetry or check for updates.

**Check the hooks' file locations from Python, with the answers taken from the scripts.** The test
runs the scripts' own `config_path`, `data_dir` and `snapshots_dir` with made-up environment
variables and a made-up home folder, takes the part after the made-up base folder, and checks the
hook source builds the path from the same piece after the same variable (`${home}`, `${xdg}` and so
on). It also compares the server folder and snapshot file name patterns, which are written the same
way in Python and TypeScript. Alternative: a shared JSON file both sides read. Rejected because the
scripts must stay self-contained and the hooks run in a sandbox; a test is enough.

**The test never spells out the settings file's full path.** The read-only guard refuses any command
or file that names that path, which is what it should do, so the test builds the expected text from
the scripts' answers instead of writing it out.

## Risks / Trade-offs

- [Reading TypeScript source as text breaks if the hook is reworded] → The test names the hook file
  and the piece it expected, so the fix is clear; the mods' own tests still check behavior.
- [The pinned Claude Code version ages] → Raise it when the mods need something newer; the job's
  comment says so.
