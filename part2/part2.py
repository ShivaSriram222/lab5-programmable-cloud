#!/usr/bin/env python3

import time
from pathlib import Path

import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError

ZONE = "us-west1-b"
SOURCE_INSTANCE = "blog"
SNAPSHOT_NAME = f"base-snapshot-{SOURCE_INSTANCE}"
CLONE_NAMES = [f"{SOURCE_INSTANCE}-clone-{i}" for i in range(3)]
NETWORK = "global/networks/default"
FIREWALL_TAG = "allow-5000"

credentials, project = google.auth.default()
compute = googleapiclient.discovery.build("compute", "v1", credentials=credentials)


def wait_for_zone_op(op_name: str):
    while True:
        op = compute.zoneOperations().get(project=project, zone=ZONE, operation=op_name).execute()
        if op.get("status") == "DONE":
            if "error" in op:
                raise RuntimeError(op["error"])
            return
        time.sleep(2)


def wait_for_global_op(op_name: str):
    while True:
        op = compute.globalOperations().get(project=project, operation=op_name).execute()
        if op.get("status") == "DONE":
            if "error" in op:
                raise RuntimeError(op["error"])
            return
        time.sleep(2)


def snapshot_exists(name: str) -> bool:
    try:
        compute.snapshots().get(project=project, snapshot=name).execute()
        return True
    except HttpError as e:
        if e.resp.status == 404:
            return False
        raise


def instance_exists(name: str) -> bool:
    try:
        compute.instances().get(project=project, zone=ZONE, instance=name).execute()
        return True
    except HttpError as e:
        if e.resp.status == 404:
            return False
        raise


def get_boot_disk_name(instance_name: str) -> str:
    inst = compute.instances().get(project=project, zone=ZONE, instance=instance_name).execute()
    for d in inst.get("disks", []):
        if d.get("boot"):
            # source looks like: .../disks/<diskname>
            return d["source"].split("/")[-1]
    raise RuntimeError(f"No boot disk found on instance '{instance_name}'")


def create_snapshot_from_instance():
    if snapshot_exists(SNAPSHOT_NAME):
        print(f"Snapshot '{SNAPSHOT_NAME}' already exists.")
        return

    disk_name = get_boot_disk_name(SOURCE_INSTANCE)
    print(f"Creating snapshot '{SNAPSHOT_NAME}' from boot disk '{disk_name}'...")

    body = {"name": SNAPSHOT_NAME}
    op = compute.disks().createSnapshot(
        project=project, zone=ZONE, disk=disk_name, body=body
    ).execute()

    wait_for_zone_op(op["name"])
    print("Snapshot created.")


def create_instance_from_snapshot(instance_name: str) -> float:
    if instance_exists(instance_name):
        print(f"Instance '{instance_name}' already exists (skipping create).")
        return 0.0

    source_snapshot = f"global/snapshots/{SNAPSHOT_NAME}"
    machine_type = f"zones/{ZONE}/machineTypes/e2-medium"

    config = {
        "name": instance_name,
        "machineType": machine_type,
        "tags": {"items": [FIREWALL_TAG]},
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {"sourceSnapshot": source_snapshot},
            }
        ],
        "networkInterfaces": [
            {
                "network": NETWORK,
                "accessConfigs": [{"name": "External NAT", "type": "ONE_TO_ONE_NAT"}],
            }
        ],
    }

    print(f"Creating instance '{instance_name}' from snapshot '{SNAPSHOT_NAME}'...")
    start = time.perf_counter()
    op = compute.instances().insert(project=project, zone=ZONE, body=config).execute()
    wait_for_zone_op(op["name"])
    end = time.perf_counter()
    elapsed = end - start
    print(f"Created '{instance_name}' in {elapsed:.2f} seconds.")
    return elapsed


def write_timing(times: dict):
    lines = [
        "# TIMING",
        "",
        f"Project: `{project}`",
        f"Zone: `{ZONE}`",
        f"Source instance: `{SOURCE_INSTANCE}`",
        f"Snapshot: `{SNAPSHOT_NAME}`",
        "",
        "| Instance | Creation time (seconds) |",
        "|---|---:|",
    ]
    for name, t in times.items():
        lines.append(f"| `{name}` | {t:.2f} |")
    lines.append("")

    Path("TIMING.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote TIMING.md")


def main():
    print(f"Using project: {project}")
    create_snapshot_from_instance()

    times = {}
    for name in CLONE_NAMES:
        times[name] = create_instance_from_snapshot(name)

    write_timing(times)

    print("\n✅ Done. Next: commit TIMING.md to your repo.")
    print("Tip: each clone should be reachable at http://<its-external-ip>:5000")


if __name__ == "__main__":
    main()
