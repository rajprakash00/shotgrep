# Recorded ingest: an arbitrary file, end to end

The corpus is curated; this recording proves the pipeline works on a file it
has never seen. It ingests a public-domain NASA/JPL short that is not part of
the corpus and prints every stage's wall-clock time.

- **Recording:** [ingest.cast](ingest.cast) (asciinema v2)
- **Machine-readable timings:** [ingest.timings.json](ingest.timings.json)

Play the recording with:

```sh
uvx asciinema play docs/demo/ingest.cast
```

## Source file

| | |
|---|---|
| Title | Mars in a Minute: How Do You Choose a Landing Site? |
| Author | NASA Jet Propulsion Laboratory |
| License | Public domain ([Commons file](https://commons.wikimedia.org/wiki/File:Mars_in_a_Minute-_How_Do_You_Choose_a_Landing_Site-.webm)) |
| URL | https://upload.wikimedia.org/wikipedia/commons/f/fb/Mars_in_a_Minute-_How_Do_You_Choose_a_Landing_Site-.webm |
| SHA-256 | `a32a55492177632af63b562b77d220dfc6e653f81349db21458685c95723127e` |
| Size / duration | 6.3 MB, 60.1 s, 1920×1080 VP9 + Opus |

## Reproduce

```sh
curl -L -o mars_in_a_minute.webm \
  "https://upload.wikimedia.org/wikipedia/commons/f/fb/Mars_in_a_Minute-_How_Do_You_Choose_a_Landing_Site-.webm"
sha256sum mars_in_a_minute.webm   # a32a55492177632af63b562b77d220dfc6e653f81349db21458685c95723127e
scripts/record_ingest.sh mars_in_a_minute.webm
```

The script refuses to reuse a work directory, runs
`shotgrep ingest --verbose`, and prints the stage table below. The recording
was made by running the same script under `asciinema rec`.

## Measured timings

60.1 s of 1080p video ingested in 72 s wall clock (0.83× realtime) on a 3-core
machine with CUDA. ASR is the dominant stage; on the same machine, forcing the
CPU path takes ASR from 29 s to 194 s for the same clip.

| Stage | Wall clock |
|---|---|
| probe | 0.1 s |
| proxy | 8.8 s |
| shots | 8.7 s |
| asr | 29.2 s |
| frames | 5.5 s |
| embed | 13.6 s |
| index | 0.3 s |
| **total** | **72 s** |

The run produced 73 moments, an 11-segment / 179-word transcript with word
timestamps, thumbnails, and a playable proxy, and ended with manifest status
`complete`. Transcript excerpt:

> 3.02–7.50 s — "How do you choose a landing site? So you want to study Mars
> with a lander or rover,"
>
> 50.46–56.26 s — "sites. When you find the best spot to land, work, and
> discover, you've found your new home on Mars."

The work directory is disposable; delete it and rerun the script.
