## MODIFIED Requirements

### Requirement: Standard library only
Scripts SHALL run on Python 3.10 or newer using only the Python standard library. Nothing is installed
with `pip`.

#### Scenario: A third-party package would be convenient
- **WHEN** a change would need a package outside the standard library
- **THEN** the change is done with the standard library instead, or not done
