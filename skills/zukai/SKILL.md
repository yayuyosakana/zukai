---
name: zukai
description: >-
  Create and check SVG diagrams and charts for Markdown, reports, tutorials, and slides.
  Use when explaining a workflow, system architecture, experiment setup, or results comparison,
  or when asked to review a figure. Handles diagrams, learning curves, scatter plots, and charts
  with uncertainty. 図解、処理フロー、モデル構成、研究結果のグラフを描いて点検する。
license: MIT
---

# zukai

Use a figure when it helps the reader follow a multistep process, see how parts fit together, or compare values. A single figure should answer one question. Read [the chart and diagram guide](references/patterns.md) when the form is unclear.

1. Decide where the figure will appear and how wide it will be. Pass `display_px` for Markdown or HTML, or `place_mm` and `target="slide"` for a slide. Size text for the placed figure.
2. Write down what the figure should show, where the reader should look first, and where the numbers come from. Keep the source with the generation script. Label synthetic data when it is used for a demonstration.
3. Draw with `Fig` from the bundled `scripts/svglib.py`. Resolve imports relative to this skill or to your generation script. Keep related panels on comparable scales when readers need to compare them.
4. Save the SVG, read the warnings from `Fig.save()`, and run `python3 /path/to/zukai/scripts/check_svg.py path/to/figure.svg` with the installed skill path. Fix overlaps by moving elements or making more room. Preview the rendered figure when a warning is ambiguous or layout matters.
5. Embed using a path relative to the Markdown file. Give the image meaningful alt text and place a caption directly below it. State what a point, line, or box represents and where the reader should look. Run `check_md.py` on the finished Markdown.

## Result figures

- Show individual observations for small samples when possible. Define the observation unit and identify the type of interval shown. Supply the interval from the analysis and keep its assumptions explicit.
- Put units on quantitative axes. Keep zero visible for ordinary bar charts. Use points and intervals if the differences need a finer scale.
- Use shape or line style alongside color when readers need to distinguish series. Give a reference line a name and distinguish it from the data.
- If showing change across two paired conditions, carry the pairing through the analysis. The scripts can draw the result but cannot infer the appropriate analysis.

## Bundled tools

Use Python 3.10 or later. The Markdown checker uses Git to locate the repository. PNG preview is optional.

| Path | Purpose |
|---|---|
| `scripts/svglib.py` | Draw figures with explicitly placed components using Python's standard library. |
| `scripts/check_svg.py` | Check saved SVG files for layout, legibility, and document issues. |
| `scripts/check_md.py` | Check Markdown images for missing files, relative paths, and nearby captions. |
| `scripts/svg2png.sh` | Render an optional PNG preview when a supported renderer is available. |

When reviewing an existing figure, explain what is compared, what each mark represents, how to read the axes or encodings, what the reader should look at, and what conclusion the available data supports.
