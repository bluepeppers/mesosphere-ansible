#!/usr/bin/env python3
import json
import argparse
import logging
import time
import os.path
import subprocess

import requests
import jinja2

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARN)

BASE_URL = "https://api.digitalocean.com/v2/"
IMAGE = 'ubuntu-14-04-x64'

MASTER_NAMES = "m{}"
SLAVE_NAMES = "s{}"

INVENTORY_TEMPLATE = """
[mesos_masters]
{% for droplet in masters %}
{{ droplet.public_ipv4 }} ansible_ssh_user=root
{% endfor %}

[mesos_slaves]
{% for droplet in slaves %}
{{ droplet.public_ipv4 }} ansible_ssh_user=root
{% endfor %}
"""

parser = argparse.ArgumentParser(description="Create a inventory file for DO")
parser.add_argument("auth", type=str,
                    help="a digital ocean auth token with write permissions")

parser.add_argument("-m", "--master", type=int, default=3,
                    help="the number of master nodes to create")
parser.add_argument("-s", "--slaves", type=int, default=9,
                    help="the number of slave nodes to create")
parser.add_argument("-n", "--name", type=str, default="mesosphere",
                    help="the name/prefix of the cluster")
parser.add_argument("-i", "--inventory", type=str, default="mesos_inv",
                    help="the name of the inventory file to output")

parser.add_argument("-k", "--ssh", action="append",
                    help="the ssh key to install on the droplets")
parser.add_argument("-p", "--provision", default=False, action="store_true",
                    help="run the ansible playbook when done")

parser.add_argument("-r", "--region", type=str, default="lon1",
                    help="the region to create the droplets in")
parser.add_argument("-d", "--droplet", type=str, default="512mb",
                    help="the size of droplet to create in the cluster")
parser.add_argument("--private-networking", type=bool, default=True,
                    help="enable private networking on the droplets")
parser.add_argument("--ipv6", type=bool, default=False,
                    help="enable ipv6 networking on the droplets")
parser.add_argument("--cleanup", default=False, action="store_true",
                    help="destroy any created droplets once done")

def create_droplet(name, options):
    body = {
        "name": "-".join((options.name, name)),
        "region": options.region,
        "size": options.droplet,
        "image": IMAGE,
        "ssh_keys": options.ssh,
        "ipv6": options.ipv6,
        "private_networking": options.private_networking,
    }
    resp = requests.post(BASE_URL + "droplets", auth=(options.auth, ""),
                         headers={"content-type": 'application/json'},
                         data=json.dumps(body))

    logger.info("Create droplet %s body: %s", name, resp.text)
    if resp.status_code != 202:
        logger.warn("Failed to create droplet: %s", resp.status_code)
        return
    return resp.json()

def destroy_droplet(droplet, options):
    resp = requests.delete(BASE_URL + "droplets/" + str(droplet["id"]),
                           auth=(options.auth, ""))
    logger.info("Destroy droplet %s body: %s", droplet["id"], resp.text)
    if resp.status_code != 204:
        logger.critical("Failed to destroy droplet %s, do it yourself", droplet["id"])
        logger.error("Status code: %s", resp.status_code)
        logger.debug("Body: %s", resp.text)
        return False
    return True

def get_ssh_key(name, options):
    resp = requests.get(BASE_URL + "account/keys", auth=(options.auth, ""))
    logger.info("Get keys body: %s", resp.text)
    if resp.status_code != 200:
        logger.critical("Failed to get ssh keys")
        return
    for entry in resp.json()["ssh_keys"]:
        if entry["name"] == name:
            return entry["id"]
    logger.critical("No ssh key %s", name)
    return

def create_masters(options):
    for i in range(options.master):
        name = MASTER_NAMES.format(i)
        droplet = create_droplet(name, options)
        if droplet:
            yield droplet["droplet"]

def create_slaves(options):
    for i in range(options.slaves):
        name = SLAVE_NAMES.format(i)
        droplet = create_droplet(name, options)
        if droplet:
            yield droplet["droplet"]

def add_ip(droplet, options):
    resp = requests.get(BASE_URL + "droplets/" + str(droplet["id"]),
                        auth=(options.auth, ""))
    logger.info("Get droplet %s body: %s", droplet["id"], resp.text)
    if resp.status_code != 200:
        logger.critical("Could not get droplet ip")
        raise RuntimeError("Could not get droplet ip")

    for network in resp.json()["droplet"]["networks"]["v4"]:
        if network["type"] == "public":
            droplet["public_ipv4"] = network["ip_address"]

def create_template(masters, slaves, options):
    tmpl = jinja2.Template(INVENTORY_TEMPLATE)

    with open(options.inventory, "w") as inventory_file:
        inventory_file.write(tmpl.render(masters=masters, slaves=slaves))

def cleanup(masters, slaves, options):
    print("Waiting 60s for all droplets to come online before destroy")
    time.sleep(60)
    for droplet in masters:
        destroy_droplet(droplet, options)
    for droplet in slaves:
        destroy_droplet(droplet, options)

if __name__ == "__main__":
    options = parser.parse_args()
    logger.info("ARGS: %s", options)

    keys = []
    for key_name in options.ssh:
        key_id = get_ssh_key(key_name, options)
        if key_id:
            keys.append(key_id)
    if not keys:
        logger.warn("No keys found")
    options.ssh = keys

    masters = []
    slaves = []
    try:
        for droplet in create_masters(options):
            masters.append(droplet)
        for droplet in create_slaves(options):
            slaves.append(droplet)
        droplets = masters + slaves

        print("Waiting 60s for all droplets to come online before getting ips")
        time.sleep(60)

        for droplet in droplets:
            add_ip(droplet, options)

        create_template(masters, slaves, options)

        if options.provision:
            site_filename = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "site.yml"
            )
            subprocess.call(
                ["ansible-playbook", site_filename, "-i", options.inventory])
    except:
        cleanup(masters, slaves, options)
        raise

    if options.cleanup:
        cleanup(masters, slaves, options)
