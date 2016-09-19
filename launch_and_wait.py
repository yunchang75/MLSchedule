import glob
from py_euca_wrappers import *

def launch_instances(num_insts, inst_type):
    print 'Starting to launch an instance from an image'

    image = 0
    if glob.LAUNCH_FROM == 'scratch':
        image = glob.BASE_IMAGE
    else:
        image = read_image_id()

    stdout = py_euca_run_instances(image, num_insts, inst_type)
    wait_for_nodes_to_launch()
    ips = check_instance_status('ips', 'running')
    wait_ssh(ips)
    return stdout

def launch_instance_with_metadata(inst_type):
    stdout = launch_instances(1, inst_type)
    out_array = stdout.split('\n')[1].split()
    _ip = out_array[12]
    _id = out_array[1]
    return _ip, _id


def setup_instance(ip):
    cmd = [#Files for both
           'tar -cf scripts.tar.gz ' + glob.PEM_PATH + ' ' + glob.S3CMD_CFG_PATH +
           ' scripts hadoop_xml_files ssh_config'
           ]
    py_cmd_line(cmd[0])

    py_scp_to_remote('', ip, 'scripts.tar.gz', '/home/ubuntu/scripts.tar.gz')
    py_scp_to_remote('', ip, 'scripts/build_dependencies.sh', '/home/ubuntu/build_dependencies.sh')
    py_ssh('', ip, 'source build_dependencies.sh')
    return

def read_image_id():
    file_name = glob.CLOUD + '/' + glob.CLOUD + '_image_id'
    if os.path.isfile(file_name):
        f = open(glob.CLOUD + '/' + glob.CLOUD + '_image_id', 'r')
        image_id = f.read()
        if 'emi' in image_id:
            return image_id.strip()
        else:
            return 0
    else:
        return 0

def check_instance_status(info, inst_status):
    stdout = py_euca_describe_instances()
    ret_vals = []
    stdout_array = stdout.split('\n')

    idx = 0
    if info == 'ids':
        idx = 1
    elif info == 'ips':
        idx = 12
    for line in stdout_array:
        inst_info = line.split()
        if len(inst_info) > 0 and (inst_info[0] == 'INSTANCE') :
            check_bool = True
            if inst_status == 'running':
                check_bool = inst_info[5] == 'running'
            elif inst_status == 'all':
                check_bool = inst_info[5] != 'terminated'

            if check_bool:
                if idx == 12 and len(inst_info[idx].split('.')) == 4:
                    ret_vals.append(inst_info[idx])
                elif idx == 1 and inst_info[idx].split('-')[0] == 'i':
                    ret_vals.append(inst_info[idx])
    return ret_vals

def wait_for_nodes_to_launch():
    while(1):
        sleep(10)
        stdout = py_euca_describe_instances()
        ret_vals = []
        stdout_array = stdout.split('\n')
        flag = 0
        for line in stdout_array:
            inst_info = line.split()
            if len(inst_info) > 0 and (inst_info[0] == 'INSTANCE') and (inst_info[5] == 'pending'):
                print 'Need to wait...the nodes are not running yet'
                flag = 1
        if flag == 1:
            continue
        break
    return

def wait_ssh(ips):
    for ip in ips:
        count = 0
        while(1):
            proc = py_ssh('-o connecttimeout=3', ip,'true 2>/dev/null')
            if proc.returncode == 0:
                break
            count += 1
            if count % 100 == 1:
                print 'Waiting on node', ip
    return
