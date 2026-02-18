#!/usr/bin/env python3

import time
import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError

ZONE = "us-west1-b"
INSTANCE_NAME = "blog"
FIREWALL_RULE_NAME = "allow-5000"
NETWORK = "global/networks/default"

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


def firewall_rule_exists(name: str) -> bool:
    try:
        compute.firewalls().get(project=project, firewall=name).execute()
        return True
    except HttpError as e:
        if e.resp.status == 404:
            return False
        raise


def ensure_firewall_rule():
    if firewall_rule_exists(FIREWALL_RULE_NAME):
        print(f"Firewall rule '{FIREWALL_RULE_NAME}' already exists.")
        return

    print(f"Creating firewall rule '{FIREWALL_RULE_NAME}' for tcp:5000 ...")
    body = {
        "name": FIREWALL_RULE_NAME,
        "network": NETWORK,
        "direction": "INGRESS",
        "sourceRanges": ["0.0.0.0/0"],
        "allowed": [{"IPProtocol": "tcp", "ports": ["5000"]}],
        "targetTags": [FIREWALL_RULE_NAME],
    }
    op = compute.firewalls().insert(project=project, body=body).execute()
    wait_for_global_op(op["name"])
    print("Firewall rule created.")


def instance_exists(name: str) -> bool:
    try:
        compute.instances().get(project=project, zone=ZONE, instance=name).execute()
        return True
    except HttpError as e:
        if e.resp.status == 404:
            return False
        raise


def create_instance():
    if instance_exists(INSTANCE_NAME):
        print(f"Instance '{INSTANCE_NAME}' already exists.")
        return

    with open("startup-script.sh", "r", encoding="utf-8") as f:
        startup_script = f.read()

    print(f"Creating instance '{INSTANCE_NAME}' in zone {ZONE}...")

    machine_type = f"zones/{ZONE}/machineTypes/e2-medium"
    source_image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"

    config = {
        "name": INSTANCE_NAME,
        "machineType": machine_type,
        "tags": {"items": [FIREWALL_RULE_NAME]},
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {"sourceImage": source_image},
            }
        ],
        "networkInterfaces": [
            {
                "network": NETWORK,
                "accessConfigs": [{"name": "External NAT", "type": "ONE_TO_ONE_NAT"}],
            }
        ],
        "metadata": {"items": [{"key": "startup-script", "value": startup_script}]},
    }

    op = compute.instances().insert(project=project, zone=ZONE, body=config).execute()
    wait_for_zone_op(op["name"])
    print("Instance created.")


def get_external_ip() -> str | None:
    inst = compute.instances().get(project=project, zone=ZONE, instance=INSTANCE_NAME).execute()
    nics = inst.get("networkInterfaces", [])
    if not nics:
        return None
    access = nics[0].get("accessConfigs", [])
    if not access:
        return None
    return access[0].get("natIP")


def main():
    print(f"Using project: {project}")
    ensure_firewall_rule()
    create_instance()

    print("Waiting for external IP...")
    ip = None
    for _ in range(60):  # ~2 minutes
        ip = get_external_ip()
        if ip:
            break
        time.sleep(2)

    if not ip:
        raise RuntimeError("No external IP found (timed out).")

    print("\n✅ Visit your app (it may take 1–3 minutes to start):")
    print(f"http://{ip}:5000\n")
    print("If it doesn’t load yet, wait and refresh.")
    print("Debug log on VM: /var/log/startup-script.log")


if __name__ == "__main__":
    main()
