import pandas as pd, numpy as np
print("pandas", pd.__version__)
df = pd.DataFrame({"a": np.arange(5.0), "f": 0.0})
try:
    df.at[2:, "f"] = df["a"].iloc[2:] * 10
    print("at-slice OK:", df["f"].tolist())
except Exception as e:
    print("at-slice error:", type(e).__name__, e)
# chained assignment as in Pair trading backtest.py line 139/152
df2 = pd.DataFrame({"z": np.nan, "x": np.arange(5.0)})
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    df2["z"].iloc[2:] = 1.0
    print("chained z after:", df2["z"].tolist(), "warnings:", [str(x.category.__name__) for x in w])
