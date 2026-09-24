# Product

## Register

product

## Users

- **Editors and creators** with a folder of footage. They know the moment they want and cannot scrub to it. Their context is a browser next to an editor or file manager; patience is low, trust is earned by result quality.
- **Developers and agent builders** evaluating shotgrep from the README. They want to see the read contract, the latency, and the MCP surface quickly, then decide whether to self-host.
- **Demo visitors** who clicked a link. They get one query to be convinced the thing works.

## Product Purpose

Turn video into a searchable index and return the exact moment, not a vague range. The web app is the visible half of one query service: search, results with thumbnails and timecodes, and a player that opens at the moment. Success is a visitor typing a sentence and landing on the right frame within one interaction, with the numbers behind it credible.

## Brand Personality

Precise, wry, archival. A careful technician with a librarian's streak. The name is a pun on `grep`, and the product treats footage like a corpus to be indexed and queried. Copy is short, concrete, and evidence-first: timecodes, scores, kinds, counts. No hype adjectives, no exclamation marks. The tone is that of a good man page, not a landing page.

## Anti-references

- Dark SaaS dashboards: zinc-950 surfaces, purple/blue gradients, glow accents, generic glass cards.
- Neon terminal cosplay: green-on-black, CRT scanlines, blinking cursors as decoration.
- Netflix-style streaming UI: poster rows, autoplay trailers, hero carousels.
- AI-brand gradient text, sparkle icons, "Powered by AI" badges.
- Skeuomorphism as costume: leather textures, fake stitched borders, drop-shadowed photographs.

## Design Principles

1. **The result is the interface.** Frames, timecodes, kinds, and snippets do the persuading. Chrome stays quiet.
2. **Evidence over decoration.** Show the score, the model name, the duration, the count, the timestamp. Numbers are the brand.
3. **One cognitive model across surfaces.** The web player, REST, MCP, and the CLI describe the same result contract; the web should feel like the CLI's counterpart, not a different product.
4. **Material, not mimicry.** A tactile, physical feel (paper, card, film, ink) comes from color, type, and structure, never from textures that fight readability.
5. **Fast is a feature.** Search has no ceremony between arrival and typing; results render at full density with no reveal animation.

## Accessibility & Inclusion

- WCAG 2.1 AA: contrast 4.5:1 body text, 3:1 large text and UI boundaries, visible focus rings on every interactive element.
- Color is never the only signal (kind, active state, and selection must read in grayscale).
- Respect `prefers-reduced-motion`: hover transitions optional, no scroll-driven motion required to understand content.
- Keyboard-first: search reachable on load, results and player fully operable without a pointer.
