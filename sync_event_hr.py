import asyncio
import csv
import os
import signal
import struct
import threading
import time
from datetime import datetime

from bleak import BleakClient, BleakScanner


# -----------------------------
# Polar H10 BLE constants
# -----------------------------
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


# -----------------------------
# Global stop flag
# -----------------------------
stop_event = threading.Event()


def now_ns() -> int:
    """
    One shared laptop clock for synchronization.
    Monotonic time does not jump if system time changes.
    """
    return time.monotonic_ns()


def parse_heart_rate_measurement(data: bytearray):
    """
    Parse standard Bluetooth Heart Rate Measurement packet.

    Returns:
        hr_bpm: int
        rr_intervals_ms: list[float]
    """
    flags = data[0]

    hr_16_bit = flags & 0x01
    rr_present = flags & 0x10

    index = 1

    if hr_16_bit:
        hr_bpm = struct.unpack_from("<H", data, index)[0]
        index += 2
    else:
        hr_bpm = data[index]
        index += 1

    # Energy expended present
    if flags & 0x08:
        index += 2

    rr_intervals_ms = []

    if rr_present:
        while index + 1 < len(data):
            rr_raw = struct.unpack_from("<H", data, index)[0]
            index += 2

            # RR interval is in units of 1/1024 second
            rr_ms = rr_raw / 1024.0 * 1000.0
            rr_intervals_ms.append(rr_ms)

    return hr_bpm, rr_intervals_ms


async def find_polar_h10():
    print("Searching for Polar H10...")

    devices = await BleakScanner.discover(timeout=8.0)

    for d in devices:
        name = d.name or ""
        if "Polar" in name or "H10" in name:
            print(f"Found device: {name} [{d.address}]")
            return d

    raise RuntimeError("Polar H10 not found. Make sure it is worn and not already connected to your phone.")


async def polar_logger(output_dir: str):
    """
    Connects to Polar H10 and logs heart rate packets.
    """
    csv_path = os.path.join(output_dir, "polar_h10_hr.csv")

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "laptop_time_ns",
            "laptop_time_s",
            "heart_rate_bpm",
            "rr_intervals_ms"
        ])

        # device = await find_polar_h10()

        POLAR_ADDRESS = "DF:8D:76:00:66:90"
        
        async with BleakClient(POLAR_ADDRESS) as client:
            print("Connected to Polar H10.")

            def notification_handler(sender, data):
                t_ns = now_ns()
                t_s = t_ns / 1e9

                hr_bpm, rr_intervals_ms = parse_heart_rate_measurement(data)

                writer.writerow([
                    t_ns,
                    t_s,
                    hr_bpm,
                    ";".join(f"{x:.3f}" for x in rr_intervals_ms)
                ])
                f.flush()

                print(f"[HR] {hr_bpm} bpm, RR={rr_intervals_ms}")

            await client.start_notify(HR_MEASUREMENT_UUID, notification_handler)

            while not stop_event.is_set():
                await asyncio.sleep(0.1)

            await client.stop_notify(HR_MEASUREMENT_UUID)

    print(f"Polar HR log saved to: {csv_path}")


def prophesee_event_logger(output_dir: str):
    """
    Reads Prophesee event camera stream and logs event batch timing.

    This records:
    - laptop receive timestamp
    - event camera first timestamp in batch
    - event camera last timestamp in batch
    - number of events
    - simple spatial statistics

    This does NOT save every single event, because that can create huge files.
    """
    csv_path = os.path.join(output_dir, "prophesee_event_batches.csv")

    try:
        from metavision_core.event_io import EventsIterator
    except ImportError:
        print("Could not import Metavision SDK Python module.")
        print("Check that Metavision SDK is installed and sourced.")
        return

    print("Starting Prophesee event camera...")

    # delta_t is event batch duration in microseconds.
    # 10000 us = 10 ms batches.
    mv_iterator = EventsIterator(
        input_path="",
        mode="delta_t",
        delta_t=10000
    )

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "laptop_time_ns",
            "laptop_time_s",
            "camera_batch_start_us",
            "camera_batch_end_us",
            "event_count",
            "mean_x",
            "mean_y",
            "positive_event_count",
            "negative_event_count"
        ])

        for events in mv_iterator:
            if stop_event.is_set():
                break

            t_laptop_ns = now_ns()
            t_laptop_s = t_laptop_ns / 1e9

            if len(events) == 0:
                continue

            # Prophesee event fields are usually:
            # events["x"], events["y"], events["p"], events["t"]
            cam_start_us = int(events["t"][0])
            cam_end_us = int(events["t"][-1])
            event_count = len(events)

            mean_x = float(events["x"].mean())
            mean_y = float(events["y"].mean())

            positive_count = int((events["p"] > 0).sum())
            negative_count = int((events["p"] <= 0).sum())

            writer.writerow([
                t_laptop_ns,
                t_laptop_s,
                cam_start_us,
                cam_end_us,
                event_count,
                mean_x,
                mean_y,
                positive_count,
                negative_count
            ])
            f.flush()

            print(
                f"[EV] count={event_count}, "
                f"cam_t={cam_start_us}->{cam_end_us} us, "
                f"laptop_t={t_laptop_s:.3f}"
            )

    print(f"Event camera log saved to: {csv_path}")


async def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"sync_recording_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    print(f"Saving logs to: {output_dir}")

    def handle_stop(sig, frame):
        print("\nStopping...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    event_thread = threading.Thread(
        target=prophesee_event_logger,
        args=(output_dir,),
        daemon=True
    )
    event_thread.start()

    try:
        await polar_logger(output_dir)
    finally:
        stop_event.set()
        event_thread.join(timeout=3.0)

    print("Finished synchronization logging.")


if __name__ == "__main__":
    asyncio.run(main())