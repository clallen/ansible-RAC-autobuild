#!/usr/bin/python

import socket, sys
sys.path.append("/home/clallen/work/autobuild/ansible_modules")
from ldevblock import LDEVBlock

HORCM_CONF_TEMPLATE = "HORCM_MON\n#ip_address\tservice poll(10ms)\ttimeout(10ms)\n{}\t\t{}\t1000\t\t3000\n\nHORCM_CMD\n\\\\.\\CMD-{}:/dev/rdsk/*\n\nHORCM_LDEV\n#dev_group\tdev_name\tSerial#\tCU:LDEV(LDEV#)\tMU#\n{}\n\nHORCM_INST\n#dev_group\tip_address\tservice\n{}\n"
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

    serial = str(LDEVBlock.get_serial(horcminst))
    ldev_lines = []
    inst_lines = []
    for disk_group in disk_groups:
        ldevs = LDEVBlock.hds_scan(disk_group, "ldev")
        for ldev_name in ldevs.iterkeys():
            ldev_lines.append(disk_group+"\t"+ldev_name+"\t"+serial+"\t"+ldevs[ldev_name]+"\t0")
        inst_lines.append(disk_group+"\t"+SI_HOST+"\t"+horcminst)
    # template field order:
    # hostname
    # horcminst
    # serial
    # ldev_lines
    # inst_lines
    horcm_conf_lines = HORCM_CONF_TEMPLATE.format(socket.gethostname().split(".")[0], horcminst, serial, "\n".join(ldev_lines), "\n".join(inst_lines))

    # write out the file
    horcm_conf_file = "/etc/"+horcminst+".conf"
    try:
        fh = open(horcm_conf_file, "w+")
    except IOError as e:
        module.fail_json(msg = "Error opening "+horcm_conf_file+": "+e.strerror)
    fh.write(horcm_conf_lines)
    fh.close()

    module.exit_json(changed = changed, msg = msg)

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
