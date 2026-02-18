#!/usr/bin/env python3
import time
from pathlib import Path

import google.auth
import googleapiclient.discovery

ZONE = "us-west1-b"
NETWORK = "global/networks/default"
FIREWALL_TAG = "allow-5000"
VM2_NAME = "blog-vm2"

def wait_for_zone_op(compute, project, zone, op_name):
    while True:
        op = compute.zoneOperations().get(
            project=project, zone=zone, operation=op_name
        ).execute()
        if op.get("status") == "DONE":
            if "error" in op:
                raise RuntimeError(op["error"])
            return
        time.sleep(2)

def main():
    project_id = Path("/srv/project.txt").read_text().strip()
    vm2_startup = Path("/srv/vm2-startup-script.sh").read_text()

    credentials, _ = google.auth.default()
    compute = googleapiclient.discovery.build(
        "compute", "v1", credentials=credentials
    )

    machine_type = f"zones/{ZONE}/machineTypes/e2-medium"
    source_image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"

    config = {
        "name": VM2_NAME,
        "machineType": machine_type,
        "tags": {"items": [FIREWALL_TAG]},
        "disks": [{
            "boot": True,
            "autoDelete": True,
            "initializeParams": {"sourceImage": source_image},
        }],
        "networkInterfaces": [{
            "network": NETWORK,
            "accessConfigs": [{
                "name": "External NAT",
                "type": "ONE_TO_ONE_NAT"
            }],
        }],
        "metadata": {
            "items": [{"key": "startup-script", "value": vm2_startup}]
        },
    }

    print(f"Creating VM-2 '{VM2_NAME}'...")
    op = compute.instances().insert(
        project=project_id, zone=ZONE, body=config
    ).execute()
    wait_for_zone_op(compute, project_id, ZONE, op["name"])

    inst = compute.instances().get(
        project=project_id, zone=ZONE, instance=VM2_NAME
    ).execute()
    ip = inst["networkInterfaces"][0]["accessConfigs"][0]["natIP"]

    print(f"✅ VM-2 running at http://{ip}:5000")

if __name__ == "__main__":
    main()
