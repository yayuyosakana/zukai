"""Generate the README gallery using synthetic data."""

from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skills" / "zukai" / "scripts"))

from svglib import Fig


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


if __name__ == "__main__":
    workflow()
    comparison()
    learning_curve()
    score_matrix()
    agreement()
    effect_intervals()
