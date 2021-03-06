#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from gnocchiclient import client
from gnocchiclient import exceptions as gnocchi_exc
from oslo_log import log

from ceilometer import keystone_client

LOG = log.getLogger(__name__)


def get_gnocchiclient(conf, endpoint_override=None):
    group = conf.dispatcher_gnocchi.auth_section
    session = keystone_client.get_session(conf, group=group)
    return client.Client('1', session,
                         interface=conf[group].interface,
                         region_name=conf[group].region_name,
                         endpoint_override=endpoint_override)


# NOTE(sileht): This is the initial resource types created in Gnocchi
# This list must never change to keep in sync with what Gnocchi early
# database contents was containing
resources_initial = {
    "image": {
        "name": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "container_format": {"type": "string", "min_length": 0,
                             "max_length": 255, "required": True},
        "disk_format": {"type": "string", "min_length": 0, "max_length": 255,
                        "required": True},
    },
    "instance": {
        "flavor_id": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
        "image_ref": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": False},
        "host": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "display_name": {"type": "string", "min_length": 0, "max_length": 255,
                         "required": True},
        "server_group": {"type": "string", "min_length": 0, "max_length": 255,
                         "required": False},
    },
    "instance_disk": {
        "name": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "instance_id": {"type": "uuid", "required": True},
    },
    "instance_network_interface": {
        "name": {"type": "string", "min_length": 0, "max_length": 255,
                 "required": True},
        "instance_id": {"type": "uuid", "required": True},
    },
    "volume": {
        "display_name": {"type": "string", "min_length": 0, "max_length": 255,
                         "required": False},
    },
    "swift_account": {},
    "ceph_account": {},
    "network": {},
    "identity": {},
    "ipmi": {},
    "stack": {},
    "host": {
        "host_name": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
    },
    "host_network_interface": {
        "host_name": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
        "device_name": {"type": "string", "min_length": 0, "max_length": 255,
                        "required": False},
    },
    "host_disk": {
        "host_name": {"type": "string", "min_length": 0, "max_length": 255,
                      "required": True},
        "device_name": {"type": "string", "min_length": 0, "max_length": 255,
                        "required": False},
    },
}

# NOTE(sileht): Order matter this have to be considered like alembic migration
# code, because it updates the resources schema of Gnocchi
resources_update_operation = [
    {"desc": "add volume_type to volume",
     "type": "update_attribute_type",
     "resource_type": "volume",
     "data": {
         "op": "add",
         "path": "/attributes/volume_type",
         "value": {"type": "string", "min_length": 0, "max_length": 255,
                   "required": False}}},
]


def upgrade_resource_types(conf):
    gnocchi = get_gnocchiclient(conf)
    for name, attributes in resources_initial.items():
        try:
            gnocchi.resource_type.get(name=name)
        except gnocchi_exc.ResourceTypeNotFound:
            rt = {'name': name, 'attributes': attributes}
            try:
                gnocchi.resource_type.create(resource_type=rt)
            except Exception:
                LOG.error("Gnocchi resource creation fail", exc_info=True)
                return

    for op in resources_update_operation:
        if op['type'] == 'update_attribute_type':
            rt = gnocchi.resource_type.get(name=op['resource_type'])
            attrib = op['data']['path'].replace('/attributes', '')
            if op['data']['op'] == 'add' and attrib in rt['attributes']:
                continue
            if op['data']['op'] == 'remove' and attrib not in rt['attributes']:
                continue
            try:
                gnocchi.resource_type.update(op['resource_type'], op['data'])
            except Exception:
                LOG.error("Gnocchi resource update fail: %s", op['desc'],
                          exc_info=True)
                return
