# Corpus attribution

The films in the shotgrep corpus are released by the Blender Foundation under
Creative Commons Attribution licenses. This file is the canonical attribution
text: the README ships these lines verbatim, and the demo renders each asset's
`attribution` string from `corpus/manifest.json`.

No media binaries are committed to git. Run `python3 corpus/fetch.py` to
download and verify them into `corpus/media/` (gitignored).

## Ready-to-ship attribution

```
Big Buck Bunny (2008) © Blender Foundation / Peach open movie project. Source: https://peach.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
Sintel (2010) © Blender Foundation / Durian open movie project. Source: https://durian.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
Tears of Steel (2012) © Blender Foundation / Mango open movie project. Source: https://mango.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
Elephants Dream (2006) © Blender Foundation / Orange open movie project. Source: https://orange.blender.org/. License: CC BY 2.5 — https://creativecommons.org/licenses/by/2.5/. No changes; playback uses generated proxies.
```

Each line carries the title, author, source URI, and license URI that CC BY
requires. The films themselves are unmodified; ingest derives proxies,
thumbnails, transcripts, and embeddings from them, and those derivatives stay
under the film's license.

## Per-asset verification

Licenses were verified against the films' official project pages on
2026-09-19. `python3 corpus/fetch.py --verify-licenses` re-checks each page for
the quoted license statement.

### Big Buck Bunny

- Title: Big Buck Bunny (2008)
- Author: Blender Foundation / Peach open movie project
- Source: <https://peach.blender.org/>
- License: CC-BY-3.0 — <https://creativecommons.org/licenses/by/3.0/>
- Evidence: <https://peach.blender.org/about/> — "licensed under the Creative Commons Attribution 3.0 license"

### Sintel

- Title: Sintel (2010)
- Author: Blender Foundation / Durian open movie project
- Source: <https://durian.blender.org/>
- License: CC-BY-3.0 — <https://creativecommons.org/licenses/by/3.0/>
- Evidence: <https://durian.blender.org/sharing/> — "Creative Commons Attribution 3.0"

### Tears of Steel

- Title: Tears of Steel (2012)
- Author: Blender Foundation / Mango open movie project
- Source: <https://mango.blender.org/>
- License: CC-BY-3.0 — <https://creativecommons.org/licenses/by/3.0/>
- Evidence: <https://mango.blender.org/sharing/> — "Creative Commons Attribution 3.0"

### Elephants Dream

- Title: Elephants Dream (2006)
- Author: Blender Foundation / Orange open movie project
- Source: <https://orange.blender.org/>
- License: CC-BY-2.5 — <https://creativecommons.org/licenses/by/2.5/>
- Evidence: <https://orange.blender.org/press/> — "licensed as “Creative Commons Attribution 2.5”"
- Note: standalone soundtrack releases from the same project are licensed
  separately as CC BY-NC-ND 2.5. The film itself, as released, is CC BY 2.5.
