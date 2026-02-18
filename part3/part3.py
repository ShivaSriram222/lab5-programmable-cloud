#!/usr/bin/env python3

import time
from pathlib import Path

import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError

ZONE = "us-west1-b"
VM1_NAME = "part3-launcher"
NETWORK = "global/networks/default"
SERVICE_ACCOUNT_EMAIL = "lab5-vm-launcher@project-ea5fb48a-0d44-403f-8ab.iam.gserviceaccount.com"

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

def instance_exists(compute, project, zone, name):
    try:
        compute.instances().get(
            project=project, zone=zone, instance=name
        ).execute()
        return True
    except HttpError as e:
        if e.resp.status == 404:
            return False
        raise

def main():
    credentials, project_id = google.auth.default()
    compute = googleapiclient.discovery.build(
        "compute", "v1", credentials=credentials
    )

    print(f"Using project: {project_id}")

    if instance_exists(compute, project_id, ZONE, VM1_NAME):
        print(f"VM-1 '{VM1_NAME}' already exists. Delete it to rerun.")
        return

    vm1_startup = Path("vm1-startup-script.sh").read_text()
    vm2_startup = Path("vm2-startup-script.sh").read_text()
    vm1_launch_code = Path("vm1-launch-vm2.py").read_text()

    machine_type = f"zones/{ZONE}/machineTypes/e2-medium"
    source_image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"

    config = {
        "name": VM1_NAME,
        "machineType": machine_type,
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
        "serviceAccounts": [{
            "email": SERVICE_ACCOUNT_EMAIL,
            "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
        }],
        "metadata": {
            "items": [
                {"key": "startup-script", "value": vm1_startup},
                {"key": "vm2-startup-script", "value": vm2_startup},
                {"key": "vm1-launch-vm2-code", "value": vm1_launch_code},
                {"key": "project", "value": project_id},
            ]
        },
    }

    print(f"Creating VM-1 '{VM1_NAME}'...")
    op = compute.instances().insert(
        project=project_id, zone=ZONE, body=config
    ).execute()
    wait_for_zone_op(compute, project_id, ZONE, op["name"])

    print("✅ VM-1 created. It will now create VM-2 automatically.")
    print("Check VM-1 log: /var/log/vm1-startup.log")

if __name__ == "__main__":
    main()
