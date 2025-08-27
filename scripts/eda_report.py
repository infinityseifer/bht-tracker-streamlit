#!/usr/bin/env python3
import argparse, json, sys
import pandas as pd
import numpy as np

def safe_pct(part, whole):
    try:
        return round(100.0 * float(part)/float(max(whole,1)), 2)
    except Exception:
        return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='in_path', required=True, help='Input CSV path')
    ap.add_argument('--sep', default=',', help='CSV delimiter')
    ap.add_argument('--encoding', default='utf-8', help='CSV encoding')
    ap.add_argument('--nrows', type=int, default=None, help='Optional row cap')
    args = ap.parse_args()

    df = pd.read_csv(args.in_path, sep=args.sep, encoding=args.encoding, nrows=args.nrows)

    # Basic shape and memory
    out = {
        "shape": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
        "memory": f"{round(df.memory_usage(deep=True).sum()/1_048_576, 2)} MB"
    }

    # Column meta
    cols = []
    for c in df.columns:
        s = df[c]
        dtype = str(s.dtype)
        nunique = int(s.nunique(dropna=True))
        missing = int(s.isna().sum())
        cols.append({
            "column": c,
            "dtype": dtype,
            "unique": nunique,
            "missing": missing,
            "missing_pct": safe_pct(missing, len(s))
        })
    out["columns"] = cols

    # Missing overview (sorted desc)
    miss = s = df.isna().sum().sort_values(ascending=False)
    miss_rows = []
    for c, m in miss.items():
        miss_rows.append({
            "column": str(c),
            "missing": int(m),
            "missing_pct": safe_pct(m, len(df))
        })
    out["missing"] = miss_rows

    # Numeric summary
    numeric_df = df.select_dtypes(include=[np.number])
    if not numeric_df.empty:
        desc = numeric_df.describe().T.reset_index().rename(columns={"index":"column"})
        desc = desc[['column','count','mean','std','min','25%','50%','75%','max']]
        out["numeric"] = desc.fillna("").to_dict(orient="records")
    else:
        out["numeric"] = []

    # Categorical tops
    cat_df = df.select_dtypes(exclude=[np.number])
    cat_rows = []
    top_k = 5
    for c in cat_df.columns:
        vc = cat_df[c].value_counts(dropna=True).head(top_k)
        total = max(int(cat_df[c].notna().sum()), 1)
        for cat, cnt in vc.items():
            cat_rows.append({
                "column": c,
                "category": str(cat),
                "count": int(cnt),
                "pct": safe_pct(cnt, total)
            })
    out["categorical"] = cat_rows

    # Correlation
    if not numeric_df.empty and numeric_df.shape[1] >= 2:
        corr = numeric_df.corr(numeric_only=True).reset_index().rename(columns={"index":"column"})
        out["correlation"] = corr.to_dict(orient="records")
    else:
        out["correlation"] = []

    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
