# Choose the figure by the question

| Reader question | Figure | Suggested helper |
|---|---|---|
| What happens in what order? | Labeled boxes and directed arrows | `box`, `arrow` |
| How do the parts fit together? | Component diagram with groups | `box`, `group`, `path_arrow` |
| How do observations vary by condition? | Individual points and a summary interval | `dot_strip` |
| How large are the effects across outcomes? | Estimates and intervals around a reference | `forest` |
| How does a measure change over time? | Lines with optional time annotations | `line_chart`, `events` |
| Where do two measurements agree? | Scatter plot with a diagonal | `scatter(..., diag=True)` |
| How many cases fall in each category? | Bars from zero with a labeled axis | `bar_chart` |
| How does composition change? | Stacked bars with a common ordering | `stacked_bar` |
| Where are the largest values in a matrix? | Heatmap with numbers in the cells | `heatmap` |
| How does a quantity split across stages? | Sankey diagram with a common width scale | `sankey` |

## Keep the evidence visible

- For `dot_strip`, pass one value list per condition as `groups`, the interval endpoints as `ci`, and the sample unit as `unit`. Use `err_kind="ci95"`, `"sd"`, or `"sem"` to match the analysis.
- Use a shared axis across panels when comparing magnitudes. If each panel needs its own scale, tell the reader in the caption.
- For heatmaps, use a shared scale when colors need to be comparable across columns. If columns represent different units, label the scale accordingly and retain the numeric labels.
- For Sankey diagrams, use consistent units throughout and check that incoming and outgoing amounts balance at intermediate nodes.
- For charts based on an equation, compute the plotted values from the equation. Preserve the script alongside any inputs needed to reproduce the figure.
