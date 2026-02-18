#!/bin/bash
set -e
exec > /var/log/vm1-startup.log 2>&1

apt-get update
apt-get install -y python3 python3-pip curl

mkdir -p /srv
cd /srv

fetch_attr () {
  local key="$1"
  curl -fsSL "http://metadata.google.internal/computeMetadata/v1/instance/attributes/${key}" \
    -H "Metadata-Flavor: Google"
}

fetch_attr "vm2-startup-script" > /srv/vm2-startup-script.sh
fetch_attr "vm1-launch-vm2-code" > /srv/vm1-launch-vm2.py
fetch_attr "project" > /srv/project.txt

chmod +x /srv/vm1-launch-vm2.py /srv/vm2-startup-script.sh

pip3 install --upgrade google-api-python-client google-auth google-auth-httplib2 >/dev/null 2>&1

python3 /srv/vm1-launch-vm2.py
