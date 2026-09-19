# Test fixtures

`clip.mp4` — a 10-second excerpt used by the ingest and read contract tests.

- Source: *Tears of Steel* (2012), Blender Foundation / Mango open movie project — CC BY 3.0
- Derived from: `corpus/media/tears_of_steel_720p.mov` (`corpus/manifest.json`), time range 00:00:23–00:00:33
- Changes: excerpted, downscaled to 320x134, re-encoded to H.264/AAC
- Regenerate from a verified corpus checkout:

```sh
ffmpeg -ss 23 -i corpus/media/tears_of_steel_720p.mov -t 10 -vf scale=320:-2 \
    -c:v libx264 -preset slow -crf 30 -pix_fmt yuv420p -c:a aac -ac 1 -b:a 48k \
    -movflags +faststart tests/fixtures/clip.mp4
```

Dialogue in the excerpted range, from the film's official English subtitles
(`https://download.blender.org/demo/movies/ToS/subtitles/TOS-en.srt`):

| Time | Line |
|---|---|
| 00:00:23 | You're a jerk, Thom. |
| 00:00:25 | Look Celia, we have to follow our passions; |
| 00:00:27 | ...you have your robotics, and I just want to be awesome in space. |
| 00:00:30 | Why don't you just admit that you're freaked out by my robot hand? |
