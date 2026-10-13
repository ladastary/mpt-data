# Simulator page

`index.html` is the MPT Portfolio Simulator: one self-contained file with `data/latest.json` embedded.

| File | Role |
|---|---|
| `template.html` | The page source (edit this, not `index.html`) |
| `build_page.py` | Embeds `data/latest.json` into the template |
| `test_page.mjs` | Runs the page's self-tests headless (Node, no packages) |
| `index.html` | Built page, refreshed by the monthly workflow after the data run |

The workflow rebuilds and tests the page after each data run. A Claude scheduled task republishes `index.html` to the live artifact on the 4th of each month.
