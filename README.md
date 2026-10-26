# BrickWright

***Agentic Creation of Physically Feasible Brick Builds***  
[Ava Pun](https://avapun.com/)<sup>1</sup>,
[Kevin Dai](https://github.com/K1ngHungry)<sup>1</sup>,
[Sally Chen](https://sally-chen.github.io/)<sup>1</sup>,
[Maxwell Jones](https://maxwelljon.es/)<sup>1</sup>,
[Ruixuan Liu](https://waynekyrie.github.io/)<sup>1</sup>,
[Kangle Deng](https://dunbar12138.github.io/)<sup>2</sup>,
[Changliu Liu](https://www.ri.cmu.edu/ri-faculty/changliu-liu/)<sup>1</sup>,
[Maneesh Agrawala](https://graphics.stanford.edu/~maneesh/)<sup>3</sup>,
[Deva Ramanan](https://www.cs.cmu.edu/~deva/)<sup>1</sup>,
[Jun-Yan Zhu](https://www.cs.cmu.edu/~junyanz/)<sup>1</sup>  
<sup>1</sup>Carnegie Mellon University, <sup>2</sup>Independent researcher, <sup>3</sup>Stanford University

[![Paper](https://img.shields.io/badge/arXiv-2610.31651-b5212f.svg?logo=arxiv)](https://arxiv.org/abs/2610.31651)
[![Project Page](https://img.shields.io/badge/Website-Project%20Page-0369a1?logo=googlechrome&logoColor=white)](https://avalovelace1.github.io/brickwright/)
[![PyPI](https://img.shields.io/pypi/v/brickwright?color=a16207&logo=pypi&logoColor=white)](https://pypi.org/project/brickwright/)
[![Licence](https://img.shields.io/github/license/AvaLovelace1/brickwright?color=15803d&label=%F0%9F%93%84%20License)](https://github.com/AvaLovelace1/brickwright/blob/main/LICENSE)

---

![An agent builds a lighthouse, Van Gogh's The Starry Night, and a crab from real LEGO® parts, with no collisions or floaters, fully connected](assets/video-thumbnail.webp)

**BrickWright** enables pre-trained coding agents to generate high-fidelity, _physically feasible_ LEGO® builds from
text or image prompts by writing code with **BrickLayer**, a Python toolkit for build creation and validation. Whereas
baseline agents achieve physical validity rates ranging from only 9% (GPT-6 Luna) to 69% (GPT-6 Astra),
BrickWright-guided agents achieve **100% validity** on a sample of 512 prompts, while improving prompt adherence for
lightweight agents and maintaining it for stronger agents.

This repository contains two packages:

| Package                                 | Description                                                                                                                                                                       |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [**bricklayer**](packages/bricklayer)   | An SDK for programmatically creating and validating LEGO builds. Assemble builds from real catalog parts, check them for validity, and export to [LDraw](https://www.ldraw.org/). |
| [**brickwright**](packages/brickwright) | A framework that guides an LLM agent to generate LEGO builds with BrickLayer.                                                                                                     |

## Quickstart

1. Download this repo: `git clone https://github.com/AvaLovelace1/brickwright.git`.
2. Ask your favorite agent (Codex, Claude Code, etc.) to create a brick build following
   the [packages/brickwright README](packages/brickwright/README.md).
3. Have fun!

## `/lego-build` skill (this fork)

Use a prompt to get a validated custom model, rendered preview, live LEGO parts
price with a breakdown, and a CSV accepted by LEGO Pick a Brick's **Upload List**.

[Download the skill ZIP](skills/lego-build.zip) · [Read the skill](skills/lego-build/SKILL.md)

Extract the `lego-build` folder into your agent's personal skills directory:
`~/.codex/skills/` for Codex or `~/.claude/skills/` for Claude Code. Refresh skill
discovery or start a new session. Invoke `$lego-build create me a sunflower build`
in Codex, or `/lego-build create me a sunflower build` in clients with slash-skill
commands. It uses the current assistant to author the model; no local web server
or separate AI API key is required. First use needs Python, Git, uv, and Internet
access to install the pinned runtime. Live pricing always needs Internet access.

The default store is US/USD; specify another supported market in the prompt.
The parts CSV contains LEGO **element IDs**, including color, and quantities.
A separate breakdown CSV contains names, unit prices, totals, and availability.
Missing pieces produce clearly labeled partial files, never invented IDs/prices.
Prices exclude shipping, service fees, and additional checkout tax.

## Chat studio (this fork)

A ChatGPT-style interface for prompting custom builds, revising them in conversation,
rotating a 3D preview, downloading LDraw models, and checking live LEGO prices.

```sh
uv sync --all-packages --all-extras --group dev
codex login
uv run --all-extras uvicorn brickwright.web.app:app --host 127.0.0.1 --port 8818
```

Open http://127.0.0.1:8818. Requires the official Codex CLI. This is a local studio;
see [web/README.md](web/README.md) for frontend development and hosting requirements.

## Live LEGO Pick a Brick pricing (this fork)

This fork adds current LEGO storefront prices for generated builds. It preserves
BrickWright's generation pipeline and adds a Python client, CLI command, and
optional HTTP API. No LEGO account, paid pricing service, or API key is required.

### Try a live quote

```sh
git clone https://github.com/kimjanise/brickwright.git
cd brickwright
uv sync --all-packages --all-extras --group dev
uv run brickwright price --ldraw examples/pricing-demo.ldr --locale en-us
```

The included example is a twenty-piece tower (ten red and ten blue 2×4 bricks).
The command queries LEGO at run time and prints a JSON quote with element IDs,
unit prices, quantities, availability, purchase links, and a timestamp.

For a build you generated with BrickWright:

```sh
uv run brickwright price RECORD_ID --locale en-us
# Use --records-dir if your records live outside the default records directory.
# Or price an exported file and save the response:
uv run brickwright price --ldraw path/to/build.ldr --out price.json
```

Records must be finalized and unchanged since export. Record quotes are saved to
`out/price.json` with source and LDraw hashes, and discarded when exports are
invalidated. Standalone `.ldr` and `.mpd` inputs are parsed without executing Python.
CLI exit codes are **0** for a fully priced, orderable build, **2** for a partial
quote or unavailable pieces (JSON is still returned), and **1** for a failed lookup
or invalid input.

### HTTP endpoints

```sh
uv run --extra api uvicorn brickwright.pricing.api:app --host 127.0.0.1 --port 8817
```

Interactive API documentation is at <http://127.0.0.1:8817/docs>. The API is a
separate local server; a static GitHub Pages site cannot run these Python endpoints.
Install the optional `api` extra when running from an installed package.

| Method | Endpoint | Input |
| --- | --- | --- |
| GET | `/api/pick-a-brick/search?query=3001&locale=en-us` | Design ID, element ID, or name |
| POST | `/api/pick-a-brick/quote?locale=en-us` | JSON bill of materials |
| POST | `/api/pick-a-brick/quote/ldraw?locale=en-us` | JSON `{"ldraw": "...LDraw/MPD text..."}` |

```sh
curl 'http://127.0.0.1:8817/api/pick-a-brick/quote?locale=en-us' \
  -H 'Content-Type: application/json' \
  --data '{"items":[{"ldraw_id":"3001","color_code":4,"quantity":10}]}'
```

`color_code` is the **LDraw** color code (4 is red), translated using BrickLayer's
existing LEGO color mapping (red is LEGO color 21). Matching requires both the
exact design ID and LEGO color ID. Decorated parts, aliases, and unknown colors
are never silently substituted. If multiple exact elements exist, the client
prefers an orderable element and then the lowest listed price.

Supported storefronts: `en-us` (USD), `en-gb` (GBP), `en-ca` (CAD), `en-au` (AUD),
`de-de`, `fr-fr`, and `nl-nl` (EUR). Prices come from the chosen market; currencies
are never converted. A mismatched upstream currency is an error.

**Reading the quote:** all monetary fields ending in `_cents` are integers in
hundredths of the stated currency. `total_cents` is only populated when every
piece has a price. Otherwise it is `null`, and `known_subtotal_cents` covers just
the priced pieces. `complete` means all prices are known; `purchasable` also
requires stock and quantities within LEGO's order limits. Out-of-stock pieces
can still have a listed price. `status` on each line explains missing prices,
unmapped colors, stock shortages, or quantity limits.

The result is a **parts subtotal**, not a checkout total: shipping, service fees,
and any additional checkout tax are excluded. The timestamp records the start
of the lookup. Prices and stock may change before checkout. Duplicate BOM lines
are combined; nested model instances are counted individually. At most 200 BOM
lines, 100,000 pieces, and 1 MB of LDraw text are accepted per request. An LDraw
import that skips parts is rejected instead of returning an understated quote.

### Python use

```python
from brickwright.pricing import PickABrickClient, bom_from_build

# build is an existing bricklayer.LegoBuild.
with PickABrickClient(locale="en-us") as lego:
    quote = lego.quote(bom_from_build(build))
    print(quote.model_dump_json(indent=2))
```

The integration calls LEGO's undocumented storefront GraphQL endpoint at
`https://www.lego.com/api/graphql/PickABrickQuery`. Its query was verified against
[LEGO's Pick a Brick storefront](https://www.lego.com/en-us/pick-and-build/pick-a-brick)
and live responses on October 25, 2026. It uses `availability` and color facets;
older `inStock` / `includeOutOfStock` examples no longer match the observed API.
LEGO can change or restrict this endpoint. HTTP, schema, and pagination failures
produce an explicit error (HTTP 502) instead of fabricated prices; invalid inputs
produce HTTP 422. Requests have a 15-second network timeout, and repeated design
lookups are reused within each quote. Each new quote fetches fresh prices.

Pricing tests use mocked HTTP responses and do not contact LEGO. Run them with:

```sh
uv run --all-extras pytest packages/brickwright/tests/pricing -q
```

## Development

Contributing? Make sure to run tests, lint, format, and type-check before submitting a PR:

```sh
uv run pytest          # run the full test suite
uv run ruff check .    # lint
uv run ruff format .   # format
uv run ty check        # type-check
```

## Citation

If you've used BrickWright in your work, please cite us!

```bibtex
@misc{pun2026brickwright,
  title = {BrickWright: Agentic Creation of Physically Feasible Brick Builds},
  author = {Pun, Ava and Dai, Kevin and Chen, Sally and Jones, Maxwell and Liu, Ruixuan and Deng, Kangle and Liu, Changliu and Agrawala, Maneesh and Ramanan, Deva and Zhu, Jun-Yan},
  year = {2026},
  eprint = {2610.31651},
  archivePrefix = {arXiv},
}
```

## Acknowledgments

This work is partly supported by the Packard Foundation, Sloan Foundation, and IITP grant funded by the Korean
Government (MSIT) (No. RS-2024-00457882, National AI Research Lab Project). Ava Pun is supported by the Meshy
Fellowship, Tata Consultancy Services Presidential Fellowship, and NSERC CGRS D. Maxwell Jones is supported by the
Rales Fellowship.

---

*LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this project.*
