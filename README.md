# Prophesee Event Camera + Polar H10 Synchronization

This project records and synchronizes data from a **Prophesee EVK event camera** and a **Polar H10 heart-rate sensor** simultaneously. Both data streams are timestamped, so they can be synchronized later.

The main goal is to collect:

- Event-camera activity from the Prophesee camera
- Heart rate and RR intervals from the Polar H10
- A shared timestamp column for offline synchronization

---

## System Overview

```text
Prophesee EVK camera  ---> USB ---> Laptop Python script ---> prophesee_event_batches.csv
Polar H10             ---> BLE ---> Laptop Python script ---> polar_h10_hr.csv
```

Both streams use the same laptop timestamp:

```text
laptop_time_ns
laptop_time_s
```

This shared timebase is used to synchronize event-camera data and heart-rate data.

---

## Hardware Used

- Laptop running Ubuntu
- Prophesee EVK event camera
- Polar H10 heart-rate sensor
- Bluetooth adapter, usually built into laptop
- USB cable for Prophesee camera

Recommended:

- Use a direct USB 3 port for the Prophesee camera
- Do not use a USB hub
- Use a good USB 3 cable
- Disconnect Polar H10 from your phone before running the script

---

## Software Requirements

- Ubuntu Linux
- Python 3.10+
- OpenEB / Metavision SDK
- Bleak Python package
- h5py Python package
- Optional: pandas for merging synchronized data

---

## Environment Setup

Activate the Python environment:

```bash
source ~/sync_env/bin/activate
```

Source the Metavision/OpenEB environment:

```bash
source ~/openeb/build/generated/setup_env.sh
```

If needed, install Python dependencies:

```bash
pip install bleak h5py pandas
```

Every new terminal needs these two lines before running the script:

```bash
source ~/sync_env/bin/activate
source ~/openeb/build/generated/setup_env.sh
```

---

## Testing the Devices

### Test Metavision import

```bash
python -c "from metavision_core.event_io import EventsIterator; print('Metavision OK')"
```

Expected output:

```text
Metavision OK
```

### Test Prophesee camera

```bash
metavision_viewer
```

If the viewer opens and shows event activity, the camera is working.

If you see:

```text
LIBUSB_ERROR_TIMEOUT
```

try:

```bash
pkill -f metavision
pkill -f sync_event_hr.py
```

Then unplug and replug the camera. Use a direct USB 3 port if possible.

### Test Polar H10 visibility

```bash
bluetoothctl
```

Inside `bluetoothctl`:

```text
power on
scan on
```

Wait until you see something like:

```text
Polar H10 8BF4522B
```

Then:

```text
scan off
quit
```

Important: turn off Bluetooth on your phone or disconnect Polar H10 from phone apps before running the Python script.

---

## Running the Synchronization Script

Run:

```bash
source ~/sync_env/bin/activate
source ~/openeb/build/generated/setup_env.sh
python ~/sync_event_hr.py
```

Expected output looks like:

```text
Saving logs to: sync_recording_20260612_120213
Connecting to Polar H10...
Connected to Polar H10.
Starting Prophesee event camera...
[EV] count=38842, cam_t=25030001->25039999 us, laptop_t=24692.738
[HR] 94 bpm, RR=[600.5859375, 598.6328125]
[EV] count=37128, cam_t=25110000->25119999 us, laptop_t=24692.818
```

Stop recording with:

```text
Ctrl + C
```

The script should save:

```text
sync_recording_YYYYMMDD_HHMMSS/prophesee_event_batches.csv
sync_recording_YYYYMMDD_HHMMSS/polar_h10_hr.csv
```

---

## Output Files

### `prophesee_event_batches.csv`

This file contains event-camera batches.

Columns:

```text
laptop_time_ns
laptop_time_s
camera_batch_start_us
camera_batch_end_us
event_count
mean_x
mean_y
positive_event_count
negative_event_count
```

Meaning:

- `laptop_time_ns`: laptop monotonic timestamp in nanoseconds
- `laptop_time_s`: laptop monotonic timestamp in seconds
- `camera_batch_start_us`: first Prophesee camera timestamp in the batch
- `camera_batch_end_us`: last Prophesee camera timestamp in the batch
- `event_count`: number of events in the batch
- `mean_x`, `mean_y`: average event location in the batch
- `positive_event_count`: number of positive polarity events
- `negative_event_count`: number of negative polarity events

### `polar_h10_hr.csv`

This file contains heart-rate packets.

Columns:

```text
laptop_time_ns
laptop_time_s
heart_rate_bpm
rr_intervals_ms
```

Meaning:

- `laptop_time_ns`: laptop monotonic timestamp in nanoseconds
- `laptop_time_s`: laptop monotonic timestamp in seconds
- `heart_rate_bpm`: heart rate in beats per minute
- `rr_intervals_ms`: RR intervals in milliseconds, separated by semicolons

Example:

```text
24692.806,94,600.586;598.633
```

---

## Why Event Camera Prints More Than Heart Rate

The event camera logs batches every 10 ms:

```python
delta_t = 10000  # microseconds = 10 ms
```

That means around 100 event rows per second.

Polar H10 heart-rate data is much slower, often around one packet per second. Therefore, it is normal to see many `[EV]` lines and only occasional `[HR]` lines.

---

## Synchronizing the Data

Both CSV files share this timestamp column:

```text
laptop_time_s
```

To combine them, use nearest-time matching. Use `merge_sync_data.py`:

Run:

```bash
python ~/merge_sync_data.py sync_recording_YYYYMMDD_HHMMSS
```

Example:

```bash
python ~/merge_sync_data.py sync_recording_20260612_120213
```

Output:

```text
synchronized_event_hr.csv
```

To run this code, the pandas library must be installed.

---

## Recommended Recording Procedure

1. Connect Prophesee camera to laptop.
2. Make sure the camera works with `metavision_viewer`.
3. Wear Polar H10 and wet the electrodes.
4. Disconnect Polar H10 from phone.
5. Start the Python script.
6. Wait until both `[EV]` and `[HR]` messages appear.
7. Record for at least 30-60 seconds.
8. Stop with `Ctrl + C`.
9. Merge CSV files using `merge_sync_data.py`.

---

## Additional Checks

Before running the code, it is advisable to check the Prophesee event camera window.

Run:

```bash
source ~/sync_env/bin/activate
source ~/openeb/build/generated/setup_env.sh
metavision_viewer
```

---

## Common Problems and Fixes

### Problem: `ModuleNotFoundError: No module named 'bleak'`

Fix:

```bash
source ~/sync_env/bin/activate
pip install bleak
```

### Problem: `ModuleNotFoundError: No module named 'h5py'`

Fix:

```bash
source ~/sync_env/bin/activate
pip install h5py
```

### Problem: Metavision module not found

Fix:

```bash
source ~/openeb/build/generated/setup_env.sh
```

Then test:

```bash
python -c "from metavision_core.event_io import EventsIterator; print('Metavision OK')"
```

### Problem: `LIBUSB_ERROR_TIMEOUT`

This means the Prophesee camera is detected but cannot open correctly.

Try:

```bash
pkill -f metavision
pkill -f sync_event_hr.py
```

Then unplug and replug the camera.

Also try:

```bash
sudo systemctl restart bluetooth
```

Use:

- Direct USB port
- USB 3 cable
- No USB hub

### Problem: Warning: camera is not connected in USB3

Example:

```text
[HAL][WARNING] Your EVK camera isn't connected in USB3. Please check your connection.
```

The camera may still work, but USB 2 can limit bandwidth. Use a USB 3 port and USB 3 cable.

### Problem: Polar H10 not found

Try:

```bash
sudo systemctl restart bluetooth
```

Then:

```bash
bluetoothctl
```

Inside:

```text
power on
scan on
```

Also make sure:

- Polar H10 is worn
- Electrodes are wet
- Phone Bluetooth is off
- Polar H10 is not connected to another app

### Problem: Polar connects too late

Start the event camera only after Polar connects and HR notifications begin.

Better recording order:

```text
1. Connect Polar H10
2. Start HR notifications
3. Start event camera
4. Record both together
```

---

## Notes About Accuracy

The Prophesee camera has very high timestamp precision. Polar H10 heart-rate packets are much slower. Therefore, the synchronization accuracy is mostly limited by the heart-rate data stream, not by the event camera.

For better physiological timing, use RR intervals. For the best timing, use Polar H10 ECG and detect R-peaks, but this requires a more advanced BLE/Polar SDK pipeline.

---

## Quick Launcher Script

Create:

```bash
nano ~/run_sync.sh
```

Paste:

```bash
#!/bin/bash
source ~/sync_env/bin/activate
source ~/openeb/build/generated/setup_env.sh
python ~/sync_event_hr.py
```

Make it executable:

```bash
chmod +x ~/run_sync.sh
```

Run synchronization with:

```bash
~/run_sync.sh
```

---

## Additional Attachments

Additionally, the video recording of the algorithm work is given in this repository.
