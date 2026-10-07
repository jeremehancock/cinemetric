"""Things that are copied or listed in several places stay in step (openspec/specs/testing/spec.md).

- Every copy of a shared helper matches (the list lives in tools/shared_helpers.py).
- Every script, plugin.json and marketplace.json give the same version.
- The tests know about every skill script.
"""

import importlib.util
import json
import os

from helpers import ROOT, SCRIPTS, SKILLS_DIR, OfflineTestCase, load_script


def load_tool():
    path = os.path.join(ROOT, "tools", "shared_helpers.py")
    spec = importlib.util.spec_from_file_location("cinemetric_shared_helpers_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def read_json(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


class SharedHelpers(OfflineTestCase):
    def test_every_copy_matches(self):
        problems = tool.problems()
        self.assertEqual(problems, [], "Copies of a shared helper differ. Fix with "
                         "python3 tools/shared_helpers.py copy NAME --from SKILL\n" + "\n".join(problems))

    def test_every_listed_helper_is_shared(self):
        # A helper that was renamed or removed would otherwise be checked against nothing.
        for name in tool.SHARED:
            with self.subTest(helper=name):
                self.assertGreaterEqual(len(tool.copies(name)), 2)

    def test_scripts_allowed_to_differ_exist(self):
        for name, allowed_to_differ in tool.SHARED.items():
            for skill in allowed_to_differ:
                with self.subTest(helper=name, script=skill):
                    self.assertIn(skill, SCRIPTS)
                    self.assertIsNotNone(tool.read_copy(tool.scripts()[skill], name))

    def test_tool_finds_the_same_scripts_as_the_tests(self):
        self.assertEqual(sorted(tool.scripts()), sorted(SCRIPTS))


class OneVersion(OfflineTestCase):
    def test_scripts_and_manifests_give_the_same_version(self):
        version = read_json("plugins", "cinemetric", ".claude-plugin", "plugin.json")["version"]
        [listing] = read_json(".claude-plugin", "marketplace.json")["plugins"]
        self.assertEqual(listing["version"], version, "marketplace.json")
        for skill in SCRIPTS:
            with self.subTest(script=skill):
                self.assertEqual(load_script(skill).VERSION, version)


class EveryScriptIsKnown(OfflineTestCase):
    def test_helpers_lists_every_skill_script(self):
        on_disk = {}
        for skill in sorted(os.listdir(SKILLS_DIR)):
            folder = os.path.join(SKILLS_DIR, skill, "scripts")
            if os.path.isdir(folder):
                on_disk[skill] = sorted(f for f in os.listdir(folder) if f.endswith(".py"))
        self.assertEqual(on_disk, {skill: [name] for skill, name in SCRIPTS.items()},
                         "Add the new script to SCRIPTS in tests/helpers.py")
