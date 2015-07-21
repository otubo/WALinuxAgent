# Windows Azure Linux Agent
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.4+ and Openssl 1.0+
#

import azurelinuxagent.conf as conf
from azurelinuxagent.utils.osutil import OSUTIL
import azurelinuxagent.protocol as prot
import azurelinuxagent.protocol.ovfenv as ovf
import azurelinuxagent.utils.fileutil as fileutil
import azurelinuxagent.utils.shellutil as shellutil

class DeprovisionAction(object):
    def __init__(self, func, args=[], kwargs={}):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def invoke(self):
        self.func(*self.args, **self.kwargs)

class DeprovisionHandler(object):

    def del_root_password(self, warnings, actions):
        warnings.append("WARNING! root password will be disabled. "
                        "You will not be able to login as root.")

        actions.append(DeprovisionAction(OSUTIL.del_root_password))

    def del_user(self, warnings, actions):

        try:
            ovfenv = ovf.get_ovf_env()
        except prot.ProtocolError:
            warnings.append("WARNING! ovf-env.xml is not found.")
            warnings.append("WARNING! Skip delete user.")
            return

        username = ovfenv.get_username()
        warnings.append(("WARNING! {0} account and entire home directory "
                         "will be deleted.").format(username))
        actions.append(DeprovisionAction(OSUTIL.del_account, [username]))


    def regen_ssh_host_key(self, warnings, actions):
        warnings.append("WARNING! All SSH host key pairs will be deleted.")
        actions.append(DeprovisionAction(OSUTIL.set_hostname,
                                         ['localhost.localdomain']))
        actions.append(DeprovisionAction(shellutil.run,
                                         ['rm -f /etc/ssh/ssh_host_*key*']))

    def stop_agent_service(self, warnings, actions):
        warnings.append("WARNING! The waagent service will be stopped.")
        actions.append(DeprovisionAction(OSUTIL.stop_agent_service))

    def del_files(self, warnings, actions):
        files_to_del = ['/root/.bash_history', '/var/log/waagent.log']
        actions.append(DeprovisionAction(fileutil.rm_files, files_to_del))

    def del_dhcp_lease(self, warnings, actions):
        warnings.append("WARNING! Cached DHCP leases will be deleted.")
        dirs_to_del = ["/var/lib/dhclient", "/var/lib/dhcpcd", "/var/lib/dhcp"]
        actions.append(DeprovisionAction(fileutil.rm_dirs, dirs_to_del))

    def del_lib_dir(self, warnings, actions):
        dirs_to_del = [OSUTIL.get_lib_dir()]
        actions.append(DeprovisionAction(fileutil.rm_dirs, dirs_to_del))

    def setup(self, deluser):
        warnings = []
        actions = []

        self.stop_agent_service(warnings, actions)
        if conf.get_switch("Provisioning.RegenerateSshHostkey", False):
            self.regen_ssh_host_key(warnings, actions)

        self.del_dhcp_lease(warnings, actions)

        if conf.get_switch("Provisioning.DeleteRootPassword", False):
            self.del_root_password(warnings, actions)

        self.del_lib_dir(warnings, actions)
        self.del_files(warnings, actions)

        if deluser:
            self.del_user(warnings, actions)

        return warnings, actions

    def deprovision(self, force=False, deluser=False):
        warnings, actions = self.setup(deluser)
        for warning in warnings:
            print warning

        if not force:
            confirm = raw_input("Do you want to proceed (y/n)")
            if not confirm.lower().startswith('y'):
                return

        for action in actions:
            action.invoke()

