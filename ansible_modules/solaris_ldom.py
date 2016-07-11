#!/usr/bin/python

import platform, subprocess, sys, re
sys.path.append("/home/clallen/solaris_venv/lib/python2.7/site-packages")
sys.path.append("/home/clallen/work/autobuild/ansible_modules")
from agent.lib.ldoms.ldmxml import *
from ldevblock import LDEVBlock

DOCUMENTATION = """
---
module: solaris_ldom
short_description: Manage Solaris LDOM
description:
    - Create and modify a Solaris logical domain.
author: Clint Allen
requirements:
    - Solaris 11.3 or higher
options:
    name:
        required: true
        description:
            - Domain name.  If the domain does not exist, it will be created.
    state:
        required: false
        description:
            - C(same), domain state is unchanged.
            - C(inactive), domain is stopped and unbound.
            - C(bound), domain is stopped and bound.
            - C(active), domain is started.
            - C(deleted), domain is removed (vdsdevs are not modified)
        choices: ['same', 'inactive', 'bound', 'active', 'deleted']
        default: same
    cores:
        required: false
        description:
            - Number of CPU cores assigned to the domain.
    cpu_arch:
        required: false
        description:
            - Type of CPU architecture(s) the domain will run on.
            - C(generic), configures a guest domain for a CPU-type-independent
              migration.
            - C(native), configures a guest domain to migrate only between
              platforms that have the same CPU type.
            - C(migration-class1), a cross-CPU migration family for SPARC T4,
              SPARC T5, SPARC M5, and SPARC M6 platforms that supports hardware
              cryptography across these migrations so that there is a lower
              bound to the supported CPUs.  This value is not compatible with
              UltraSPARC T2, UltraSPARC T2 Plus, or SPARC T3 platforms, or
              Fujitsu M10 servers.
            - C(sparc64-class1), a cross-CPU migration family for SPARC64
              platforms. The ``sparc64-class1`` value is based on SPARC64
              instructions, so it has a greater number of instructions than the
              ``generic`` value. Therefore, the ``sparc64-class1`` value does
              not have a performance impact compared to the ``generic`` value.
              This value is not compatible with UltraSPARC T2, UltraSPARC T2
              Plus, SPARC T3, SPARC T4, SPARC T5, SPARC M5, or SPARC M6
              platforms.
        choices: ['generic', 'native', 'migration-class1', 'sparc64-class1']
        default: migration-class1
    memory:
        required: false
        type: C{int}
        description:
            - Amount of memory, in gigabytes, assigned to the domain.
    domain_vars:
        required: false
        type: C{dict}
        description:
            - A dictionary of domain variables.
              Existing variables will be overwritten, otherwise new ones will be
              created.
    vdisks:
        required: false
        type: C{list} of C{dict}
        description:
            - A list of dictionaries describing vdisks to be added to the
              domain.  Each dictionary must have these entries:
            - * vdisk: The vdisk name.
            - * vds: The name of the virtual disk service (vds) that the virtual
              disk will use to access its backend.
            - * volume: The name of the volume from the virtual disk service (vds)
              associated with the virtual disk.
            - * backend: The backend device node.
            - * id: The vdisk ID.  Used to determine device number in the domain,
              e.g. /dev/dsk/c0d*id*.  Type: C{int}
            - Optionally "mpgroup" may be specified.  This will be used to
              set the volume's multipath group.
    vnets:
        required: false
        type: C{list} of C{dict}
        description:
            - A list of dictionaries describing vnets to be added to the domain.
              Each dictionary must have these entries:
            - * vnet: The vnet name.
            - * vswitch: The virtual switch (VSW) to connect the vnet to.
            - * id: The device id of the network device.  Type: C{int}
            - * pvid: Port VLAN-ID.  Specifies the VLAN to which the virtual 
              network device needs to be a member, in untagged mode.
              Type: C{int}
    rac_dbvers:
        required: false
        type: C{string}
        description:
            - The RAC database version (e.g. 12.1.0.2).  This will be used to 
              name the "dbdisk" and "gidisk" OS vdisks.
              IF THIS OPTION IS PRESENT THE "rac_storage" OPTION MUST ALSO BE PRESENT.
    rac_storage:
        required: false
        type: C{list}
        description:
            - Discover, configure, and attach backend storage needed for
              Oracle RAC database storage, per LDEV block name.  
              This can be used instead of individual "vdisks" options.  It is
              used to find and configure SAN disks.  It is case-sensitive, 
              and the storage device nodes must already exist and be shared to
              the target service domains.  It will usually correspond to a block
              of LDEVs (DATA, FRA, OCR, etc).
              IF THIS OPTION IS PRESENT THE "rac_dbvers" OPTION MUST ALSO BE
              PRESENT.
"""

EXAMPLES = """
# Create a new domain with no properties set (state will be ``inactive``)
solaris_ldom: name="{{ldom_name}}"

# Start a domain (the ``active`` state - if domain is inactive it will be bound)
# *Note that a domain will not start without at least CPU and RAM assigned*
solaris_ldom: name="{{ldom_name}}" state=active

# Bind a domain (the ``bound`` state - if domain is running it will be shut
# down)
solaris_ldom: name="{{ldom_name}}" state=bound

# Unbind a domain (the ``inactive`` state - if domain is running it will be shut
# down)
solaris_ldom: name="{{ldom_name}}" state=inactive

# Create a new domain, set some basic properties, and boot it
solaris_ldom:
    name: "{{ldom_name}}"
    state: active
    cores: 1
    memory: 8
    domain_vars:
        {
        "boot-device": "net",
        "boot-file": "- install"
        }
    vdisks: [
                {
                "vdisk": "rootdisk0",
                "vds": "primary-vds0",
                "volume": "{{ldom_name}}-rootdisk0",
                "id": 0,
                "backend": "/dev/zvol/dsk/rpool/ovm/images/{{ldom_name}}"
                },
                {
                "vdisk": "appdisk0",
                "vds": "primary-vds0",
                "volume": "{{ldom_name}}-appdisk0",
                "id": 1,
                "backend": "/dev/zvol/dsk/rpool/ovm/images/{{ldom_name}}-app"
                }
            ]
    vnets: [
                {
                "vnet": "mgmt0",
                "vswitch": "primary-vsw0",
                "id": 0,
                "pvid": 1
                }
           ]

# Create an Oracle RAC node:
solaris_ldom:
    name: "{{ldom_name}}"
    cores: 2
    memory: 16
    rac_dbvers: "11.2.0.4"
    rac_storage: [ "DEV_ENV_1", "TEST_ENV_2" ]

# Change properties of an existing domain (state stays the same if not
# specified)
solaris_ldom:
    name: "{{ldom_name}}"
    domain_vars: { "boot-device": "disk" }
    memory: 16

# Remove a domain variable
solaris_ldom: name="{{ldom_name}}" domain_vars={ "boot-file": }
"""


class LDOM:
    def __init__(self, module):
        self.module = module
        self.name = self.module.params["name"]
        self.cores = self.module.params["cores"]
        self.cpu_arch = self.module.params["cpu_arch"]
        self.memory = self.module.params["memory"]
        self.domain_vars = self.module.params["domain_vars"]
        self.vdisks = self.module.params["vdisks"]
        self.vnets = self.module.params["vnets"]
        self.rac_dbvers = self.module.params["rac_dbvers"]
        self.rac_storage = self.module.params["rac_storage"]

        self.changed = False
        self.msg = []

        self.lxc = LDMXMLConnection()

        self.node_id = self.name[-1]
        # VDS used for each node is one less than its ID
        # (domain1 uses vds0, domain2 uses vds1, etc)
        self.vds_id = str(int(self.node_id)-1)

        if self.module.check_mode:
            self.msg.append('RUNNING IN CHECK MODE - NO CHANGES WILL BE MADE')

    def create(self):
        if not self.module.check_mode:
            try:
                self.lxc.create(self.name, cpu_arch=self.cpu_arch)
            except LDMError as e:
                self.module.fail_json(msg = "Unable to create domain:"+
                                      str(e))
            else:
                self.changed = True
        self.msg.append("Domain created")

    def delete(self):
        if not self.exists():
            self.module.fail_json(msg = "Domain does not exist, cannot delete")
        elif not self.module.check_mode:
            if self.is_active:
                self.state_inactive()
            try:
                self.lxc.destroy(self.name)
            except LDMError as e:
                self.module.fail_json(msg = "Unable to delete domain:"+
                                      str(e))
            else:
                self.changed = True
        self.msg.append("Domain deleted")

    def set_cores(self):
        if not self.module.check_mode:
            try:
                self.lxc.set_core(self.name, self.cores)
            except LDMError as e:
                self.msg.append("Unable to set cores: "+str(e))
                return
            else:
                self.changed = True
        self.msg.append("Cores set to: "+str(self.cores))

    def set_memory(self):
        if not self.module.check_mode:
            try:
                self.lxc.set_memory(self.name, self.memory*1024*1024*1024)
            except LDMError as e:
                self.msg.append("Unable to set memory: "+str(e))
                return
            else:
                self.changed = True
        self.msg.append("Memory set to: "+str(self.memory)+"G")

    def set_vars(self):
        if not self.module.check_mode:
            try:
                self.lxc.update_variables(self.name, self.domain_vars)
            except LDMError as e:
                self.msg.append("Unable to set domain variables: "+str(e))
                return
            else:
                self.changed = True
        for varname, varval in self.domain_vars.iteritems():
            if varval is None:
                self.msg.append("Removed variable '"+varname+"'")
            else:
                self.msg.append("Set variable '"+varname+"' to: '"+varval+"'")

    def set_vdisks(self):
        failed = False
        for vdisk in self.vdisks:
            if vdisk["vdisk"] is None:
                self.msg.append("COULD NOT ADD VDISK - VDISK NAME REQUIRED")
                failed = True
                break
            if vdisk["vds"] is None:
                self.msg.append("COULD NOT ADD VDISK - VDS REQUIRED")
                failed = True
                break
            if vdisk["backend"] is None:
                self.msg.append("COULD NOT ADD VDISK - BACKEND REQUIRED")
                failed = True
                break
            if vdisk["volume"] is None:
                self.msg.append("COULD NOT ADD VDISK - VOLUME REQUIRED")
                failed = True
                break
            if vdisk["id"] is None:
                self.msg.append("COULD NOT ADD VDISK - ID REQUIRED")
                failed = True
                break
            if vdisk["mpgroup"] is None:
                self.msg.append("COULD NOT ADD VDISK - MPGROUP REQUIRED")
                failed = True
                break
            if not self.module.check_mode:
                try:
                    self.lxc.add_vdsdev(vdisk["vds"], vdisk["volume"],
                                        vdisk["backend"],
                                        mpgroup=vdisk["mpgroup"],
                                        shared=True)
                    if not re.match(r"^secondary", vdisk["vds"]):
                        self.lxc.add_vdisk(self.name, vdisk["vdisk"], vdisk["vds"],
                                           volume=vdisk["volume"], id=vdisk["id"])
                except LDMError as e:
                    self.module.fail_json(msg = str(e))
                else:
                    self.changed = True
        if not failed:
            for vdisk in self.vdisks:
                self.msg.append("Added vdisk: "+vdisk["vdisk"])

    def set_vnets(self):
        failed = False
        for vnet in self.vnets:
            if vnet["vnet"] is None:
                self.msg.append("COULD NOT ADD VNET - VNET NAME REQUIRED")
                failed = True
                break
            if vnet["vswitch"] is None:
                self.msg.append("COULD NOT ADD VNET - VSWITCH REQUIRED")
                failed = True
                break
            if vnet["pvid"] is None:
                self.msg.append("COULD NOT ADD VNET - PVID REQUIRED")
                failed = True
                break
            if vnet["id"] is None:
                self.msg.append("COULD NOT ADD VNET - ID REQUIRED")
                failed = True
                break
            if not self.module.check_mode:
                try:
                    self.lxc.add_vnet(self.name, vnet["vnet"], vnet["vswitch"],
                                      pvid = vnet["pvid"], id = vnet["id"])
                except LDMError as e:
                    self.msg.append("Unable to set vnets: "+str(e))
                    return
                else:
                    self.changed = True
        if not failed:
            for vnet in self.vnets:
                self.msg.append("Added vnet: "+vnet["vnet"])

    def setup_rac_OS_disks(self):
        if not self.module.check_mode:
            devices = LDEVBlock.hds_scan(self.name)
            try:
                self.vdisks = [
                    # primary
                    { "vdisk": "rootdisk0",
                    "vds": "primary-vds"+self.vds_id,
                    "volume": self.name+"-rootdisk0",
                    "id": 0,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_01"],
                    "mpgroup": self.name+"-rootdisk0" },
                    { "vdisk": "appdisk0",
                    "vds": "primary-vds"+self.vds_id,
                    "volume": self.name+"-appdisk0",
                    "id": 1,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_02"],
                    "mpgroup": self.name+"-appdisk0" },
                    { "vdisk": "gidisk_"+self.rac_dbvers,
                    "vds": "primary-vds"+self.vds_id,
                    "volume": self.name+"-gidisk0",
                    "id": 2,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_03"],
                    "mpgroup": self.name+"-gidisk0" },
                    { "vdisk": "dbdisk_"+self.rac_dbvers,
                    "vds": "primary-vds"+self.vds_id,
                    "volume": self.name+"-dbdisk0",
                    "id": 3,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_04"],
                    "mpgroup": self.name+"-dbdisk0" },
                    { "vdisk": self.name+"-cmd0",
                    "vds": "primary-vds"+self.vds_id,
                    "volume": self.name+"-cmd0",
                    "id": 99,
                    "backend": "/dev/dsk/"+
                    LDEVBlock.get_cmd_device(devices[self.name+"_OS_01"]),
                    "mpgroup": self.name+"-cmd0" },
                    # secondary
                    { "vdisk": "rootdisk0",
                    "vds": "secondary-vds"+self.vds_id,
                    "volume": self.name+"-rootdisk0",
                    "id": 0,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_01"],
                    "mpgroup": self.name+"-rootdisk0" },
                    { "vdisk": "appdisk0",
                    "vds": "secondary-vds"+self.vds_id,
                    "volume": self.name+"-appdisk0",
                    "id": 1,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_02"],
                    "mpgroup": self.name+"-appdisk0" },
                    { "vdisk": "gidisk_"+self.rac_dbvers,
                    "vds": "secondary-vds"+self.vds_id,
                    "volume": self.name+"-gidisk0",
                    "id": 2,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_03"],
                    "mpgroup": self.name+"-gidisk0" },
                    { "vdisk": "dbdisk_"+self.rac_dbvers,
                    "vds": "secondary-vds"+self.vds_id,
                    "volume": self.name+"-dbdisk0",
                    "id": 3,
                    "backend": "/dev/dsk/"+devices[self.name+"_OS_04"],
                    "mpgroup": self.name+"-dbdisk0" },
                    { "vdisk": self.name+"cmd0",
                    "vds": "secondary-vds"+self.vds_id,
                    "volume": self.name+"-cmd0",
                    "id": 99,
                    "backend": "/dev/dsk/"+
                    LDEVBlock.get_cmd_device(devices[self.name+"_OS_01"]),
                    "mpgroup": self.name+"-cmd0" }
                ]
            except KeyError as e:
                self.module.fail_json(msg="Key error on device '"+e.args[0]+
                                      "' when setting up OS disks")
            self.set_vdisks()

    def setup_rac_env_disks(self):
        if not self.module.check_mode:
            self.vdisks = []
            vdisk_id = 10
            for env in self.rac_storage:
                devices = LDEVBlock.hds_scan(env)
                for volname in sorted(devices):
                    device = devices[volname]
                    # primary
                    self.vdisks.append( {
                        "vdisk": volname.lower(),
                        "vds": "primary-vds"+self.vds_id,
                        "volume": volname,
                        "id": vdisk_id,
                        "backend": "/dev/dsk/"+device,
                        "mpgroup": volname+"_"+self.node_id } )
                    # secondary
                    self.vdisks.append( {
                        "vdisk": volname.lower(),
                        "vds": "secondary-vds"+self.vds_id,
                        "volume": volname,
                        "id": vdisk_id,
                        "backend": "/dev/dsk/"+device,
                        "mpgroup": volname+"_"+self.node_id } )
                    vdisk_id += 1
                # set vdisk ID to next multiple of 10 for next env
                vdisk_id = vdisk_id+(10-vdisk_id%10)
            self.set_vdisks()

    def exists(self):
        try:
            self.lxc.list(self.name)
        except:
            return False
        return True

    def is_active(self):
        return self.status() == "active"

    def is_bound(self):
        return self.status() == "bound"

    def is_inactive(self):
        return self.status() == "inactive"

    def status(self):
        if self.exists():
            try:
                ldmcfg = self.lxc.list(self.name)
            except LDMError as e:
                self.msg.append()
                self.module.fail_json(msg = "Unable to get domain status: "+
                                      str(e))
            ldom_info = ldmcfg["ldom_info"]
            return ldom_info["state"]
        else:
            return "unknown"

    def state_active(self):
        if not self.is_active() and not self.module.check_mode:
            try:
                if self.is_inactive():
                    self.lxc.bind(self.name)
                self.lxc.start(self.name)
            except LDMError as e:
                self.module.fail_json(msg = "Unable to activate domain: "+
                                      str(e))
            self.changed = True
            self.msg.append("Domain active")

    def state_bound(self):
        if not self.is_bound() and not self.module.check_mode:
            try:
                if self.is_active():
                    self.lxc.stop(self.name)
                else:
                    self.lxc.bind(self.name)
            except LDMError as e:
                self.module.fail_json(msg = "Unable to bind domain: "+
                                      str(e))
            self.changed = True
            self.msg.append("Domain bound")

    def state_inactive(self):
        if not self.is_inactive() and not self.module.check_mode:
            try:
                if self.is_active():
                    self.lxc.stop(self.name)
                self.lxc.unbind(self.name)
            except LDMError as e:
                self.msg.append()
                self.module.fail_json(msg = "Unable to deactivate domain: "+
                                      str(e))
            self.changed = True
            self.msg.append("Domain inactive")

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name = dict(required = True, type = "str"),
            cpu_arch = dict(default = "migration-class1",
                          choices = ["generic", "native", "migration-class1",
                                     "sparc64-class1"], type = "str"),
            cores = dict(default = None, type = "int"),
            memory = dict(default = None, type = "int"),
            domain_vars = dict(default = None, type = "dict"),
            vdisks = dict(default = None, type = "list"),
            vnets = dict(default = None, type = "list"),
            rac_dbvers = dict(default = None, type = "str"),
            rac_storage = dict(default = None, type = "list"),
            state = dict(default = "same", choices = ["same", "inactive",
                                                      "bound", "active",
                                                      "deleted"],
                         type = "str")
        ),
        supports_check_mode = True
    )

    if platform.system() != "SunOS":
        module.fail_json(msg = "This module requires Solaris")

    if float(platform.version()) < 11.3:
        module.fail_json(msg = "This module requires Solaris 11.3 or higher")

    ldom = LDOM(module)

    state = module.params["state"]
    if state == "deleted":
        ldom.delete()
        module.exit_json(changed = ldom.changed, msg = " | ".join(ldom.msg))
    if not ldom.exists():
        ldom.create()

    if ldom.cores is not None:
        ldom.set_cores()
    if ldom.memory is not None:
        ldom.set_memory()
    if ldom.domain_vars is not None:
        ldom.set_vars()
    if ldom.vdisks is not None:
        ldom.set_vdisks()
    if ldom.vnets is not None:
        ldom.set_vnets()
    if ldom.rac_dbvers is not None and ldom.rac_storage is not None:
        try:
            # run cfgadm on primary and secondary service domains
            subprocess.check_call(["/usr/sbin/cfgadm", "-al"])
            sec_svc = platform.node().replace("pri", "sec")
            subprocess.check_call(["/usr/bin/ssh", sec_svc,
                                   "/usr/sbin/cfgadm -al"])
        except subprocess.CalledProcessError as e:
            module.fail_json(msg = "cfgadm command failed: "+e.output)
        ldom.setup_rac_OS_disks()
        ldom.setup_rac_env_disks()

    if state == "active":
        ldom.state_active()
    elif state == "bound":
        ldom.state_bound()
    elif state == "inactive":
        ldom.state_inactive()

    module.exit_json(changed = ldom.changed, msg = " | ".join(ldom.msg))


from ansible.module_utils.basic import *
if __name__ == "__main__":
    main()

# vim: textwidth=80 formatoptions=cqt wrapmargin=0
