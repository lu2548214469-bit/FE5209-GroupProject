"""Run every test of the project in research order and print one summary.

    python tests/run_all_tests.py                 # about 4 minutes
    python tests/run_all_tests.py --skip factor   # leave out a stage (factor | strategy | execution)

Stages
  1  factor     tests/factor_tests/run_factor_tests.py      single-factor tests, 2011-2015
  2  strategy   tests/strategy_tests/run_strategy_tests.py  configuration selection, 2016-2020
  3  execution  tests/execution_tests/run_execution_tests.py  execution engine (synthetic) + reproduction
Each stage keeps its own outputs under outputs/; a stage that fails does not stop the others.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGES = [
    ("factor", "Single-factor tests (2011-2015)", HERE / "factor_tests" / "run_factor_tests.py"),
    ("strategy", "Strategy selection (2016-2020)", HERE / "strategy_tests" / "run_strategy_tests.py"),
    ("execution", "Execution engine tests", HERE / "execution_tests" / "run_execution_tests.py"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip", nargs="*", default=[], choices=[s[0] for s in STAGES])
    a = ap.parse_args()
    results = []
    for key, title, script in STAGES:
        if key in a.skip:
            results.append((title, "SKIPPED", 0.0))
            continue
        print("\n" + "#" * 100 + f"\n#  {title}\n" + "#" * 100, flush=True)
        t0 = time.time()
        code = subprocess.run([sys.executable, str(script)]).returncode
        results.append((title, "PASS" if code == 0 else f"FAIL (exit {code})", time.time() - t0))
    print("\n" + "=" * 60 + "\nSUMMARY\n" + "=" * 60)
    for title, status, secs in results:
        print(f"  {title:<36} {status:<14} {secs:6.0f} s")
    if any(s.startswith("FAIL") for _, s, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
