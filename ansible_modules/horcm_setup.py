#!/usr/bin/python

import socket, sys
sys.path.append("/home/clallen/work/autobuild/ansible_modules")
from ldevblock import LDEVBlock

MON_COLUMNS_FORMAT = "{:15}{:10}{:15}{}"
LDEV_COLUMNS_FORMAT = "{:30}{:30}{:10}{:18}{}"
INST_COLUMNS_FORMAT = "{:30}{:15}{}"
HORCM_CONF_TEMPLATE = ("HORCM_MON\n"+
                      MON_COLUMNS_FORMAT+"\n"+
                      MON_COLUMNS_FORMAT+"\n\n"
                      "HORCM_CMD\n"
                      "#dev name\n"
                      "\\\\.\\CMD-{}:/dev/rdsk/*\n\n"
                      "HORCM_LDEV\n"+
                      LDEV_COLUMNS_FORMAT+"\n"
                      "{}\n\n"
                      "HORCM_INST\n"+
                      INST_COLUMNS_FORMAT+"\n"
                      "{}\n")
SI_HOST = "boxmgr"

def main():
    module = AnsibleModule(
        argument_spec = dict(
            horcminst = dict(required = True, type = "str"),
            disk_groups = dict(required = True, type = "list")
        ),
        supports_check_mode = True
    )

    changed = False
    msg = []

    horcminst = module.params["horcminst"]
    disk_groups = module.params["disk_groups"]

    # add service instance
    rc, stdout, stderr = module.run_command("/usr/sbin/svccfg -s site/horcm:"+horcminst+" list")
    if stdout.strip() != ":properties":
        msg.append("Adding "+horcminst+" service instance")
        if not module.check_mode:
            module.run_command("/usr/sbin/svccfg -s site/horcm add "+horcminst, check_rc = True)
            changed = True
    # add property groups
    rc, stdout, stderr = module.run_command("/usr/sbin/svccfg -s site/horcm:"+horcminst+" listpg")
    if stdout.strip() == "":
        msg.append("Adding "+horcminst+" property groups")
        if not module.check_mode:
            module.run_command("/usr/sbin/svccfg -s site/horcm:"+horcminst+" addpg general framework", check_rc = True)
            changed = True
    # add general/enabled property value
    rc, stdout, stderr = module.run_command("/usr/sbin/svccfg -s site/horcm:"+horcminst+" listprop general/enabled")
    if stdout.strip() == "":
        msg.append("Adding "+horcminst+" general/enabled property value")
        if not module.check_mode:
            module.run_command("/usr/sbin/svccfg -s site/horcm:"+horcminst+" addpropvalue general/enabled boolean: false", check_rc = True)
            changed = True

    # populate template
    msg.append("Building HORCM config")
    serial = str(LDEVBlock.get_serial(horcminst))
    ldev_lines = []
    inst_lines = []
    for disk_group in disk_groups:
        ldevs = LDEVBlock.hds_scan(disk_group, "ldev")
        for ldev_name in ldevs.iterkeys():
            ldev_lines.append(LDEV_COLUMNS_FORMAT.format(disk_group, ldev_name, serial, ldevs[ldev_name], "0"))
        inst_lines.append(INST_COLUMNS_FORMAT.format(disk_group, SI_HOST, horcminst))
    horcm_conf_lines = HORCM_CONF_TEMPLATE.format("#ip_address", "service", "poll(10ms)", "timeout(10ms)",
                                                  socket.gethostname().split(".")[0], horcminst, "1000", "3000",
                                                  serial,
                                                  "#dev_group", "dev_name", "Serial#", "CU:LDEV(LDEV#)", "MU#",
                                                  "\n".join(ldev_lines),
                                                  "#dev_group", "ip_address", "service",
                                                  "\n".join(inst_lines))

    # write out the file
    horcm_conf_file = "/etc/"+horcminst+".conf"
    if os.path.isfile(horcm_conf_file):
        msg.append("HORCM config file "+horcm_conf_file+" exists, not overwriting")
    else:
        msg.append("Writing HORCM config to "+horcm_conf_file)
        if not module.check_mode:
            try:
                fh = open(horcm_conf_file, "w+")
            except IOError as e:
                module.fail_json(msg = "Error opening "+horcm_conf_file+": "+e.strerror)
            fh.write(horcm_conf_lines)
            fh.close()
            changed = True

    module.exit_json(changed = changed, msg = msg)

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
