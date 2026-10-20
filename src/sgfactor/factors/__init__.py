"""Factor layer.

Style scores (Quality, Momentum, Low Risk, Investment, Size, Value) are supplied ready-made
by the data team in data/sg_universe_weekly.csv.gz (cross-sectionally standardised, higher =
more favoured). This layer reads them and turns them into weekly long-short factor returns,
which the strategy layer uses to choose and weight styles.

Sub-factor construction (which raw signals make up each style and how they are combined)
belongs to the data / factor-test side and will be documented in docs/factor_definitions.md.
"""
from .scores import style_scores
from .factor_returns import factor_returns

__all__ = ["style_scores", "factor_returns"]
