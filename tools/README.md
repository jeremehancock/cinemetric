# Development tools

Helpers for working on Cinemetric itself. Nothing here is part of the plugin (which installs from
`plugins/cinemetric/`) or the website (which is served from `website/`), so these files are never
shipped to users or published online.

- **`dashboard_screenshot.py`**: retakes the website's dashboard screenshot
  (`website/screens/dashboard.jpg`) from made-up sample data and updates its height in
  `website/index.html`. Run `python3 tools/dashboard_screenshot.py` after changing how the
  dashboard looks. Needs Google Chrome or Chromium, and Pillow (`pip install pillow`).
- **`year_in_review_screenshot.py`**: retakes the website's year-in-review screenshot
  (`website/screens/year-in-review.jpg`) from made-up sample plays and updates its height in
  `website/index.html`. Run `python3 tools/year_in_review_screenshot.py` after changing how the recap
  page looks. Same needs as the dashboard tool.
- **`shared_helpers.py`**: checks that every script's copy of a shared helper (config loading,
  address checks, the Plex client, text cleaning, snapshot reading and so on) matches. Run
  `python3 tools/shared_helpers.py` to see which copies differ, and
  `python3 tools/shared_helpers.py copy NAME --from SKILL` after fixing a helper in one script to
  copy the fix into the others. The list of shared helpers, and the scripts allowed their own copy,
  is at the top of the file. The tests run the same check. Standard library only.
