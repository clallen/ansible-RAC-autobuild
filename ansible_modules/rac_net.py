#!/usr/bin/python

import subprocess, time, platform, socket, re

NET_13_GW = "130.164.13.1"
NET_13_MASK = "24"
NET_51_LOOKUP = [ { "range": range(2, 63), "gw": "130.164.51.1", "mask": "26" },
                  { "range": range(66, 127), "gw": "130.164.51.65", "mask": "26" },
                  { "range": range(130, 159), "gw": "130.164.51.129", "mask": "27" },
                  { "range": range(162, 191), "gw": "130.164.51.161", "mask": "27" },
                  { "range": range(194, 255), "gw": "130.164.51.193", "mask": "27" } ]
PRIV_MASK = "24"
LINKNAME_MAP = [ ("net1", "publink0"), ("net2", "publink1"),
                 ("net3", "privlink0"), ("net4", "privlink1") ]
IPMP_MAP = [ { "pubnet0": ("publink0", "publink1") },
             { "privnet0": ("privlink0", "privlink1") } ]

def main():
    module = AnsibleModule(argument_spec = dict(), supports_check_mode = True)

    changed = False
    msg = []

    if module.check_mode:
        self.msg.append('RUNNING IN CHECK MODE - NO CHANGES WILL BE MADE')

    pub_hostname = platform.node().replace("-mgmt", "")
    priv_hostname = platform.node().replace("-mgmt", "-priv1")

    # do DNS lookups
    try:
        pub_IP = socket.gethostbyname(pub_hostname)
    except socket.gaierror as e:
        module.fail_json(msg = "Error resolving public hostname "+pub_hostname+": "+e.strerror)
    try:
        priv_IP = socket.gethostbyname(priv_hostname)
    except socket.gaierror as e:
        module.fail_json(msg = "Error resolving private hostname "+priv_hostname+": "+e.strerror)
    # check net range/get public gateway and mask
    if re.match(r"130.164.13.", pub_IP) is not None:
        pub_gw = NET_13_GW
        pub_mask = NET_13_MASK
    elif re.match(r"130.164.51.", pub_IP) is not None:
        for net in NET_51_LOOKUP.iterkeys():
            if pub_IP in net["range"]:
                pub_gw = net["gw"]
                pub_mask = net["mask"]
                break
    else:
        module.fail_json(msg = "Public IP "+pub_IP+" is not in a valid range")

    # get current links
    try:
        cur_links = subprocess.check_output(["/usr/sbin/dladm", "show-link", "-po", "LINK"]).split()
    except subprocess.CalledProcessError as e:
        module.fail_json(msg = "Error querying links: "+e.output)
    # rename if necessary
    for names in LINKNAME_MAP:
        if names[1] not in cur_links:
            msg.append("Renaming link "+names[0]+" to "+names[1])
            if not module.check_mode:
                try:
                    subprocess.check_call(["/usr/sbin/dladm", "rename-link", names[0], names[1]])
                except subprocess.CalledProcessError as e:
                    module.fail_json(msg = "Error renaming link "+names[0]+" to "+names[1]+": "+e.output)
                else:
                    changed = True

    # create link IPs
    for names in LINKNAME_MAP:
        try:
            linkstate = subprocess.check_output(["/usr/sbin/dladm", "show-linkprop", "-co", "VALUE", "-p", "state", names[1]])
        except subprocess.CalledProcessError as e:
            module.fail_json(msg = "Error querying link "+names[1]+": "+e.output)
        if linkstate != "up":
            msg.append("Creating IP on link "+names[1])
            if not module.check_mode:
                try:
                    subprocess.check_call("/usr/sbin/ipadm", "create-ip", names[1])
                except subprocess.CalledProcessError as e:
                    module.fail_json(msg = "Error creating IP on link "+names[1]+": "+e.output)
                else:
                    changed = True

    # create IPMP interfaces
    for ipmp in IPMP_MAP:
        try:
            ifaces = subprocess.check_output(["/usr/sbin/ipadm", "show-if", "-po", "IFNAME"]).split()
        except subprocess.CalledProcessError as e:
            module.fail_json(msg = "Error querying interfaces: "+e.output)
        ifname = ipmp.keys()[0]
        if ifname not in ifaces:
            msg.append("Building IPMP interface "+ifname)
            if not module.check_mode:
                try:
                    links = ipmp[ifname]
                    subprocess.check_call(["/usr/sbin/ipadm", "create-ipmp", "-i", ",".join(links), ifname])
                    time.sleep(5)
                except subprocess.CalledProcessError as e:
                    module.fail_json(msg = "Error building IPMP interface "+ifname+": "+e.output)

    # create IP addresses
    try:
        ifstate = subprocess.check_output(["/usr/sbin/ipadm", "show-if", "-po", "STATE", "pubnet0"])
    except subprocess.CalledProcessError as e:
        module.fail_json(msg = "Error querying interface pubnet0: "+e.output)
    if ifstate != "ok":
        msg.append("Creating IP address on interface pubnet0")
        if not module.check_mode:
            try:
                subprocess.check_call(["/usr/sbin/ipadm", "create-addr", "-T", "static", "-a", "local="+pub_IP+"/"+pub_mask, "pubnet0"])
            except subprocess.CalledProcessError as e:
                module.fail_json(msg = "Error creating IP address on interface pubnet0: "+e.output)
    try:
        ifstate = subprocess.check_output(["/usr/sbin/ipadm", "show-if", "-po", "STATE", "pubnet0"])
    except subprocess.CalledProcessError as e:
        module.fail_json(msg = "Error querying interface pubnet0: "+e.output)
    if ifstate != "ok":
        msg.append("Creating IP address on interface privnet0")
        if not module.check_mode:
            try:
                subprocess.check_call(["/usr/sbin/ipadm", "create-addr", "-T", "static", "-a", "local="+priv_IP+"/"+PRIV_MASK, "privnet0"])
            except subprocess.CalledProcessError as e:
                module.fail_json(msg = "Error creating IP address on interface privnet0: "+e.output)

    # replace default route with public
    try:
        output = subprocess.check_output(["/usr/sbin/route", "-p", "show"]).split()
        cur_gw = output[len(output)-1]
    except subprocess.CalledProcessError as e:
        module.fail_json(msg = "Error querying default route: "+e.output)
    if cur_gw != pub_gw:
        msg.append("Setting default route to "+pub_gw)
        if not module.check_mode:
            try:
                subprocess.check_call(["/usr/sbin/route", "-p", "add", "default", pub_gw])
                subprocess.check_call(["/usr/sbin/route", "-p", "delete", "default", cur_gw])
            except subprocess.CalledProcessError as e:
                module.fail_json(msg = "Error setting default route: "+e.output)

    # set IPMP transitive probing
    try:
        probe_state = subprocess.check_output(["/usr/sbin/svcprop", "-p", "config/transitive-probing", "ipmp"])
    except subprocess.CalledProcessError as e:
        module.fail_json(msg = "Error querying IPMP transitive probing: "+e.output)
    if probe_state == "false":
        msg.append("Setting IPMP transitive probing")
        if not module.check_mode:
            try:
                subprocess.check_call(["/usr/sbin/svccfg", "-s", "ipmp", "setprop", "config/transitive-probing", "=", "boolean:", "true"])
                subprocess.check_call(["/usr/sbin/svcadm", "restart", "ipmp"])
            except subprocess.CalledProcessError as e:
                module.fail_json(msg = "Error setting IPMP transitive probing: "+e.output)

    module.exit_json(changed = changed, msg = " | ".join(msg))


from ansible.module_utils.basic import *
if __name__ == "__main__":
    main()
