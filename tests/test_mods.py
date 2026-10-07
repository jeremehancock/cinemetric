"""Mods: the files that make them load on every supported Claude Code, and the website's Mods section.

The mods' own behavior is tested by `claude plugin test plugins/cinemetric` (plugins/cinemetric/tests/);
see openspec/specs/mods/spec.md and openspec/specs/website/spec.md.
"""

import html.parser
import json
import os
import unittest

from helpers import ROOT

PLUGIN = os.path.join(ROOT, "plugins", "cinemetric")
SITE = os.path.join(ROOT, "website", "index.html")


def read_json(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return json.load(f)


class Sections(html.parser.HTMLParser):
    """Collects each <section id>'s text, and every data-copy value, nav link and in-page link."""

    def __init__(self):
        super().__init__()
        self.text = {}
        self.copy = set()
        self.nav = []
        self.links = []
        self._section = None
        self._in_nav = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and attrs.get("id"):
            self._section = attrs["id"]
            self.text[self._section] = ""
        if tag == "nav":
            self._in_nav = True
        if tag == "a" and attrs.get("href", "").startswith("#"):
            (self.nav if self._in_nav else self.links).append((self._section, attrs["href"]))
        if "data-copy" in attrs:
            self.copy.add(attrs["data-copy"])

    def handle_endtag(self, tag):
        if tag == "section":
            self._section = None
        if tag == "nav":
            self._in_nav = False

    def handle_data(self, data):
        if self._section:
            self.text[self._section] += data


def site():
    parser = Sections()
    with open(SITE, encoding="utf-8") as f:
        parser.feed(f.read())
    return parser


class PluginFiles(unittest.TestCase):
    def test_hooks_file_works_with_and_without_mods(self):
        hooks = read_json(PLUGIN, "hooks", "hooks.json")
        self.assertEqual(hooks["modules"], ["./register.ts"])
        # The old-style section is what lets Claude Code before 2.1.260 load the plugin at all.
        start = hooks["hooks"]["SessionStart"][0]
        self.assertEqual(start["matcher"], "startup")
        self.assertIn("mods_notice.py", start["hooks"][0]["command"])

    def test_guard_starts_on_and_status_line_starts_off(self):
        settings = read_json(PLUGIN, ".claude-plugin", "plugin.json")["userConfig"]
        self.assertEqual(settings["read_only_guard"]["type"], "boolean")
        self.assertIs(settings["read_only_guard"]["default"], True)
        self.assertEqual(settings["library_status_line"]["type"], "boolean")
        self.assertIs(settings["library_status_line"]["default"], False)


class WebsiteMods(unittest.TestCase):
    def setUp(self):
        self.site = site()

    def test_mods_section_sits_between_dashboard_and_privacy(self):
        order = list(self.site.text)
        self.assertEqual(order.index("mods"), order.index("skill-dashboard") + 1)
        self.assertEqual(order.index("privacy"), order.index("mods") + 1)

    def test_mods_section_says_what_and_where(self):
        text = self.site.text["mods"]
        for words in ("Claude Code", "nothing extra to install", "Read-only guard", "On by default",
                      "Library status line", "Off by default", "status", "safety net", "/config",
                      "meant to be turned off only by you", "usual ways", "2.1.260"):
            self.assertIn(words, text)
        # The settings check can be worked around, so the site mustn't promise more.
        for words in ("never Claude", "only you can turn it off"):
            self.assertNotIn(words, text)

    def test_guard_card_and_privacy_mention_the_token(self):
        self.assertIn("hides your Plex token and Tautulli API key", self.site.text["mods"])
        self.assertIn("keeps your Plex token and Tautulli API key out of Claude's sight",
                      self.site.text["privacy"])
        self.assertIn("safety net", self.site.text["privacy"])
        # Hiding can be worked around, so the site mustn't promise more.
        for words in ("never see", "can't see your token", "completely"):
            self.assertNotIn(words, self.site.text["mods"])

    def test_mods_commands_can_be_copied(self):
        self.assertIn("/cinemetric-mods", self.site.copy)
        self.assertIn("/cinemetric-mods status on", self.site.copy)
        # The guard is meant to be switched off only by the user, so it isn't the switching example.
        self.assertNotIn("/cinemetric-mods guard off", self.site.copy)

    def test_nav_and_privacy_link_to_mods(self):
        self.assertIn((None, "#mods"), self.site.nav)
        self.assertIn(("privacy", "#mods"), self.site.links)

    def test_setup_mentions_the_mods_without_adding_a_step(self):
        text = self.site.text["setup"]
        self.assertIn("Up and running in four steps.", text)
        self.assertIn("Mods (optional)", text)
        self.assertIn(("setup", "#mods"), self.site.links)

    def test_setup_states_the_claude_code_versions(self):
        text = self.site.text["setup"]
        self.assertIn("2.1.75", text)
        self.assertIn("2.1.260", text)


if __name__ == "__main__":
    unittest.main()
