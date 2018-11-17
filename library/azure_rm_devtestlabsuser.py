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
module: azure_rm_devtestlabsuser
version_added: "2.8"
short_description: Manage User instance.
description:
    - Create, update and delete instance of User.

options:
    resource_group:
        description:
            - The name of the resource group.
        required: True
    lab_name:
        description:
            - The name of the lab.
        required: True
    name:
        description:
            - The name of the user profile.
        required: True
    location:
        description:
            - The location of the resource.
    identity:
        description:
            - The identity of the user.
        suboptions:
            principal_name:
                description:
                    - Set to the principal name / UPN of the client JWT making the request.
            principal_id:
                description:
                    - Set to the principal Id of the client JWT making the request. Service principal will not have the principal Id.
            tenant_id:
                description:
                    - Set to the tenant ID of the client JWT making the request.
            object_id:
                description:
                    - "Set to the object Id of the client JWT making the request. Not all users have object Id. For CSP (reseller) scenarios for example,
                       object Id is not available."
            app_id:
                description:
                    - Set to the app Id of the client JWT making the request.
    secret_store:
        description:
            - The secret store of the user.
        suboptions:
            key_vault_uri:
                description:
                    - "The URI of the user's Key vault."
            key_vault_id:
                description:
                    - "The ID of the user's Key vault."
    unique_identifier:
        description:
            - The unique immutable identifier of a resource (Guid).
    state:
      description:
        - Assert the state of the User.
        - Use 'present' to create or update an User and 'absent' to delete it.
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
  - name: Create (or update) User
    azure_rm_devtestlabsuser:
      resource_group: NOT FOUND
      lab_name: NOT FOUND
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


class AzureRMUsers(AzureRMModuleBase):
    """Configuration class for an Azure RM User resource"""

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
            name=dict(
                type='str',
                required=True
            ),
            location=dict(
                type='str'
            ),
            identity=dict(
                type='dict'
            ),
            secret_store=dict(
                type='dict'
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
        self.name = None
        self.user = dict()

        self.results = dict(changed=False)
        self.mgmt_client = None
        self.state = None
        self.to_do = Actions.NoAction

        super(AzureRMUsers, self).__init__(derived_arg_spec=self.module_arg_spec,
                                           supports_check_mode=True,
                                           supports_tags=True)

    def exec_module(self, **kwargs):
        """Main module execution method"""

        for key in list(self.module_arg_spec.keys()) + ['tags']:
            if hasattr(self, key):
                setattr(self, key, kwargs[key])
            elif kwargs[key] is not None:
                if key == "location":
                    self.user["location"] = kwargs[key]
                elif key == "identity":
                    self.user["identity"] = kwargs[key]
                elif key == "secret_store":
                    self.user["secret_store"] = kwargs[key]
                elif key == "unique_identifier":
                    self.user["unique_identifier"] = kwargs[key]

        response = None

        self.mgmt_client = self.get_mgmt_svc_client(DevTestLabsClient,
                                                    base_url=self._cloud_environment.endpoints.resource_manager)

        resource_group = self.get_resource_group(self.resource_group)

        old_response = self.get_user()

        if not old_response:
            self.log("User instance doesn't exist")
            if self.state == 'absent':
                self.log("Old instance didn't exist")
            else:
                self.to_do = Actions.Create
        else:
            self.log("User instance already exists")
            if self.state == 'absent':
                self.to_do = Actions.Delete
            elif self.state == 'present':
                if (not default_compare(self.parameters, old_response, '')):
                    self.to_do = Actions.Update

        if (self.to_do == Actions.Create) or (self.to_do == Actions.Update):
            self.log("Need to Create / Update the User instance")

            if self.check_mode:
                self.results['changed'] = True
                return self.results

            response = self.create_update_user()

            self.results['changed'] = True
            self.log("Creation / Update done")
        elif self.to_do == Actions.Delete:
            self.log("User instance deleted")
            self.results['changed'] = True

            if self.check_mode:
                return self.results

            self.delete_user()
            # make sure instance is actually deleted, for some Azure resources, instance is hanging around
            # for some time after deletion -- this should be really fixed in Azure.
            while self.get_user():
                time.sleep(20)
        else:
            self.log("User instance unchanged")
            self.results['changed'] = False
            response = old_response

        if self.state == 'present':
            self.results.update(self.format_item(response))
        return self.results

    def create_update_user(self):
        '''
        Creates or updates User with the specified configuration.

        :return: deserialized User instance state dictionary
        '''
        self.log("Creating / Updating the User instance {0}".format(self.name))

        try:
            response = self.mgmt_client.users.create_or_update(resource_group_name=self.resource_group,
                                                               lab_name=self.lab_name,
                                                               name=self.name,
                                                               user=self.user)
            if isinstance(response, LROPoller) or isinstance(response, AzureOperationPoller):
                response = self.get_poller_result(response)

        except CloudError as exc:
            self.log('Error attempting to create the User instance.')
            self.fail("Error creating the User instance: {0}".format(str(exc)))
        return response.as_dict()

    def delete_user(self):
        '''
        Deletes specified User instance in the specified subscription and resource group.

        :return: True
        '''
        self.log("Deleting the User instance {0}".format(self.name))
        try:
            response = self.mgmt_client.users.delete(resource_group_name=self.resource_group,
                                                     lab_name=self.lab_name,
                                                     name=self.name)
        except CloudError as e:
            self.log('Error attempting to delete the User instance.')
            self.fail("Error deleting the User instance: {0}".format(str(e)))

        return True

    def get_user(self):
        '''
        Gets the properties of the specified User.

        :return: deserialized User instance state dictionary
        '''
        self.log("Checking if the User instance {0} is present".format(self.name))
        found = False
        try:
            response = self.mgmt_client.users.get(resource_group_name=self.resource_group,
                                                  lab_name=self.lab_name,
                                                  name=self.name)
            found = True
            self.log("Response : {0}".format(response))
            self.log("User instance : {0} found".format(response.name))
        except CloudError as e:
            self.log('Did not find the User instance.')
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
    AzureRMUsers()


if __name__ == '__main__':
    main()