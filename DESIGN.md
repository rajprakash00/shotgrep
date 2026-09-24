---
name: shotgrep
description: A search index for footage, rendered as a greenbar ledger.
colors:
  paper: "oklch(0.95 0.035 132)"
  card: "oklch(0.978 0.015 132)"
  paper-deep: "oklch(0.9 0.05 132)"
  ink: "oklch(0.27 0.045 145)"
  ink-soft: "oklch(0.43 0.04 145)"
  rule: "oklch(0.76 0.04 132)"
  stamp: "oklch(0.48 0.17 15)"
typography:
  display:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "2.25rem"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "normal"
  title:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "0.18em"
rounded:
  none: "0px"
  icon-tile: "6px"
spacing:
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "20": "20px"
  "32": "32px"
  "40": "40px"
  "48": "48px"
components:
  button-primary:
    backgroundColor: "{colors.stamp}"
    textColor: "{colors.card}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "12px 20px"
    height: "48px"
  button-secondary:
    backgroundColor: "{colors.paper-deep}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "10px 20px"
    height: "38px"
  button-small:
    backgroundColor: "{colors.paper-deep}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "8px 16px"
    height: "34px"
  input-search:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 14px"
    height: "48px"
  chip-example:
    backgroundColor: "{colors.paper-deep}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  card-moment:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "14px"
  notice-card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "32px"
  nav-link:
    textColor: "{colors.ink-soft}"
    typography: "{typography.label}"
---

# Design System: shotgrep

## 1. Overview

**Creative North Star: "The Archive Box"**

shotgrep's web app is an archive box lined with greenbar ledger paper: continuous-form ruling, index cards, ink lines, and an oxblood stamp for the one thing that matters. The product is a catalog for footage, so the interface borrows the materials of a working archive rather than the chrome of a SaaS dashboard. Density is a feature: cards sit close, timecodes are always visible, and the page never performs.

The system is product register, so familiarity wins where it counts. The search field looks like a search field, the player keeps native controls, and results render at full density with no reveal animation. The archival character comes from material choices (ruled paper, hard offset shadows, mono data) and never from novel affordances.

What it rejects, per PRODUCT.md: dark SaaS dashboards with purple gradients and glass cards, neon terminal cosplay, Netflix-style poster rows, AI-brand gradient text, and skeuomorphism as costume. The paper here is a surface, not a costume. No texture fights readability, and nothing pretends to be leather.

**Key Characteristics:**
- Greenbar paper surfaces (hue 132-145) with a 28px ruling and a subtle SVG grain, never pure white or untinted grey.
- Oxblood Stamp on under 10% of any screen: the primary action, focus rings, hover shadows, and kind stamps.
- Hard, unblurred offset shadows (2-6px) as the only elevation; presses physically sink by the offset.
- Square corners everywhere except the icon tile.
- Numbers always in IBM Plex Mono with tabular figures.
- No motion beyond 150ms state feedback; no entrance choreography.

## 2. Colors

A greenbar-paper light theme with deep ledger ink and one oxblood stamp. Seven tokens, all OKLCH, every neutral tinted toward the brand hue.

### Primary
- **Oxblood Stamp** (oklch(0.48 0.17 15)): the single accent. Fills the primary Search button, colors focus rings and hover shadows, stamps the kind label, and marks inline errors and danger notices. Never a background wash.

### Neutral
- **Greenbar Paper** (oklch(0.95 0.035 132)): the page surface, carrying the ruling and the grain.
- **Index Card** (oklch(0.978 0.015 132)): cards, inputs, notice panels, and the lightest surface in the system.
- **Greenbar Band** (oklch(0.9 0.05 132)): the 28px ruling band, secondary buttons, example chips, skeleton blocks, and pressed surfaces.
- **Ledger Ink** (oklch(0.27 0.045 145)): body text, headings, structural borders, and button shadows.
- **Faded Ledger** (oklch(0.43 0.04 145)): secondary text only: snippets, metadata, helper copy.
- **Ruled Line** (oklch(0.76 0.04 132)): rules, dividers, resting shadows, and the perforation line. Never body text.

### Named Rules
**The One Stamp Rule.** Oxblood Stamp covers under 10% of any screen. If two stamp-red elements compete for attention, one of them is wrong.

**The Tinted Neutral Rule.** Every neutral is tinted green (hue 132-145). Pure black, pure white, and untinted grey are forbidden.

**The Greenbar Rule.** The page surface carries the 28px ruling (Greenbar Band at 55%) under the grain. Cards, inputs, and the player stay solid Index Card, so content never sits on the ruling.

**The Icon Export Rule.** The SVG favicon hardcodes sRGB equivalents (paper #E6F4DC, ink #182C18, stamp #A8203D) because the icon pipeline does not accept OKLCH. OKLCH stays canonical everywhere else.

## 3. Typography

**Display Font:** Fraunces (with Georgia, serif fallback; weights 400 and 600, normal and italic)
**Body Font:** Archivo (with system-ui, sans-serif fallback; weights 400, 500, 600)
**Label/Mono Font:** IBM Plex Mono (with ui-monospace, monospace fallback; weights 400 and 500)

**Character:** A letterpress index card. Fraunces gives titles and asset names a warm, bookish voice. Archivo keeps prose plain and legible. IBM Plex Mono handles every number and label so data reads like it was typed onto the card. Archival without costume.

### Hierarchy
- **Display** (600, 2.25rem rising to 3rem at sm, line-height 1.05): the home hero heading only.
- **Title** (600, 1.5rem, line-height 1.2): the watch page filename.
- **Headline** (400, 1.25rem, line-height 1.3): notice card titles and player messages, in Fraunces regular.
- **Body** (400, 0.875rem, line-height 1.5): prose, snippets, helper text; max line length about 65ch on hero and notices.
- **Label** (500, 0.6875rem to 0.75rem, letter-spacing 0.16-0.22em, uppercase): buttons, nav links, metadata, count lines, kind stamps. Always mono.

### Named Rules
**The Mono For Numbers Rule.** Timecodes, durations, fps, codecs, counts, and scores are always IBM Plex Mono with tabular figures. A number set in Archivo or Fraunces is a bug.

**The Italic Is A Voice Rule.** Fraunces italic appears twice only: asset names on cards, and the single emphasized word in the hero. Body copy is never italic.

**The Uppercase Is A Label Rule.** Uppercase text is always mono, always letter-spaced, and never longer than a short label.

## 4. Elevation

The system is flat at rest and lifted only by hard offset shadows. A shadow is a second sheet of paper offset from the first, never a glow and never blurred. Depth signals state and structure: a card at rest, a card under the cursor, a button waiting to be pressed. Ambient shadows do not exist here.

### Shadow Vocabulary
- **Card at rest** (`box-shadow: 3px 3px 0 0 oklch(0.76 0.04 132)`): result cards.
- **Card on hover** (`box-shadow: 4px 4px 0 0 oklch(0.48 0.17 15)`): result card hover, paired with a 2px rise.
- **Primary button** (`box-shadow: 3px 3px 0 0 oklch(0.27 0.045 145)`): Search and Load more.
- **Small button** (`box-shadow: 2px 2px 0 0 oklch(0.27 0.045 145)`): inline retries such as Try again.
- **Chip at rest** (`box-shadow: 2px 2px 0 0 oklch(0.76 0.04 132)`), **chip on hover** (`2px 2px 0 0 oklch(0.48 0.17 15)`).
- **Input at rest** (`box-shadow: 3px 3px 0 0 oklch(0.76 0.04 132)`), **input on focus** (`3px 3px 0 0 oklch(0.48 0.17 15)`).
- **Player frame** (`box-shadow: 6px 6px 0 0 oklch(0.76 0.04 132)`).

### Named Rules
**The No Blur Rule.** Every shadow is `Npx Npx 0 0 color`. A blurred shadow is a bug.

**The Press Rule.** On `:active`, a pressable element translates by exactly its shadow offset and drops the shadow, so it sinks into the page. Buttons press 3px, small buttons 2px, and nothing ever scales.

## 5. Components

### Buttons
- **Shape:** square corners (0px radius) with a 1px Ledger Ink border.
- **Primary:** Oxblood Stamp fill, Index Card label text, mono uppercase at 0.75rem with 0.18em tracking, 12px 20px padding, 48px tall, 3px ink shadow. One per view, reserved for Search.
- **Secondary:** Greenbar Band fill and ink text, same shape, 10px 20px padding, 38px tall, 3px ink shadow. Used for Load more.
- **Small:** Greenbar Band fill, 8px 16px padding, 34px tall, 2px ink shadow. Used for notice-card retries such as Try again.
- **Danger outline:** Oxblood Stamp border and text with no shadow; fills stamp with card text on hover. Used for the inline retry after a failed Load more, where the action must read as error recovery rather than a normal step.
- **Hover / Focus:** no color change on hover; the global focus ring is 2px Oxblood Stamp at a 2px offset. Active sinks per the Press Rule.
- **Disabled:** 50% opacity with the shadow retained, never a greyed fill.

### Chips
- **Style:** Greenbar Band fill, 1px Ledger Ink at 60% opacity border (keeps the control edge above 3:1 against paper), 4px 10px padding, 0.75rem text, 2px Ruled Line shadow. They carry the example queries, introduced by a mono "From the card catalog" label.
- **State:** hover swaps the border to Ledger Ink and the shadow to Oxblood Stamp. There is no selected state.

### Cards / Containers
- **Corner Style:** square (0px).
- **Background:** Index Card.
- **Shadow Strategy:** 3px Ruled Line at rest, 4px stamp on hover with a 2px rise (see Elevation).
- **Border:** 1px Ledger Ink at 80% opacity.
- **Internal Padding:** 14px, with the thumbnail flush to the card edge.
- **Anatomy:** 16:9 thumbnail; timecode chip pinned bottom-right over the image (Index Card background, Ruled Line top and left borders); asset name in Fraunces italic; kind stamp at the top-right of the body; snippet in Faded Ledger, clamped to two lines.

### Inputs / Fields
- **Style:** 48px tall, 1px Ledger Ink border, Index Card background, mono 0.875rem text, 14px horizontal padding, 3px Ruled Line shadow, square corners.
- **Focus:** border and shadow shift to Oxblood Stamp, plus the global 2px stamp outline at a 2px offset.
- **Error / Disabled:** search failures surface as a dashed stamp notice card, never as field styling.

### Navigation
- **Header:** a 2px Ledger Ink bottom rule. The brand is Fraunces at 1.125rem semibold; a mono uppercase tagline sits centered on wide screens; `rest` and `mcp` links are mono uppercase at 11px with Ruled Line underlines that turn stamp on hover.
- **Watch page:** a mono uppercase "← Back to search" link above the player, same underline treatment.
- No side nav, no tabs, no breadcrumbs.

### Signature Components
- **Kind stamp:** the moment kind (frame / shot start / speech) in 10px mono uppercase with 0.16em tracking, stamp text inside a 1px stamp border, rotated -1 degree. It is the only rotated element in the system.
- **Timecode chip:** mono 11px tabular figures, Index Card background, Ruled Line top and left borders, pinned to the thumbnail's bottom-right corner.
- **Perforation line:** an 8px band of 1.5px Ruled Line dots at a 14px pitch, separating the hero from the results. Decorative but structural: it marks the move from query to catalog.
- **Player frame:** 1px ink border, ink video surface, 6px Ruled Line shadow, native controls, no custom chrome.
- **Page surface:** Greenbar Paper with the 28px ruling and the grain (the `paper-surface` utility); all content sits on solid Index Card or directly on the ruling.

## 6. Do's and Don'ts

### Do:
- **Do** tint every neutral green (hue 132-145) and keep the page on Greenbar Paper with its ruling and grain.
- **Do** use IBM Plex Mono with tabular figures for every number.
- **Do** keep shadows hard and offset (2-6px, zero blur) and make presses sink by exactly the offset.
- **Do** use 2px Ledger Ink rules for page structure and 1px ink borders for controls.
- **Do** keep Oxblood Stamp under 10% of the screen: one primary action, focus rings, hover shadows, kind stamps.
- **Do** keep the results grid at 1/2/3 columns with a 20px gap and let cards stay dense.

### Don't:
- **Don't** ship dark SaaS dashboards: zinc-950 surfaces, purple/blue gradients, glow accents, generic glass cards.
- **Don't** do neon terminal cosplay: green-on-black, CRT scanlines, blinking cursors as decoration.
- **Don't** build Netflix-style streaming UI: poster rows, autoplay trailers, hero carousels.
- **Don't** use AI-brand gradient text, sparkle icons, or "Powered by AI" badges.
- **Don't** use skeuomorphism as costume: leather textures, fake stitched borders, drop-shadowed photographs.
- **Don't** blur a shadow, round a corner (the icon tile is the only exception), or use pure #000 or #fff.
- **Don't** set a number in a non-mono face or a label in Fraunces.
- **Don't** animate beyond 150ms state feedback: no entrance choreography, no scroll-driven motion.
