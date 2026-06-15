import pandas as pd
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python merge_sync_data.py sync_recording_FOLDER")
    sys.exit(1)

folder = Path(sys.argv[1])

ev_path = folder / "prophesee_event_batches.csv"
hr_path = folder / "polar_h10_hr.csv"

ev = pd.read_csv(ev_path)
hr = pd.read_csv(hr_path)

if len(hr) == 0:
    raise RuntimeError("Heart-rate CSV is empty.")

# Sort by laptop time
ev = ev.sort_values("laptop_time_s")
hr = hr.sort_values("laptop_time_s")

# For each event batch, attach nearest HR sample
merged = pd.merge_asof(
    ev,
    hr[["laptop_time_s", "heart_rate_bpm", "rr_intervals_ms"]],
    on="laptop_time_s",
    direction="nearest",
    tolerance=2.0
)

out_path = folder / "synchronized_event_hr.csv"
merged.to_csv(out_path, index=False)

print(f"Saved synchronized file to: {out_path}")
print(merged.head())
