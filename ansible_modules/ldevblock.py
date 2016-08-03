#!/usr/bin/python

import re, platform, subprocess

DOCUMENTATION = """
---
module: ldevblock
short_description: Create and allocate a block of LDEVs
description:
    - Create and allocate a block of LDEVs.  The block will be shared to
      specified chassis.
author: Clint Allen
requirements:
    - Solaris 10 or higher
    - raidcom
options:
    horcm:
        required: true
        type: C{str}
        description:
            - HORCM instance to use.
    blocks:
        required: true
        type: C{list} of C{dict}
        description:
            - Each dictionary in the list must contain these entries:
            - name: Block base name.  Used to name the LDEVs in the block.  
              Incremental IDs will be added to each LDEV name (e.g.
              given a base name of "MYNAME", will create LDEVs named
              "MYNAME_01", "MYNAME_02", etc).
            - size: Size of each LDEV in the block.  Must be specified in GB.
            - begin: Beginning index of the block.  This is the index of the first
              LDEV (e.g. "15:60").
            - end: Ending index of the block.  This is the index of the last
              LDEV (e.g. "15:6F").
            - ports: List of ports to share through (e.g. CL1-B, CL2-B, CL7-F, CL8-F).
            - pool: Storage pool in which the block will be created.
            - chassis: List of chassis to share to.
"""


class LDEVBlock:
    RAIDCOM = "/HORCM/usr/bin/raidcom"
    TIERED = [ 15, 16 ]
    GS5_SERIAL = 66673
    GS6_SERIAL = 93133
    GS7_SERIAL = 12345
    GS5_CMD_DEV = "c0t60060E801604710000010471000025FFd0s2"
    GS6_CMD_DEV = "c0t60060E80166BCD0000016BCD000026FFd0s2"
    GS7_CMD_DEV = "c0t60060E8016--bogus--a6FFd0s2"

    def __init__(self, module, name, begin, end, size, ports, pool, chassis):
        self.module = module
        self.horcm = self.module.params["horcm"]
        self.chassis = chassis
        self.pool = pool
        self.ports = ports
        self.name = name
        self.size = size
        self.begin = begin
        self.end = end
        self.lock_cmd = "lock resource -resource_name meta_resource -time 60 -I"+self.horcm
        self.unlock_cmd = "unlock resource -resource_name meta_resource -I"+self.horcm

        self.ldevs = []
        self.msg = []
        self.changed = False

        # populate LDEV list
        cu = self.begin[0:2].upper()
        dec_begin_idx = int(self.begin[3:5], 16)
        dec_end_idx = int(self.end[3:5], 16)
        for dec_idx in xrange(dec_begin_idx, dec_end_idx+1):
            if len(format(dec_idx, "X")) < 2:
                idx = "0"+format(dec_idx, "X")
            else:
                idx = format(dec_idx, "X")
            ldev_id = cu+":"+idx
            self.ldevs.append(ldev_id)

        if self.module.check_mode:
            self.msg.append('RUNNING IN CHECK MODE - NO CHANGES WILL BE MADE')

    def create(self):
        name_idx = 1
        cmd_list = []
        cmd_list.append(self.lock_cmd)
        for ldev_id in self.ldevs:
            # create
            if self._ldev_exists(ldev_id):
                self.msg.append("LDEV "+ldev_id+" already exists, skipping")
                name_idx += 1
                continue
            cmd_list.append("reset command_status -I"+self.horcm)
            cmd_list.append("add ldev -pool "+str(self.pool)+" -ldev_id "+ldev_id+
                            " -capacity "+self.size+"g -I"+self.horcm)
            cmd_list.append("get command_status -I"+self.horcm)
            # rename
            if name_idx > 9:
                display_name_idx = str(name_idx)
            else:
                display_name_idx = "0"+str(name_idx)
            name_idx += 1
            cmd_list.append("modify ldev -ldev_id "+ldev_id+" -ldev_name "+self.name+"_"+
                            display_name_idx+" -I"+self.horcm)
            # set LDEV to not use prod tier storage
            if self.pool in self.TIERED:
                cmd_list.append("modify ldev -ldev_id "+ldev_id+" -status enable_reallocation 5 -I"+
                                self.horcm)
        cmd_list.append(self.unlock_cmd)
        # only run commands if there are more than just lock and unlock
        if len(cmd_list) > 2:
            self._run_cmd_list(cmd_list)
            self.changed = True

    def share(self):
        cmd_list = []
        cmd_list.append(self.lock_cmd)
        for ldev_id in self.ldevs:
            if len(self._get_shared_hosts(ldev_id)) != 0:
                self.msg.append("LDEV "+ldev_id+" is already shared, skipping")
                continue
            for port in self.ports:
                for chassis in self.chassis:
                    cmd_list.append("add lun -port "+port+" "+chassis+"-pri -ldev_id "+
                                    ldev_id+" -I"+self.horcm)
                    cmd_list.append("add lun -port "+port+" "+chassis+"-sec -ldev_id "+
                                    ldev_id+" -I"+self.horcm)
        cmd_list.append(self.unlock_cmd)
        if len(cmd_list) > 2:
            self._run_cmd_list(cmd_list)
            self.changed = True

    @staticmethod
    def get_serial(horcminst):
        """ Return the decimal serial number of the storage frame for the given
        HORCM instance """
        if horcminst == "horcm5":
            return LDEVBlock.GS5_SERIAL
        if horcminst == "horcm6":
            return LDEVBlock.GS6_SERIAL
        if horcminst == "horcm7":
            return LDEVBlock.GS7_SERIAL

    @staticmethod
    def get_cmd_device(device):
        """ Return the command device for the storage frame for the given device
        node string. """
        if re.search(format(LDEVBlock.GS5_SERIAL, "X"), device) is not None:
            return LDEVBlock.GS5_CMD_DEV
        if re.search(format(LDEVBlock.GS6_SERIAL, "X"), device) is not None:
            return LDEVBlock.GS6_CMD_DEV
        if re.search(format(LDEVBlock.GS7_SERIAL, "X"), device) is not None:
            return LDEVBlock.GS7_CMD_DEV

    @staticmethod
    def hds_scan(blockname, return_type):
        """ Returns a dictionary of LDEV names mapped to device ids, or mapped 
        to LDEV ids, depending on C{return_type}.
        args:
        - blockname: the LDEV name pattern to search
        - return_type: if "device", return device node names, if "ldev" return LDEV ids
        
        Return type "devices": { "ldevname1": "c0t60060E80166BCD0000016BCD00006DE0d0s2" }
        Return type "ldev": { "ldevname1": "15:6C" }
        """
        try:
            lines = subprocess.check_output("/usr/bin/ls /dev/rdsk/* | "+
                                            "/HORCM/usr/bin/inqraid -fnx -CLI | "+
                                            "/usr/bin/grep "+blockname, shell = True)
        except subprocess.CalledProcessError as e:
            module.fail_json(msg = "Unable to scan for backend devices: "+
                             e.output)
        result = dict()
        if return_type == "device":
            for line in lines.splitlines():
                columns = line.split()
                device = columns[0].strip()
                name = columns[8].strip()
                result[name] = device
        elif return_type == "ldev":
            for line in lines.splitlines():
                columns = line.split()
                tmp = columns[3].strip()
                ldev = tmp[:2]+":"+tmp[2:]
                name = columns[8].strip()
                result[name] = ldev
        return result

    def _ldev_exists(self, ldev):
        output = self._run_cmd("get ldev -ldev_id "+ldev+" -I"+self.horcm)
        if re.search(r"NOT DEFINED", output) is None:
            return True
        else:
            return False

    def _get_shared_hosts(self, ldev_id):
        hosts = []
        output = self._run_cmd("get ldev -ldev_id "+ldev_id+" -I"+self.horcm)
        for line in output.splitlines():
            if re.match(r"^PORTs", line):
                portline = line.split(":")
                portline.pop(0)
                if len(portline) > 1:
                    for glob in portline:
                        port = glob.split()[0]
                        host = glob.split()[2]
                        if not host in hosts:
                            hosts.append({ "port": port, "host": host })
                break
        return hosts

    def _run_cmd_list(self, cmd_list):
        self.msg.append("raidcom commands: ")
        for cmd in cmd_list:
            if self.module.check_mode:
                self.msg.append(self.RAIDCOM+" "+cmd)
            else:
                output = self._run_cmd(cmd)
                self.msg.append(cmd)
                if len(output) != 0:
                    self.msg.append(output)

    def _run_cmd(self, cmd):
        stdout = self.module.run_command(self.RAIDCOM+" "+cmd, check_rc = True)[1]
        return stdout.strip()

def main():
    module = AnsibleModule(
        argument_spec = dict(
            horcm = dict(required = True, type = "str"),
            blocks = dict(type = "list")
        ),
        supports_check_mode = True
    )

    if platform.system() != "SunOS":
        module.fail_json(msg = "This module requires Solaris")

    if float(platform.version()) < 10:
        module.fail_json(msg = "This module requires Solaris 10 or higher")

    exit_msg = []

    for block in module.params["blocks"]:
        ldb = LDEVBlock(module, block["name"], block["begin"], block["end"],
                        block["size"], block["ports"], block["pool"], block["chassis"])
        ldb.create()
        ldb.share()
        exit_msg.extend(ldb.msg)

    module.exit_json(changed = ldb.changed, msg = " | ".join(exit_msg))


from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
