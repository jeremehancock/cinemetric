## ADDED Requirements

### Requirement: Library growth chart
The Library section SHALL show a "Storage added per month" bar chart built from the library report's
top-level `growth.months`: one bar per month, oldest on the left, each bar's height the month's `gb`.
The tallest bar SHALL be highlighted the way the busiest day is in the plays-per-day chart. Each bar
SHALL have a tooltip giving the month, the size added and the number of items added; the current
(last) month's tooltip SHALL say it is so far. Next to the chart heading the page SHALL show the
total size and number of items added over the whole period. Like the plays-per-day chart, the chart
SHALL be inline SVG with a wide and a narrow version so labels stay readable on a phone.

When every month is zero, the section SHALL say in one line that nothing was added in that period,
with no chart. When the report has no `growth` section (for example a report from an older
version), the section SHALL show no chart and no message. The chart SHALL NOT add anything to the
server's "Needs a look" list or change the page's overall status. Hiding names SHALL NOT change it,
since it contains no person's name.

#### Scenario: A year of additions
- **WHEN** the library report's `growth.months` has 12 months with sizes, the largest in March
- **THEN** the Library section shows 12 bars with March highlighted, and the heading shows the total
  size and items added

#### Scenario: Nothing added
- **WHEN** every month in `growth.months` has `added` of 0
- **THEN** the Library section says nothing was added in the last 12 months, with no chart

#### Scenario: Report without growth
- **WHEN** the library report has no `growth` field
- **THEN** the Library section is shown as before, with no chart and no error

#### Scenario: Current month tooltip
- **WHEN** the last month in `growth.months` is the current month
- **THEN** its bar's tooltip says the figure is so far this month
