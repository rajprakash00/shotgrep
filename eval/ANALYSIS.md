# shotgrep eval analysis

## Purpose

This document explains the first eval run of shotgrep. It answers three questions:

- How good is the search today?
- Where does the search fail?
- What must we do next?

TThe labels in
`eval/queries.yaml` stay frozen. The raw numbers live in [RESULTS.md](RESULTS.md).

## Source data

| Item | Value |
|---|---|
| Run date | 2026-09-21 |
| Query set | `eval/queries.yaml`, 64 queries, frozen |
| Corpus | 4 Blender films, 3,797 moments |
| Index | SigLIP base int8, index version 2 |
| Command | `uv run python -m eval --index work/index` |

Each query names one moment in one film. A result is correct when its time range
touches the labeled range, with a tolerance of 2 seconds.

## Results

Recall@5 is the share of queries with a correct result in the top 5. MRR is the
mean reciprocal rank. MRR 1.0 means that the first result is correct for every
query.

| Split | Fused Recall@5 | Fused MRR | Baseline Recall@5 | Baseline MRR |
|---|---|---|---|---|
| overall | 0.609 | 0.459 | 0.578 | 0.420 |
| easy | 0.562 | 0.484 | 0.500 | 0.458 |
| paraphrase | 0.562 | 0.393 | 0.562 | 0.285 |
| temporal | 0.625 | 0.361 | 0.562 | 0.375 |
| negation | 0.688 | 0.599 | 0.688 | 0.562 |

The fused system finds a correct result in the top 5 for 39 of 64 queries. The
mean reciprocal rank is 0.459. Thus the first correct result is near rank 2.

Latency: fused p50 is 114 ms and p95 is 144 ms. Baseline p50 is 48 ms and p95 is
61 ms. The search is fast. The fused system is 2.4 times slower than the
baseline.

## Findings

### The fusion gives a small gain

The fused system beats the baseline by 0.031 Recall@5 and 0.039 MRR. The gain is
small. The visual embedding model does most of the work. On the temporal split,
the fused MRR is lower than the baseline MRR.

### The transcript channel gives almost no results

Only 1 of 64 queries finds a transcript result. Query `easy-11` matches because
its words are almost the same as the spoken line. All other queries about speech
find no transcript result. Therefore the fused system works as a visual-only
search.

### Dialogue films are the weakest

| Film | Correct in top 5 | Dialogue |
|---|---|---|
| Big Buck Bunny | 13 of 16 | none |
| Sintel | 11 of 16 | some |
| Elephants Dream | 9 of 16 | some |
| Tears of Steel | 6 of 16 | much |

Big Buck Bunny has no dialogue and the best result. Tears of Steel has much
dialogue and the worst result. This agrees with the silent transcript channel.

### Queries about speech fail

Seven queries quote or describe a spoken line. None of them finds the right
moment. The transcript channel returns nothing for these queries. The visual
channel then returns a person, not the line.

### Queries about a position in time fail

The system has no model of story order. Five queries name a position in time,
such as "the last shot before the end credits". None of them finds the right
moment.

### Queries with negation fail

The visual model cannot represent absence. Five queries name an absent object.
None of them finds the right moment. A query for a bridge without machines
returns a bridge with machines.

### Some moments look like other moments

Eight queries fail because the target looks like a different moment. Fine detail
is a weak point. The same object in another film also causes errors.

### Failure examples

| Failure type | Query | Correct moment | First result |
|---|---|---|---|
| Spoken words | `easy-05` | a woman who searches for someone, 134 s | a woman in a city, 390 s |
| Position in time | `temporal-01` | the Big Buck Bunny title card, 25 s | a title card in Sintel, 785 s |
| Negation | `negation-11` | two people on a bridge, 349 s | the machine bridge, 222 s |
| Similar shots | `easy-02` | three rodents together, 118 s | rodents that laugh, 163 s |
| Fine detail | `paraphrase-16` | typewriter keys, 395 s | a machine scene in another film, 116 s |

## Limits of this test

- The queries do not name the film. The system searches all four films at the same time. A result from another film can match the words but not the label.
- The first run measures latency at k=5. The 2026-09-22 rerun measures latency at the service default k=10.
- The test covers retrieval only. It does not cover REST, MCP, the web player, or the ingest of new files.
- The labels are frozen. A ranking change must not edit them. A new run appends a dated table to [RESULTS.md](RESULTS.md).

## Update 2026-09-22: the dense transcript channel (action 1)

The transcript channel now retrieves by meaning as well as by words: transcript
segments are embedded with `bge-small-en-v1.5` (index version 4), a dense
channel joins the visual and lexical ones in the query service, and hits below
bge's similarity floor (0.6) are treated as noise. The frozen set was rerun at
k=10 and the dated table appended to [RESULTS.md](RESULTS.md).

| Metric | k=10 baseline | dense transcript | Change |
|---|---|---|---|
| Overall Recall@5 | 0.609 | 0.688 | +0.079 |
| Overall MRR | 0.459 | 0.495 | +0.036 |
| Sintel Recall@5 | 0.688 | 0.875 | +0.187 |
| Tears of Steel Recall@5 | 0.375 | 0.500 | +0.125 |
| Elephants Dream Recall@5 | 0.562 | 0.562 | 0.000 |
| Big Buck Bunny Recall@5 | 0.812 | 0.812 | 0.000 |
| p50 latency | 125 ms | 189 ms | +64 ms |

The queries about spoken lines that fail in the first analysis now find their
moment: `easy-05` (a woman searching for someone), `easy-06` (an old man
asking about a dragon), and `easy-10` (a man asking a woman whether a machine
freaks her out) enter the top 5 through the dense channel. Sintel and Tears of
Steel improve; the two films whose queries are visual descriptions hold their
baseline. Elephants Dream does not improve: its paraphrases score below the
similarity floor, and the ungated variant of the same channel (committed as a
rejected run in [RESULTS.md](RESULTS.md)) scored it 0.375 by letting noise
displace visual results.

What still fails:

- **Hallucinated transcript on Big Buck Bunny.** The ASR model invents 20
  "I don't know." segments over the music. They are below the floor, but they
  show that segment text is only as good as the ASR.
- **Elephants Dream paraphrases.** Its dialogue is quiet and indirect, and
  bge-small scores it below the floor. A larger embedder or a reranker is the
  next lever, not a lower gate.
- **Position in time and negation.** Actions 2 and 3 remain open; the splits
  moved with the dense channel but the failures in the first analysis stand.

## Actions

1. Repair the transcript channel. A query with different words finds nothing today. Use semantic retrieval over transcript segments, or a looser match. This is the largest expected gain. It must help Tears of Steel first. **Done in the 2026-09-22 dense transcript rerun; Tears of Steel and Sintel improved, Elephants Dream held.**
2. Make negation explicit. After retrieval, inspect the top results for the absent object. Remove the results that contain it.
3. Add time priors. A query with the word "opening" can prefer early moments. A query with the word "final" can prefer late moments.
4. Report per-film numbers. The table groups results by split only. Per-film rows show the weak film. Done in the 2026-09-22 rerun.
5. Measure latency at k=10. The default API call must appear in the table. Done in the 2026-09-22 rerun.
6. Continue the product work. The web player and the MCP server are built and tested. The hosted demo is not built (#11). The eval covers search quality only.

## Conclusion

The pipeline works. The index is portable. The search is fast. The test is
reproducible. The quality is not sufficient.

The system finds the labeled moment in the top 5 for about 6 of 10 queries.
Visual moments work best. Spoken words and positions in time do not work yet.
The transcript channel is the first repair. After the repair, we run the frozen
set again and append a new dated table.

The project solves the problem only in part. This run is a first measurement,
not a final quality claim.
