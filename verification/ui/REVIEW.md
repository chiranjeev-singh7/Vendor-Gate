# UI screenshot review

Screenshots are grouped by review pass in `round1`, `round2`, and `round3`. Each pass includes desktop (1440px) and mobile (375px) captures for the empty dashboard, sample form and JSON editor, live stepper, all three decisions, populated dashboard, resubmission diff drawer, and rules page. Contact sheets provide a quick comparison; the individual PNGs preserve full detail.

## Pass 1

The initial screenshots exposed filled black SVG icons, a cursor artifact, a transient toast over dashboard content, and a resubmission comparison below the drawer's stage list. The long full-page form captures also placed the sticky action bar across the middle of the form.

## Pass 2

Icons now use a consistent stroked SVG style. The drawer comparison moved directly below its decision card, and screenshot capture hides the cursor and temporary toast. The comparison is readable, though the documents field still appeared as dense serialized JSON.

## Pass 3

The comparison now summarizes document values as a count and type list. Form and JSON screenshots use viewport captures positioned at the editor, so the sticky action bar stays at the bottom and mobile captures show the filled state. The final screenshots show no browser console errors or page errors.

## Remaining visual notes

- At narrow widths, the runs table scrolls horizontally inside its own table container so the page itself does not overflow.
- Select and date inputs use native browser controls, so their small glyph details can vary by operating system.
- No clipping, unreadable text, or layout overflow was observed at 1440px, 768px, or 375px.
