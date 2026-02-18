#!/bin/bash
set -e

# Log startup output for debugging
exec > /var/log/startup-script.log 2>&1

mkdir -p /opt/flaskapp
cd /opt/flaskapp

apt-get update
apt-get install -y python3 python3-pip git

# Clone the flask tutorial app
if [ ! -d flask-tutorial ]; then
  git clone https://github.com/cu-csci-4253-datacenter/flask-tutorial
fi

cd flask-tutorial
python3 setup.py install
pip3 install -e .

export FLASK_APP=flaskr
flask init-db

nohup flask run -h 0.0.0.0 -p 5000 &
