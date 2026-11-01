# Root-cause diagnosis for plantation yield

**Live demo: https://dhaneswaramandrasa.github.io/plantation-root-cause/**

[![Demo: a pulpwood plantation of eucalyptus and acacia grows block by block, the diagnosis checks run one at a time and colour the ground under weak blocks, the trees grow after the fixes, then the step-by-step diagnosis for two blocks](docs/demo-3d.gif)](https://dhaneswaramandrasa.github.io/plantation-root-cause/)

An interactive, simulated version of a project I led at iZeno for an agriculture client: when a plantation block grows poorly, is it the land, the pesticide, the species or something else? We built the diagnosis with the client's foresters so the field team fixes the right thing. Acting on it lifted yield by 18%. Case study: [Root-cause diagnosis for plantation yield](https://dhaneswara-mandrasa.vercel.app/project-root-cause).

Client data can't be published, so this demo uses **a made-up pulpwood plantation of eucalyptus and acacia, 455 blocks of 25 ha**. The method is the same; the numbers are not real results, except that the before and after total is set to the real +18%.

## What it shows

The page plays the story once on load, and "Play again" replays it.

| Part | What happens |
| --- | --- |
| The plantation | Trees grow in every block. Each block's trees are as tall and as green as the block is growing against the benchmark for its age; slow blocks have short, yellow trees, and disease leaves gaps |
| The checks | The checklist runs one check at a time: rainfall, disease, weed control, land, planting stock, fertiliser. The ground under the blocks that fail each check takes that cause's colour |
| The fixes | The trees in fixed blocks grow and green up while a counter goes from 100 to 118 |
| One block | Click any block to fly to it and see the checks it went through with the evidence at each step, for example: growth 46% of the benchmark, rainfall normal, disease under 6%, weed control on time, land fails (peat, pH 4.2). Then the cause, the fix, the block's growth after the fix, and its loss per cause from the growth model |
| Before and after | Switch between the two at any time. The panel shows plantation growth indexed (100 before, 118 after) and every block's growth before and after |

## The method

1. **Join the records per block.** Land (drainage, soil pH, slope), planting stock (eucalyptus clone or acacia seedlings, planting year), weed control (days the herbicide round was late, product used), rainfall, disease (share of trees with wilt or root rot), fertiliser (share of the recommended dose), and growth as mean annual increment in m³ of wood per hectare per year.
2. **Model what drives growth.** A regression of log growth against the benchmark for the stand's age on those records (R² 0.94 here). For each block, each coefficient times the block's distance from good practice is that cause's loss in m³/ha/yr.
3. **Walk the foresters' checklist.** In the order they asked for: is the block below its age benchmark; was rainfall normal; is disease under control; was weed control on schedule with the right herbicide; is the land in good shape; is the planting stock a current clone; was the full fertiliser dose applied. The first check that fails is the cause. If every check passes, the model's largest loss goes to a forester to review.
4. **Check the two against each other.** The checklist and the model's largest loss agree on 84% of weak blocks. Where they don't, the block's ranked loss list shows what else to look at.
5. **Act and measure again.** Each cause has a field fix (herbicide rounds back on schedule, drains cleared and liming, extra fertiliser now and a current clone at replanting, and so on) and a share of the modelled loss it recovers in a year.

| Cause | Blocks | Share of lost growth |
| --- | --- | --- |
| Land | 150 | 32% |
| Species (planting stock) | 74 | 25% |
| Fertiliser | 13 | 16% |
| Pesticide (weed control) | 51 | 13% |
| Weather | 33 | 9% |
| Pests and disease | 10 | 5% |

Fertiliser is a small number of blocks but a large share of the loss, because underdosing shows up as a secondary cause on many blocks whose first cause is something else.

## Data

| Part | Real or synthetic |
| --- | --- |
| Plantation, blocks and every record | Synthetic. Hidden effects of drainage, soil, slope, planting stock, weed control delay, rainfall, disease and fertiliser drive growth, with noise the records never see. `scripts/build_data.py` |
| Benchmark growth by stand age | A typical short-rotation curve: 8 m³/ha/yr in the first year, about 30 from year four |
| Recovery after the fixes | Recovery rates per cause, with one common scale (0.98) so the plantation total lands on the real +18% |

## Run it

```bash
pip install -r requirements.txt     # numpy only
python scripts/build_data.py        # a second or two; writes web/data/estate.json
python -m http.server -d web 8000   # open http://localhost:8000
```

`web/index.html` is a single static page (deck.gl from a CDN, no basemap). The trees are drawn in code: a cylinder trunk and a sphere crown per tree, 25 trees a block. `?block=A0813` opens a given block, `?view=after` opens the after view, `?still` skips the opening story and `?embed` hides the code link. GitHub Actions deploys `web/` to Pages on every push to `main`.

## Layout

```
scripts/build_data.py   synthetic plantation, growth model, loss per cause, checklist, fixes, JSON export
web/index.html          the demo
web/data/estate.json    everything the demo reads
```
