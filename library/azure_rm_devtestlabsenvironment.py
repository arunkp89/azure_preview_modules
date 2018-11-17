#!/usr/bin/python
#
# Copyright (c) 2018 Zim Kalinowski, <zikalino@microsoft.com>
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: azure_rm_devtestlabsenvironment
version_added: "2.8"
short_description: Manage Environment instance.
description:
    - Create, update and delete instance of Environment.

options:
    resource_group:
        description:
            - The name of the resource group.
        required: True
    lab_name:
        description:
            - The name of the lab.
        required: True
    user_name:
        description:
            - The name of the user profile.
        required: True
    name:
        description:
            - The name of the environment.
        required: True
    location:
        description:
            - The location of the resource.
    deployment_properties:
        description:
            - The deployment properties of the environment.
        suboptions:
            arm_template_id:
                description:
                    - "The Azure Resource Manager template's identifier."
            parameters:
                description:
                    - The parameters of the Azure Resource Manager template.
                type: list
                suboptions:
                    name:
                        description:
                            - The name of the template parameter.
                    value:
                        description:
                            - The value of the template parameter.
    arm_template_display_name:
        description:
            - The display name of the Azure Resource Manager template that produced the environment.
    unique_identifier:
        description:
            - The unique immutable identifier of a resource (Guid).
    state:
      description:
        - Assert the state of the Environment.
        - Use 'present' to create or update an Environment and 'absent' to delete it.
      default: present
      choices:
        - absent
        - present

extends_documentation_fragment:
    - azure
    - azure_tags

author:
    - "Zim Kalinowski (@zikalino)"

'''

EXAMPLES = '''
  - name: Create (or update) Environment
    azure_rm_devtestlabsenvironment:
      resource_group: NOT FOUND
      lab_name: NOT FOUND
      user_name: NOT FOUND
      name: NOT FOUND
'''

RETURN = '''
id:
    description:
        - The identifier of the resource.
    returned: always
    type: str
    sample: id
'''

import time
from ansible.module_utils.azure_rm_common import AzureRMModuleBase

try:
    from msrestazure.azure_exceptions import CloudError
    from msrest.polling import LROPoller
    from msrestazure.azure_operation import AzureOperationPoller
    from azure.mgmt.devtestlabs import DevTestLabsClient
    from msrest.serialization import Model
except ImportError:
    # This is handled in azure_rm_common
    pass


class Actions:
    NoAction, Create, Update, Delete = range(4)


class AzureRMEnvironments(AzureRMModuleBase):
    """Configuration class for an Azure RM Environment resource"""

    def __init__(self):
        self.module_arg_spec = dict(
            resource_group=dict(
                type='str',
                required=True
            ),
            lab_name=dict(
                type='str',
                required=True
            ),
            user_name=dict(
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
            deployment_properties=dict(
                type='dict'
            ),
            arm_template_display_name=dict(
                type='str'
            ),
            unique_identifier=dict(
                type='str'
            ),
            state=dict(
                type='str',
                default='present',
                choices=['present', 'absent']
            )
        )

        self.resource_group = None
        self.lab_name = None
        self.user_name = None
        self.name = None
        self.dtl_environment = dict()

        self.results = dict(changed=False)
        self.mgmt_client = None
        self.state = None
        self.to_do = Actions.NoAction

        super(AzureRMEnvironments, self).__init__(derived_arg_spec=self.module_arg_spec,
                                                  supports_check_mode=True,
                                                  supports_tags=True)

    def exec_module(self, **kwargs):
        """Main module execution method"""

        for key in list(self.module_arg_spec.keys()) + ['tags']:
            if hasattr(self, key):
                setattr(self, key, kwargs[key])
            elif kwargs[key] is not None:
                if key == "location":
                    self.dtl_environment["location"] = kwargs[key]
                elif key == "deployment_properties":
                    self.dtl_environment["deployment_properties"] = kwargs[key]
                elif key == "arm_template_display_name":
                    self.dtl_environment["arm_template_display_name"] = kwargs[key]
                elif key == "unique_identifier":
                    self.dtl_environment["unique_identifier"] = kwargs[key]

        response = None

        self.mgmt_client = self.get_mgmt_svc_client(DevTestLabsClient,
                                                    base_url=self._cloud_environment.endpoints.resource_manager)

        resource_group = self.get_resource_group(self.resource_group)

        old_response = self.get_environment()

        if not old_response:
            self.log("Environment instance doesn't exist")
            if self.state == 'absent':
                self.log("Old instance didn't exist")
            else:
                self.to_do = Actions.Create
        else:
            self.log("Environment instance already exists")
            if self.state == 'absent':
                self.to_do = Actions.Delete
            elif self.state == 'present':
                if (not default_compare(self.parameters, old_response, '')):
                    self.to_do = Actions.Update

        if (self.to_do == Actions.Create) or (self.to_do == Actions.Update):
            self.log("Need to Create / Update the Environment instance")

            if self.check_mode:
                self.results['changed'] = True
                return self.results

            response = self.create_update_environment()

            self.results['changed'] = True
            self.log("Creation / Update done")
        elif self.to_do == Actions.Delete:
            self.log("Environment instance deleted")
            self.results['changed'] = True

            if self.check_mode:
                return self.results

            self.delete_environment()
            # make sure instance is actually deleted, for some Azure resources, instance is hanging around
            # for some time after deletion -- this should be really fixed in Azure.
            while self.get_environment():
                time.sleep(20)
        else:
            self.log("Environment instance unchanged")
            self.results['changed'] = False
            response = old_response

        if self.state == 'present':
            self.results.update(self.format_item(response))
        return self.results

    def create_update_environment(self):
        '''
        Creates or updates Environment with the specified configuration.

        :return: deserialized Environment instance state dictionary
        '''
        self.log("Creating / Updating the Environment instance {0}".format(self.name))

        try:
            response = self.mgmt_client.environments.create_or_update(resource_group_name=self.resource_group,
                                                                      lab_name=self.lab_name,
                                                                      user_name=self.user_name,
                                                                      name=self.name,
                                                                      dtl_environment=self.dtl_environment)
            if isinstance(response, LROPoller) or isinstance(response, AzureOperationPoller):
                response = self.get_poller_result(response)

        except CloudError as exc:
            self.log('Error attempting to create the Environment instance.')
            self.fail("Error creating the Environment instance: {0}".format(str(exc)))
        return response.as_dict()

    def delete_environment(self):
        '''
        Deletes specified Environment instance in the specified subscription and resource group.

        :return: True
        '''
        self.log("Deleting the Environment instance {0}".format(self.name))
        try:
            response = self.mgmt_client.environments.delete(resource_group_name=self.resource_group,
                                                            lab_name=self.lab_name,
                                                            user_name=self.user_name,
                                                            name=self.name)
        except CloudError as e:
            self.log('Error attempting to delete the Environment instance.')
            self.fail("Error deleting the Environment instance: {0}".format(str(e)))

        return True

    def get_environment(self):
        '''
        Gets the properties of the specified Environment.

        :return: deserialized Environment instance state dictionary
        '''
        self.log("Checking if the Environment instance {0} is present".format(self.name))
        found = False
        try:
            response = self.mgmt_client.environments.get(resource_group_name=self.resource_group,
                                                         lab_name=self.lab_name,
                                                         user_name=self.user_name,
                                                         name=self.name)
            found = True
            self.log("Response : {0}".format(response))
            self.log("Environment instance : {0} found".format(response.name))
        except CloudError as e:
            self.log('Did not find the Environment instance.')
        if found is True:
            return response.as_dict()

        return False

    def format_item(self, d):
        d = {
            'id': d.get('id', None)
        }
        return d


def default_compare(new, old, path):
    if new is None:
        return True
    elif isinstance(new, dict):
        if not isinstance(old, dict):
            return False
        for k in new.keys():
            if not default_compare(new.get(k), old.get(k, None), path + '/' + k):
                return False
        return True
    elif isinstance(new, list):
        if not isinstance(old, list) or len(new) != len(old):
            return False
        if isinstance(old[0], dict):
            key = None
            if 'id' in old[0] and 'id' in new[0]:
                key = 'id'
            elif 'name' in old[0] and 'name' in new[0]:
                key = 'name'
            new = sorted(new, key=lambda x: x.get(key, None))
            old = sorted(old, key=lambda x: x.get(key, None))
        else:
            new = sorted(new)
            old = sorted(old)
        for i in range(len(new)):
            if not default_compare(new[i], old[i], path + '/*'):
                return False
        return True
    else:
        return new == old


def main():
    """Main execution"""
    AzureRMEnvironments()


if __name__ == '__main__':
    main()