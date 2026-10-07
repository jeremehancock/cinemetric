"""The media deletion setting (openspec/specs/conventions/spec.md): the helper every script copies."""

import inspect

import helpers
from helpers import OfflineTestCase, PREFS_SECRET, Reply, load_script, prefs_answer

# Every script with its own copy of the helper, found by looking rather than listed by hand.
MODULES = [(name, module) for name, module in ((name, load_script(name)) for name in helpers.SCRIPTS)
           if hasattr(module, "media_deletion_allowed")]


def setting(value):
    return {"Setting": [{"id": "allowMediaDeletion", "value": value}]}


class Helper(OfflineTestCase):
    def test_every_script_that_should_have_it_does(self):
        self.assertGreaterEqual({name for name, _ in MODULES}, {"setup", "library-report", "show-progress"})

    def test_copies_are_identical(self):
        first = inspect.getsource(MODULES[0][1].media_deletion_allowed)
        for name, module in MODULES[1:]:
            with self.subTest(script=name):
                self.assertEqual(inspect.getsource(module.media_deletion_allowed), first)

    def test_values(self):
        cases = [(True, True), (False, False), ("1", True), ("0", False), ("true", True), ("false", False),
                 ("maybe", None), (None, None)]
        helper = MODULES[0][1].media_deletion_allowed
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIs(helper(lambda: setting(value)), expected)

    def test_unreadable_answers_are_unknown(self):
        helper = MODULES[0][1].media_deletion_allowed

        def refused():
            raise RuntimeError("HTTP 403")
        for read in (refused, lambda: None, lambda: [], lambda: {"Setting": "junk"}, lambda: {"Setting": ["junk"]},
                     lambda: prefs_answer(None)["MediaContainer"]):
            with self.subTest(read=read):
                self.assertIsNone(helper(read))

    def test_only_a_boolean_comes_out(self):
        helper = MODULES[0][1].media_deletion_allowed
        answer = prefs_answer(True)["MediaContainer"]
        self.assertIs(helper(lambda: answer), True)
        self.assertNotIn(PREFS_SECRET, repr(helper(lambda: answer)))

    def test_every_report_script_allows_prefs(self):
        for name, module in MODULES:
            if name == "setup":
                continue
            with self.subTest(script=name):
                self.assertTrue(any(rule.match("/:/prefs") for rule in module.ALLOWED_PATHS))

    def test_connection_checks_never_read_settings(self):
        for name, module in MODULES:
            check = getattr(module, "check", None)
            if check is None:
                continue
            with self.subTest(script=name):
                self.assertNotIn("prefs", inspect.getsource(check))
