#!/usr/bin/python

import subprocess

def _run_cmd(cmd, module):
    try:
        return subprocess.check_output(cmd, shell = True).strip()
    except subprocess.CalledProcessError as e:
        module.fail_json(msg = "Command '"+e.cmd+"' failed: "+e.output)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            types = dict(required = True, type = "list")
        ),
        supports_check_mode = True
    )

    data = { "ansible_facts": {} }

    if "repos" in module.params["types"]:
        # get current repos
        data["ansible_facts"]["current_solaris_repo"] = _run_cmd("/bin/pkg publisher solaris | /bin/grep Origin | /bin/awk '{print $3}'", module)
        data["ansible_facts"]["current_site_repo"] = _run_cmd("/bin/pkg publisher site | /bin/grep Origin | /bin/awk '{print $3}'", module)

    module.exit_json(**data)


from ansible.module_utils.basic import *
if __name__ == '__main__':
        main()

# vim: textwidth=80 formatoptions=cqt wrapmargin=0
