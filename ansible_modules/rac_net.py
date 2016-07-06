#!/usr/bin/python

import subprocess, time, platform

def main():
    module = AnsibleModule(argument_spec = dict(), supports_check_mode = True)

    changed = False
    msg = []

    pub_hostname = platform.node().replace("-mgmt", "")

    # setup networking
    msg.append("Renaming links")
    if not module.check_mode:
        try:
            subprocess.check_call("/usr/sbin/dladm", "rename-link", "net1", "publink0")
            subprocess.check_call("/usr/sbin/dladm", "rename-link", "net2", "publink1")
            subprocess.check_call("/usr/sbin/dladm", "rename-link", "net3", "privlink0")
            subprocess.check_call("/usr/sbin/dladm", "rename-link", "net4", "privlink1")
        except subprocess.CalledProcessError as e:
            module.fail_json(msg = "Error renaming link: "+e.output)
        else:
            changed = True
    msg.append("Creating IPs")
    if not module.check_mode:
        try:
            subprocess.check_call("/usr/sbin/ipadm", "create-ip", "publink0")
            subprocess.check_call("/usr/sbin/ipadm", "create-ip", "publink1")
            subprocess.check_call("/usr/sbin/ipadm", "create-ip", "privlink0")
            subprocess.check_call("/usr/sbin/ipadm", "create-ip", "privlink1")
        except subprocess.CalledProcessError as e:
            module.fail_json(msg = "Error creating IP: "+e.output)
        else:
            changed = True
    msg.append("Building IPMP interfaces")
    if not module.check_mode:
        try:
            subprocess.check_call("/usr/sbin/ipadm", "create-ipmp", "-i", "publink0,publink1", "pubnet0")
            time.sleep(5)
            subprocess.check_call("/usr/sbin/ipadm", "create-ipmp", "-i", "privlink0,privlink1", "privnet0")
            time.sleep(5)
            subprocess.check_call("/usr/sbin/ipadm", "create-addr", "-T", "static", "-a", "local="+pub_IP+"/"+pub_mask, "pubnet0")
            subprocess.check_call("/usr/sbin/ipadm", "create-addr", "-T", "static", "-a", "local="+priv_IP+"/"+priv_mask, "privnet0")
        except subprocess.CalledProcessError as e:
            module.fail_json(msg = "Error Building IPMP interfaces: "+e.output)
        else:
            changed = True

    module.exit_json(changed = changed, msg = " | ".join(msg))


from ansible.module_utils.basic import *
if __name__ == "__main__":
    main()
