#!/usr/bin/python
#
# Copyright (c) 2018 Yunge Zhu, <yungez@microsoft.com>
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: azure_rm_rediscache
version_added: "2.7"
short_description: Manage Azure Redis Cache instance.
description:
    - Create, update and delete instance of Azure Redis Cache.

options:
    resource_group:
        description:
            - Name of the resource group to which the resource belongs.
        required: True
    name:
        description:
            - Unique name of the redis cache to create or update. To create or update a deployment slot, use the {slot} parameter.
        required: True

    location:
        description:
            - Resource location. If not set, location from the resource group will be used as default.
    sku:
        description: Sku info of redis cache.
        suboptions:
            name:
                description: Type of redis cache to deploy
                choices:
                    - basic
                    - standard
                    - premium
                required: True
            size:
                description:
                    - Size of redis cache to deploy.
                    - When I(sku) is C(basic) or C(standard), allowed values are C0, C1, C2, C3, C4, C5, C6.
                    - When I(sku) is C(premium), allowed values are P1, P2, P3, P4.
                    - Please see U(https://docs.microsoft.com/en-us/rest/api/redis/redis/create#sku) for allowed values.
                choices:
                    - C0
                    - C1
                    - C2
                    - C3
                    - C4
                    - C5
                    - C6
                    - P1
                    - P2
                    - P3
                    - P4
                required: True
    enable_non_ssl_port:
        description:
            - When true, the non-ssl redis server port 6379 will be enabled.
        default: false
    configuration:
        description:
            - Dict of redis cache configuration.
    shard_count:
        description:
            - The number of shards to be created when I(sku) is C(premium).
        type: integer
    static_ip:
        description:
            - Static IP address. Required when deploying a redis cache inside an existing Azure virtual network.
    subnet:
        description:
            - Subnet in a virtual network to deploy the redis cache in.
            - "It can be resource id of subnet, eg.
              /subscriptions/{subid}/resourceGroups/{resourceGroupName}/Microsoft.{Network|ClassicNetwork}/VirtualNetworks/vnet1/subnets/subnet1"
            - It can be a dictionary where contains C(name), C(virtual_network_name) and C(resource_group).
            - C(name). Name of the subnet.
            - C(resource_group). Resource group name of the subnet.
            - C(virtual_network_name). Name of virtual network to which this subnet belongs.
    tenant_settings:
        description:
            - Dict of tenant settings.
    state:
      description:
        - Assert the state of the redis cahce.
        - Use 'present' to create or update a redis cache and 'absent' to delete it.
      default: present
      choices:
        - absent
        - present

extends_documentation_fragment:
    - azure
    - azure_tags

author:
    - "Yunge Zhu(@yungezz)"

'''

EXAMPLES = '''
    - name: Create a windows web app with non-exist app service plan
      azure_rm_webapp:
        resource_group: myresourcegroup
        name: mywinwebapp
        plan:
          resource_group: myappserviceplan_rg
          name: myappserviceplan
          is_linux: false
          sku: S1
'''

RETURN = '''
azure_webapp:
    description: Id of current web app.
    returned: always
    type: dict
    sample: {
        "id": "/subscriptions/<subscription_id>/resourceGroups/ansiblewebapp1/providers/Microsoft.Web/sites/ansiblewindowsaaa"
    }
'''

import time
import re
from ansible.module_utils.azure_rm_common import AzureRMModuleBase

try:
    from msrestazure.azure_exceptions import CloudError
    from msrestazure.azure_operation import AzureOperationPoller
    from msrest.serialization import Model
    from azure.mgmt.redis import RedisManagementClient
    from azure.mgmt.redis.models import ( RedisCreateParameters, RedisUpdateParameters, Sku )
except ImportError:
    # This is handled in azure_rm_common
    pass


sku_spec = dict(
    name=dict(type='str'),
    size=dict(
        type='str',
        choices=['C0','C1','C2','C3','C4','C5','C6','P1','P2','P3','P4']
    )
)


def rediscache_to_dict(redis):
    result = dict(
        id=redis.id,
        name=redis.name,
        location=redis.location,
        sku=dict(
            name=redis.sku.name.lower(),
            size=redis.sku.family + str(redis.sku.capacity)
        )
        enable_non_ssl_port=redis.enable_non_ssl_port,
        host_name=redis.host_name,
        shard_count=redis.shard_count,
        subnet=redis.subnet_id,
        static_ip=redis.static_ip,
        provisioning_state=redis.provisioning_state,
        configuration=redis.redis_configuration,
        tenant_settings=redis.tenant_settings,
        tags=redis.tags if redis.tags else None
    )


SUBNET_ID_PATTERN = r'^/subscriptions/[^/]*/resourceGroups/[^/]*/providers/Microsoft.(ClassicNetwork|Network)/virtualNetworks/[^/]*/subnets/[^/]*$'}

class Actions:
    NoAction, Create, Update, Delete = range(4)


class AzureRMRedisCaches(AzureRMModuleBase):
    """Configuration class for an Azure RM Redis Cache resource"""

    def __init__(self):
        self.module_arg_spec = dict(
            resource_group=dict(
                type='str',
                required=True
            ),
            name=dict(
                type='str',
                required=True
            ),
            location=dict(
                type='str'
            ),
            sku=dict(
                type='dct',
                options=sku_spec
            ),
            enable_non_ssl_port=dict(
                type='bool',
                default=False
            ),
            configuration=dict(
                type='dict'
            ),
            shard_count=dict(
                type='integer'
            ),
            static_ip=dict(
                type='str'
            ),
            subnet=dict(
                type='raw'
            ),
            tenant_settings=dict(
                type='dict'
            ),
            state=dict(
                type='str',
                default='present',
                choices=['present', 'absent']
            )
        )

        self._client = None

        self.resource_group = None
        self.name = None
        self.location = None

        self.sku = None
        self.size = None
        self.enable_non_ssl_port = False
        self.configuration_file_path = None
        self.shard_count = None
        self.static_ip = None
        self.subnet = None
        self.tenant_settings = None

        self.tags = None

        self.results = dict(
            changed=False,
            id=None,
        )
        self.state = None
        self.to_do = Actions.NoAction

        self.frameworks = None

        super(AzureRMWebApps, self).__init__(derived_arg_spec=self.module_arg_spec,
                                             supports_check_mode=True,
                                             supports_tags=True)

    def exec_module(self, **kwargs):
        """Main module execution method"""

        for key in list(self.module_arg_spec.keys()) + ['tags']:
            setattr(self, key, kwargs[key])

        old_response = None
        response = None
        to_be_updated = False

        # get management client
        self._client = self.get_mgmt_svc_client(RedisManagementClient,
                                                base_url=self._cloud_environment.endpoints.resource_manager,
                                                api_version='2016-04-01')

        # set location
        resource_group = self.get_resource_group(self.resource_group)
        if not self.location:
            self.location = resource_group.location

        # check subnet exists
        if self.subnet:
            if self.parse_subnet():
                subnet_id = self.get_subnet()
                if not subnet_id:
                    self.fail("Subnet {0} not exists".format(self.subnet))
                self.subnet = subnet_id
            else:
                self.fail("Invalid subnet configuration, either be a subnet resource id, or dict with name, virtual_network_name and resource_group")

        # get existing redis cache
        old_response = self.get_rediscache()

        if old_response:
            self.results['id'] = old_response['id']

        if self.state == 'present':
            # if redis not exists
            if not old_response:
                self.log("Redis cache instance doesn't exist")

                to_be_updated = True
                self.to_do = Actions.Create
                
                if not self.sku:
                    self.fail("Please specify sku to creating new redis cache.")

            else:
                # redis exists already, do update
                self.log("Redis cache instance already exists")

                update_tags, self.site.tags = self.update_tags(old_response.get('tags', None))

                if update_tags:
                    to_be_updated = True
                    self.to_do = Actions.Update

                # check if update
                if self.check_update(response):
                    to_be_updated = True
                    self.to_do = Actions.Update

        elif self.state == 'absent':
            if old_response:
                self.log("Delete Redis cache instance")
                self.results['changed'] = True

                if self.check_mode:
                    return self.results

                self.delete_webapp()

                self.log('Redis cache instance deleted')

            else:
                self.fail("Redis cache {0} not exists.".format(self.name))

        if to_be_updated:
            self.log('Need to Create/Update redis cache')
            self.results['changed'] = True

            if self.check_mode:
                return self.results

            if self.to_do == Actions.Create:
                response = self.create_rediscache()
                self.results['id'] = response['id']
                self.results['host_name'] = response['host_name']
            
            if self.to_do == Actions.Update:
                response = self.update_rediscache()
                self.results['id'] = response['id']
                self.results['host_name'] = response['host_name']

        return self.results

    def check_update(self, existing):
        if existing['enable_non_ssl_port'] != self.enable_non_ssl_port:
            self.log("enable_non_ssl_port diff: origin {0} / update {1}".format(existing['enable_non_ssl_port'], self.enable_non_ssl_port))
            return True
        if existing['sku'] != self.sku:
            self.log("sku diff: origin {0} / update {1}".format(existing['sku'], self.sku))
            return True
        if existing['configuration'] != self.configuration:
            self.log("configuration diff: origin {0} / update {1}".format(existing['configuration'], self.configuration))
            return True
        if existing['tenant_settings'] != self.tenant_settings:
            self.log("tenant_settings diff: origin {0} / update {1}".format(existing['tenant_settings'], self.tenant_settings))
            return True
        if existing['shard_count'] != self.shard_count:
            self.log("shard_count diff: origin {0} / update {1}".format(existing['shard_count'], self.shard_count))
            return True
        if existing['subnet'] != self.subnet:
            self.log("subnet diff: origin {0} / update {1}".format(existing['subnet'], self.subnet))
            return True
        if existing['static_ip'] != self.static_ip:
            self.log("static_ip diff: origin {0} / update {1}".format(existing['static_ip'], self.static_ip))
            return True
        return False

    def create_rediscache(self):
        '''
        Creates redis cache instance with the specified configuration.

        :return: deserialized redis cache instance state dictionary
        '''
        self.log(
            "Creating redis cache instance {0}".format(self.name))

        try:
            params = RedisCreateParameters(
                self.location,
                Sku(self.sku['name'].title(), self.sku['size'][0], self.sku['size'][1:]),
                self.tags,
                self.configuration,
                self.enable_non_ssl_port,
                self.tenant_settings,
                self.shard_count,
                self.subnet,
                self.static_ip
            )

            response = self._client.redis.create(resource_group_name=self.resource_group,
                                                name=self.name,
                                                parameters=params)
            if isinstance(response, AzureOperationPoller):
                response = self.get_poller_result(response)

        except CloudError as exc:
            self.log('Error attempting to create the redis cache instance.')
            self.fail(
                "Error creating the redis cache instance: {0}".format(str(exc)))
        return rediscache_to_dict(response)

    def update_rediscache(self):
        '''
        Updates redis cache instance with the specified configuration.

        :return: redis cache instance state dictionary
        '''
        self.log(
            "Updating redis cache instance {0}".format(self.name))

        try:
            params = RedisUpdateParameters(
                self.configuration,
                self.enable_non_ssl_port,
                self.tenant_settings,
                self.shard_count,
                self.subnet,
                self.static_ip
                Sku(self.sku['name'].title(), self.sku['size'][0], self.sku['size'][1:]),
                self.tags
            )

            response = self._client.redis.update(resource_group_name=self.resource_group,
                                                 name=self.name,
                                                 parameters=params)
            if isinstance(response, AzureOperationPoller):
                response = self.get_poller_result(response)

        except CloudError as exc:
            self.log('Error attempting to update the redis cache instance.')
            self.fail(
                "Error updating the redis cache instance: {0}".format(str(exc)))
        return rediscache_to_dict(response)

    def delete_rediscache(self):
        '''
        Deletes specified redis cache instance in the specified subscription and resource group.

        :return: True
        '''
        self.log("Deleting the redis cache instance {0}".format(self.name))
        try:
            response = self._client.redis.delete(resource_group_name=self.resource_group,
                                                 name=self.name)
        except CloudError as e:
            self.log('Error attempting to delete the redis cache instance.')
            self.fail(
                "Error deleting the redis cache instance: {0}".format(str(e)))
        return True

    def get_rediscache(self):
        '''
        Gets the properties of the specified redis cache instance.

        :return: redis cache instance state dictionary
        '''
        self.log("Checking if the redis cache instance {0} is present".format(self.name))

        response = None

        try:
            response = self._client.redis.get(resource_group_name=self.resource_group,
                                              name=self.name)

            self.log("Response : {0}".format(response))
            self.log("Redis cache instance : {0} found".format(response.name))
            return rediscache_to_dict(response)

        except CloudError as ex:
            self.log("Didn't find redis cache {0} in resource group {1}".format(
                self.name, self.resource_group))

        return False

    def get_subnet(self):
        '''
        Gets the properties of the specified subnet.

        :return: subnet id
        '''
        self.log("Checking if the subnet {0} is present".format(self.name))

        response = None

        try:
            response = self.network_client.subnets.get(self.subnet['resource_group'],
                                                       self.subnet['virtual_network_name'],
                                                       self.subnet['name'])

            self.log("Subnet found : {0}".format(response))
            return response.id

        except CloudError as ex:
            self.log("Didn't find subnet {0} in resource group {1}".format(
                self.subnet['name'], self.subnet['resource_group']))

        return False

    def parse_subnet(self):
        if isinstance(self.subnet, dict):
            if not hasattr(self.subnet, 'virtual_network_name') or \
               not hasattr(self.subnet, 'name'):
                self.fail("Subnet dict must contains virtual_network_name and name")
            if not hasattr(self.subnet, 'resource_group'):
                self.subnet['resource_group'] = self.resource_group
        else:
            return re.match(self.subnet, string)
        return True


def main():
    """Main execution"""
    AzureRMWebApps()


if __name__ == '__main__':
    main()