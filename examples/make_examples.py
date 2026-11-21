"""Generate the two README figures using synthetic data."""

from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skills" / "zukai" / "scripts"))

from svglib import Fig


def workflow():
    # Show where SVG checks fit between generation and publishing the figure.
    fig = Fig(760, 162, title="A figure workflow", display_px=720)
    steps = [
        ("data", "Plan the figure"),
        ("enc", "Draw the SVG"),
        ("hi", "Check at final size"),
        ("head", "Add a caption"),
    ]
    for i, (kind, label) in enumerate(steps):
        x = 24 + i * 182
        fig.box(x, 62, 168, 57, kind, label, size=15)
        if i:
            fig.arrow(x - 12, 90.5, x - 3, 90.5)
    fig.save(HERE / "workflow.svg", desc="Four steps from planning a figure to embedding it with a caption.")


def comparison():
    # Synthetic timing measurements in milliseconds, six runs for each method.
    groups = [[128, 138, 135, 123, 144, 132], [91, 86, 102, 96, 99, 83]]
    means = [statistics.mean(group) for group in groups]
    spreads = [statistics.stdev(group) for group in groups]
    intervals = [(mean - sd, mean + sd) for mean, sd in zip(means, spreads)]

    fig = Fig(760, 330, title="Comparing latency across six runs", display_px=720)
    fig.dot_strip(
        108, 88, 580, 182,
        ["Baseline", "Candidate"], groups, ci=intervals, means=means,
        unit="run", err_kind="sd", highlight=1,
        ylim=(75, 155), yticks=(80, 100, 120, 140), ylabel="Latency (ms)",
        value_fmt=lambda value: f"{value:.1f}".removesuffix(".0"),
        note="Synthetic data · 6 runs per method · Open circle and whiskers show mean ± SD",
    )
    fig.save(HERE / "comparison.svg", desc="Synthetic latency observations, means, and standard deviations for two methods.")


if __name__ == "__main__":
    workflow()
    comparison()
