## MODIFIED Requirements

### Requirement: Sharing section
The page SHALL have a Sharing section built from the `users-and-shares` report, showing:
- the number of people who can reach the server, split into Plex Home members, managed users and
  friends, and the number of pending invites;
- each library with the number of people who can see it;
- each "worth a look" item from the report as a short sentence with the number of people it applies
  to (and their names when names are shown);
- an `unused_library` item as a short sentence with the number of libraries and their titles. Library
  titles SHALL be shown even when names are hidden, because they aren't about any person;
- when names are shown, a list of people with name, type, number of libraries (or "all"), and last
  played date (or "no plays found"), with at most 20 people listed and a line saying how many more
  there are.

Sharing items SHALL NOT be added to the server's "Needs a look" list and SHALL NOT change the page's
overall status. When nobody else can reach the server, the section SHALL say so in one line.

#### Scenario: A friend can download
- **WHEN** the sharing report's `worth_a_look` has a `downloads_allowed` item and the server has no
  other issues
- **THEN** the Sharing section mentions it and the page's overall status is still "Healthy"

#### Scenario: Names hidden
- **WHEN** names are hidden and the sharing report lists three inactive people
- **THEN** the Sharing section says three people haven't played anything recently, with no names and
  no people list

#### Scenario: A long share list
- **WHEN** names are shown and 26 people can reach the server
- **THEN** 20 people are listed, followed by a line saying there are 6 more

#### Scenario: Not shared with anyone
- **WHEN** the sharing report has no people
- **THEN** the Sharing section says the server isn't shared with anyone

#### Scenario: A shared library nobody plays from
- **WHEN** names are hidden and the sharing report's `worth_a_look` has an `unused_library` item for
  "Fitness" with `days` 90
- **THEN** the Sharing section says one shared library has had no plays by the people it's shared with
  in 90+ days, names "Fitness", and the page's overall status is unchanged
