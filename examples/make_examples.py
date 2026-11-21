"""Generate the README gallery using synthetic data."""

from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skills" / "zukai" / "scripts"))

from svglib import Fig


def readme_self_portrait():
    """Draw the README explaining its own opening illustration."""
    fig = Fig(900, 278, display_px=780)
    ink, blue, pale, paper = "#24354A", "#00699C", "#E5F2F8", "#FFF5D8"

    def paper_character(x, y, scale):
        # A folded sheet holding a pencil. Repeat it inside the finished README.
        fig.raw(f'<g transform="translate({x} {y}) scale({scale})" '
                f'stroke="{ink}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                f'<path d="M12 5 H58 L79 26 V83 H12 Z" fill="{paper}"/>'
                '<path d="M58 5 V26 H79" fill="none"/>'
                f'<path d="M28 39 v3 M47 39 v3 M31 52 q8 8 16 -1" fill="none"/>'
                '<path d="M12 55 L3 61 M79 54 l9 -8 M28 84 l-4 9 h-8 M60 84 l4 9 h8" fill="none"/>'
                '<path d="M79 49 l15 -25 5 3 -15 25 -7 5 Z" fill="#E8AE44"/>'
                '</g>')

    fig.rect(1, 1, 898, 276, fill="#FAFBFC", stroke="#CDD6DE", rx=14)
    fig.text(27, 37, "A README asks for a self-portrait", size=24, anchor="start", bold=True, color=ink)

    # The prompt is part of the picture so the reader can see what the agent receives.
    fig.rect(27, 63, 216, 63, fill="#FFFFFF", stroke=ink, rx=13)
    fig.raw(f'<path d="M82 125 l-9 14 25 -14" fill="white" stroke="{ink}"/>')
    fig.text(135, 90, "“Draw how you made", size=17, color=ink, bold=True)
    fig.text(135, 113, "this figure.”", size=17, color=ink, bold=True)
    paper_character(65, 145, 1.02)

    fig.arrow(207, 184, 255, 184, color=blue, width=2)
    fig.text(282, 91, "At the drawing board", size=17, anchor="start", color=ink, bold=True)
    fig.box(282, 114, 92, 46, "data", "Plan layout", size=14)
    fig.arrow(378, 137, 406, 137, color=blue)
    fig.box(411, 114, 99, 46, "enc", "Draw SVG", size=14)
    fig.line(283, 173, 509, 173, color=blue, width=1)
    for x in (283, 509):
        fig.line(x, 168, x, 178, color=blue)
    fig.text(396, 197, "Check at display width", size=14, bold=True, color=blue)
    fig.text(396, 219, "Text size · overlap · contrast", size=14, color=ink)

    fig.arrow(527, 184, 573, 184, color=blue, width=2)
    fig.rect(593, 63, 274, 187, fill="#FFFFFF", stroke="#91A4B4", rx=8)
    fig.text(610, 89, "README.md", size=17, anchor="start", bold=True, color=ink)
    fig.line(594, 101, 866, 101, color="#CDD6DE")
    # Echo the three subjects without unreadable miniature labels.
    fig.rect(610, 116, 240, 84, fill="#FAFBFC", rx=6)
    paper_character(620, 128, 0.56)
    fig.arrow(684, 160, 703, 160, color=blue)
    fig.rect(711, 148, 18, 24, fill=pale, stroke=blue, rx=3)
    fig.rect(734, 148, 18, 24, fill=pale, stroke=blue, rx=3)
    fig.arrow(760, 160, 779, 160, color=blue)
    fig.rect(787, 131, 48, 54, fill="#FFFFFF", stroke=ink, rx=3)
    fig.line(790, 140, 831, 140, color="#91A4B4")
    paper_character(795, 145, 0.34)
    fig.text(730, 226, "This figure, with its caption.", size=14, color=ink)
    fig.save(HERE / "readme-self-portrait.svg", title="A README asks for a self-portrait",
             desc="A paper character asks for a drawing. Zukai draws the SVG, checks it at display width, and embeds it in a README showing the same character.")


def gallery_figure(title):
    return Fig(450, 272, title=title, display_px=360)


def workflow():
    # Show where SVG checks fit between generation and publishing the figure.
    fig = gallery_figure("From question to figure")
    steps = [
        (34, 61, "data", "Plan\nChoose a question"),
        (256, 61, "enc", "Draw\nBuild the SVG"),
        (256, 169, "hi", "Check\nRead at final size"),
        (34, 169, "head", "Embed\nWrite a caption"),
    ]
    for x, y, kind, label in steps:
        fig.box(x, y, 160, 67, kind, label, size=15)
    fig.arrow(200, 94.5, 250, 94.5)
    fig.arrow(336, 134, 336, 163)
    fig.arrow(250, 202.5, 200, 202.5)
    fig.save(HERE / "workflow.svg", desc="Four steps from planning a figure to embedding it with a caption.")


def comparison():
    # Synthetic timing measurements in milliseconds, six runs for each method.
    groups = [[128, 138, 135, 123, 144, 132], [91, 86, 102, 96, 99, 83]]
    means = [statistics.mean(group) for group in groups]
    spreads = [statistics.stdev(group) for group in groups]
    intervals = [(mean - sd, mean + sd) for mean, sd in zip(means, spreads)]

    fig = gallery_figure("Compare repeated runs")
    fig.dot_strip(
        76, 79, 314, 148,
        ["Baseline", "Candidate"], groups, ci=intervals, means=means,
        unit="run", err_kind="sd", highlight=1,
        ylim=(75, 155), yticks=(80, 100, 120, 140), ylabel="Latency (ms)",
        value_fmt=lambda value: f"{value:.1f}".removesuffix(".0"),
        note="Six runs per method · Mean ± SD",
    )
    fig.save(HERE / "comparison.svg", desc="Synthetic latency observations, means, and standard deviations for two methods.")


def learning_curve():
    # Synthetic validation losses for eight training epochs.
    epochs = list(range(1, 9))
    candidate = [0.94, 0.79, 0.66, 0.56, 0.49, 0.43, 0.40, 0.38]
    baseline = [0.99, 0.90, 0.79, 0.73, 0.66, 0.64, 0.61, 0.58]
    fig = gallery_figure("Track validation loss")
    fig.line_chart(
        68, 60, 274, 154,
        [
            {"name": "Candidate", "xs": epochs, "ys": candidate},
            {"name": "Baseline", "xs": epochs, "ys": baseline},
        ],
        ylim=(0.3, 1.05), xticks=(1, 2, 4, 6, 8), yticks=(0.4, 0.6, 0.8, 1.0),
        xlabel="Epoch", ylabel="Validation loss",
    )
    fig.save(HERE / "learning-curve.svg", desc="Two synthetic validation loss curves across eight epochs.")


def score_matrix():
    # Synthetic accuracy percentages on three datasets.
    fig = gallery_figure("Compare scores across datasets")
    fig.heatmap(
        35, 83, 380, 137,
        ["Baseline", "Candidate", "Ensemble"], ["Set A", "Set B", "Set C"],
        [[72, 64, 76], [78, 75, 81], [82, 79, 83]],
        vmin=60, vmax=90, cbar_label="Accuracy (%)",
    )
    fig.save(HERE / "heatmap.svg", desc="Synthetic accuracy scores for three methods and three datasets.")


def agreement():
    # Synthetic observations paired with model predictions in milliseconds.
    observed = [42, 48, 53, 60, 64, 71, 76, 81, 86, 92, 96, 105]
    predicted = [46, 51, 47, 58, 68, 63, 73, 87, 83, 96, 91, 109]
    fig = gallery_figure("Check prediction agreement")
    fig.scatter(
        128, 60, 158, 158,
        [{"name": "Prediction", "xs": observed, "ys": predicted}],
        xlim=(35, 115), ylim=(35, 115),
        xticks=(40, 60, 80, 100), yticks=(40, 60, 80, 100),
        xlabel="Observed (ms)", ylabel="Predicted (ms)", diag=True,
        diag_label="Perfect agreement", note="12 synthetic observations",
    )
    fig.save(HERE / "scatter.svg", desc="Predicted and observed latency are compared against a diagonal reference line.")


def effect_intervals():
    # Illustrative estimates and interval endpoints in percentage points.
    fig = gallery_figure("Compare effects by group")
    fig.forest(
        28, 77, 398, 131, ["Group A", "Group B", "Group C"],
        [4, 1, -2], [1, -2, -5], [7, 4, 1],
        xlim=(-6, 8), xticks=(-5, 0, 5), xlabel="Difference (percentage points)",
        col_title="Estimate (95% CI)", value_fmt=lambda value: f"{value:g}",
    )
    fig.save(HERE / "forest.svg", desc="Three illustrative effect estimates and 95% confidence intervals compared against zero.")


def request_routing():
    # Synthetic request counts and mean stage durations among successful requests.
    cache_hits, upstream_served, timeouts = 720, 240, 40
    cache_misses = upstream_served + timeouts
    gray, blue, orange = "#777777", "#0072B2", "#D55E00"
    fig = Fig(920, 328, title="Cache misses account for all 40 timeouts", title_size=25, display_px=780)
    fig.panel_label(26, 75, "A", "Where requests go", size=17, title_size=17)
    fig.panel_label(520, 75, "B", "What takes time", size=17, title_size=17)
    fig.line(500, 63, 500, 274)

    fig.sankey(
        95, 104, 292, 153,
        [
            ("Incoming", "Cache hit", cache_hits, gray),
            ("Incoming", "Cache miss", cache_misses, blue),
            ("Cache hit", "Served", cache_hits, gray),
            ("Cache miss", "Served", upstream_served, blue),
            ("Cache miss", "Timed out", timeouts, orange),
        ],
        columns=[["Incoming"], ["Cache hit", "Cache miss"], ["Served", "Timed out"]],
        colors={"Incoming": gray, "Cache hit": gray, "Cache miss": blue, "Served": gray, "Timed out": orange},
        value_fmt=lambda count: f"{count:,}",
        gap=20,
    )

    fig.stacked_bar(
        520, 104, 372, 132,
        ["Cache hit", "Cache miss"], [[12, 8], [12, 68]],
        ["Cache lookup", "Response"],
        colors=["#BBBBBB", blue], n=[cache_hits, upstream_served],
        value_label="Mean time among successful requests (ms)",
    )
    fig.caption(f"Synthetic traffic · {cache_hits + cache_misses:,} incoming requests", y=305, size=12)
    fig.save(
        HERE / "request-routing.svg",
        desc="A Sankey diagram traces simulated requests. Stacked bars compare mean latency by stage for successful requests.",
    )


if __name__ == "__main__":
    readme_self_portrait()
    workflow()
    comparison()
    learning_curve()
    score_matrix()
    agreement()
    effect_intervals()
    request_routing()
