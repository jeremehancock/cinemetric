"""The README, SECURITY.md and website say where Cinemetric's promise ends: it controls only what its
own skills do. See "Honest about what Cinemetric can't control" in openspec/specs/security/spec.md
and "Matches the project's promises" in openspec/specs/website/spec.md."""

import html
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def page_text():
    """The website's text with tags removed and spacing made ordinary."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", read("website", "index.html")))
    return re.sub(r"\s+", " ", text)


def plain(markdown):
    """Markdown text with quote markers, bold and line breaks removed."""
    text = re.sub(r"^> ?", "", markdown, flags=re.M).replace("**", "")
    return re.sub(r"\s+", " ", text)


SENTENCE = "Cinemetric only controls what its own skills do"
# Ways around the guard the wording must never spell out.
NOT_SAID = ("get around the guard", "get past the guard", "bypass", "/dev/tcp")


class SafetyWording(unittest.TestCase):
    def test_website_has_its_own_notice_about_changes(self):
        text = page_text()
        notice = text.split("Changes are up to you", 1)[1].split("Support", 1)[0]
        for words in ("Cinemetric only reads", "Claude Code shows you each command first",
                      "before you approve", "Allow media deletion"):
            self.assertIn(words, notice)
        # The caution beside it is about reports only.
        caution = text.split("AI can make mistakes", 1)[1].split("Changes are up to you", 1)[0]
        self.assertNotIn("approve", caution)

    def test_readme_caution_says_it_and_links_to_security(self):
        caution = plain(read("README.md").split("AI can make mistakes.", 1)[1].split("\n\n", 1)[0])
        self.assertIn(SENTENCE, caution)
        self.assertIn("SECURITY.md", caution)

    def test_security_lists_the_limits_and_the_plex_settings(self):
        limits = plain(read("SECURITY.md").split("## What the skills do not protect against", 1)[1])
        for words in ("can't stop Claude from changing your server if you ask it to",
                      "permission prompts are your last check",
                      "Allow media deletion", "Backup database every three days"):
            self.assertIn(words, limits)

    def test_early_days_note_is_gone(self):
        self.assertNotIn("Early days", page_text())
        self.assertNotIn("Early days", read("README.md"))

    def test_issues_are_still_linked(self):
        issues = "https://github.com/jeremehancock/cinemetric/issues"
        self.assertIn(issues, read("website", "index.html"))
        self.assertIn(issues, read("README.md"))

    def test_no_ways_around_the_guard(self):
        for text in (page_text(), plain(read("README.md")), plain(read("SECURITY.md"))):
            for words in NOT_SAID:
                self.assertNotIn(words, text.lower())


if __name__ == "__main__":
    unittest.main()
