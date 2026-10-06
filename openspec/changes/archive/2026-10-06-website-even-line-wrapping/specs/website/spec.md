## ADDED Requirements

### Requirement: Text doesn't end on a lonely word
Paragraphs, list items and captions SHALL NOT end with a single word alone on their last line, at any
width from phone to large desktop. Short text (three lines or fewer, such as feature bullets, intros,
"Ask Claude" lines, card text and notices) SHALL wrap into lines of roughly even length, so its last
line is not a word or two under a full line. This SHALL be done with CSS line wrapping, not by changing
the wording. In browsers that don't support `text-wrap: pretty`, a script SHALL keep the last two
words of each paragraph, list item and caption together, unless together they are longer than 24
characters.

#### Scenario: A short feature bullet
- **WHEN** a visitor at any width reads "Who's watching right now, on which device, and how far along
  they are."
- **THEN** if it wraps, its two lines are of similar length rather than a full line followed by
  "they are."

#### Scenario: A long paragraph
- **WHEN** a paragraph of four or more lines wraps
- **THEN** its last line has at least two words

#### Scenario: Firefox
- **WHEN** the page is viewed in a browser without `text-wrap: pretty` support, with JavaScript on
- **THEN** each paragraph, list item and caption's last two words stay on the same line, unless they
  are longer than 24 characters together

#### Scenario: Wording unchanged
- **WHEN** the page is viewed with JavaScript turned off
- **THEN** all text reads exactly as written in the HTML, only its line breaks differ
