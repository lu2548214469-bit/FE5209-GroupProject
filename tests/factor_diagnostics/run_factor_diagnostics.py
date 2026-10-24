#!/usr/bin/env python3
"""Generate factor diagnostics from the final main-backtest outputs.

Prerequisite:
    python run_backtest.py --skip-execution

Run:
    python tests/factor_diagnostics/run_factor_diagnostics.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = Path(__file__).resolve().parent / "src"
SCRIPTS = (
    SOURCE_DIR / "plot_factor_predictability.py",
    SOURCE_DIR / "plot_factor_volatility_boxplot.py",
)
REQUIRED_INPUTS = (
    REPOSITORY_ROOT
    / "outputs/SG_Adaptive_K3_IVweekly_Top20/01_factor_returns_weekly.csv",
    REPOSITORY_ROOT
    / "outputs/SG_Adaptive_K3_IVweekly_Top20/02_annual_style_decisions.csv",
)


def validate_inputs() -> None:
    """Check all required final-backtest artifacts before spawning plot scripts."""
    missing = [path for path in REQUIRED_INPUTS if not path.is_file()]
    if missing:
        missing_paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(
            "Factor diagnostics require these main-backtest outputs:\n"
            f"{missing_paths}\n"
            "Run `python run_backtest.py --skip-execution` first."
        )


def main() -> None:
    """Run each factor diagnostic in a deterministic order."""
    validate_inputs()
    for script in SCRIPTS:
        print(f"\n{'=' * 80}\nRunning {script.name}\n{'=' * 80}", flush=True)
        subprocess.run([sys.executable, str(script)], check=True, cwd=REPOSITORY_ROOT)
    print("\nFactor diagnostics complete.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from None
