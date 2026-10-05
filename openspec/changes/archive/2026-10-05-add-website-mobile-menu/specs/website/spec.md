## MODIFIED Requirements

### Requirement: Accessible and responsive
The page SHALL work from phone width (360px) to large desktop without horizontal scrolling, SHALL be
usable with a keyboard alone (visible focus, a skip link), SHALL give images and icons text
alternatives or hide purely decorative ones from screen readers, and SHALL keep text contrast at WCAG AA
or better. When the visitor's system asks for reduced motion, animations SHALL be turned off.

Every header link SHALL stay reachable at every width. At phone width (640px and narrower) the header
SHALL show a menu button that opens and closes a panel holding the section links and the GitHub link.
The button SHALL report whether the menu is open to screen readers, and the menu SHALL close when a
link in it is chosen, when Escape is pressed (returning focus to the button), or when the visitor taps
outside it. Without JavaScript there SHALL be no menu button, and the header links SHALL be shown
directly in the header instead.

#### Scenario: Reduced motion
- **WHEN** the visitor's operating system has "reduce motion" turned on
- **THEN** content appears without scroll-in or background animations

#### Scenario: Phone width
- **WHEN** the page is viewed 360px wide
- **THEN** all sections stack into one column, code blocks wrap or scroll within themselves, and the
  page itself never scrolls sideways

#### Scenario: Opening the phone menu
- **WHEN** a visitor on a phone taps the menu button
- **THEN** a panel opens listing Skills, Privacy, Setup, Support and GitHub, and the button is marked
  as expanded

#### Scenario: Choosing a link from the phone menu
- **WHEN** a visitor taps Setup in the open phone menu
- **THEN** the page scrolls to the setup section and the menu closes

#### Scenario: Closing the phone menu by keyboard
- **WHEN** the phone menu is open and the visitor presses Escape
- **THEN** the menu closes and focus returns to the menu button

#### Scenario: Phone menu without JavaScript
- **WHEN** the page is viewed at phone width with JavaScript turned off
- **THEN** there is no menu button and the Skills, Privacy, Setup, Support and GitHub links are visible
  in the header
