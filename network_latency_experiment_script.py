import os
import sys
from subprocess import Popen, PIPE
from time import sleep, gmtime, strftime

#INCLUDE FILES
import data_partition
import image_funcs

def time_str():
    return strftime("-%Y-%m-%d-%H-%M-%S", gmtime())

def read_instance_types():
    stdout = py_euca_describe_instance_types()
    stdout_array = stdout.split('\n')
    instance_types = []
    for line in stdout_array[1:]:
        line_array = line.split()
        if len(line_array) > 0:
            instance_types.append((line_array[1], int(line_array[2]), int(line_array[3]), int(line_array[4])))
    return instance_types

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

        check_bool = True
        if inst_status == 'running':
            check_bool = inst_info[5] == 'running'
        elif inst_status == 'all':
            check_bool = inst_info[5] != 'terminated'

        if len(inst_info) > 0 and (inst_info[0] == 'INSTANCE') and check_bool:
            ret_vals.append(inst_info[idx])
    return ret_vals

#WAITS


def wait_for_nodes_to_launch():
    while(1):
        sleep(10)
        stdout = py_euca_describe_instances()
        ret_vals = []
        stdout_array = stdout.split('\n')
        flag = 0
        for line in stdout_array:
            instance_info = line.split()
            if len(instance_info) > 0 and (instance_info[0] == 'INSTANCE') and (instance_info[5] == 'pending'):
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



#LAUNCHES


def launch_instances(num_insts, inst_type, inst_role):
    print 'Starting to launch an instance from an image'

    image = read_image_id(inst_role)

    if image == 0:
        sys.exit('ERROR: Cannot find image.')

    stdout = py_euca_run_instances(image, num_insts, inst_type)
    wait_for_nodes_to_launch()
    ips = check_instance_status('ips', 'running')
    wait_ssh(ips)
    return stdout


def launch_instance_with_metadata(inst_type, inst_role):
    stdout = launch_instances(1, inst_type, inst_role)
    out_array = stdout.split('\n')[1].split()
    _ip = out_array[12]
    _id = out_array[1]
    return _ip, _id


def create_hostfiles(ips, new_ips):
    print 'Creating Hostfiles...'
    f1 = open('./hostfile', 'w')
    for ip in ips:
        f1.write(ip + '\n')
    f1.close()
    f2 = open('./new_hostfile', 'w')
    for ip in new_ips:
        f2.write(ip + '\n')
    f2.close()
    f3 = open('./hostfile_petuum_format', 'w')

    for (j, ip) in enumerate(ips):
        if j != len(ips) - 1:
            f3.write(str(j) + ' ' + ip + ' 9999\n')
    if len(ips) > 0:
        f3.write(str(len(ips) - 1) + ' ' + ips[-1] + ' 9999')
    f3.close()



def setup_instance(ip, inst_role):
    print 'Starting to setup ' + inst_role + '...'
    py_wait_proc('source ' + inst_role + '_setup_script.sh ' + ip)
    return


def replace_hostfiles(master_ip):
    print 'Replacing Hostfiles...'
    py_wait_proc('source replace_hostfiles.sh ' + master_ip)
    return


def passwordless_ssh(master_ip):
    print 'Moving Hostfile to Master...'
    py_scp_to_remote('', master_ip, 'hostfile', REMOTE_PATH + '/hostfile')
    print 'Moving New Hostfile to Master...'
    py_scp_to_remote('', master_ip, 'new_hostfile', REMOTE_PATH + '/new_hostfile')
    print 'Setting up Passwordless SSH...'
    py_ssh('', master_ip, 'source ' + REMOTE_PATH + '/add_public_key_script.sh')
    print 'Finished Passwordless SSH'
    return


def add_ssh_key_to_master(master_ip):
    py_ssh('', master_ip, 'source ' + REMOTE_PATH + '/create_ssh_keygen.sh')
    return


def push_launch_script_to_master(master_ip):
    py_scp_to_remote('', master_ip, 'launch.py', REMOTE_PATH + '/bosen/app/mlr/script/launch.py')
    return


def clean_master_known_hosts(master_ip):
    py_ssh('', master_ip, 'sudo echo -n > /home/ubuntu/.ssh/known_hosts') 
    return


def terminate_instances(inst_ids, inst_ips):
    print "Terminating Instances...Hasta la vista baby!"
    f1 = open('/Users/Kevin/.ssh/known_hosts', 'r')
    known_host_lines = f1.readlines()
    f2 = open('temp_known_hosts', 'w')
    for line in known_host_lines:
        flag = 0
        for ip in instance_ips:
            if ip in line:
                flag = 1
        if flag == 0:
            f2.write(line)

    py_cmd_line('cp temp_known_hosts /Users/Kevin/.ssh/known_hosts')

    for inst_id in inst_ids:
        py_euca_terminate_instances(inst_id)







def launch_machine_learning_job(master_ip, argvs, remote_file_name):
    py_ssh('', master_ip, 'python ' + REMOTE_PATH + '/bosen/app/mlr/script/launch.py ' + argvs + ' &> ' + file_name)
    return


def wait_for_file_to_write(master_ip, remote_file_name, local_file_path):
    while(1):
        sleep(20)
        local_file_path = local_file_dir + '/' + file_root
        proc = py_scp_to_local('', master_ip, remote_file_name, local_file_path)
        stdout = py_out_proc('cat ' + local_file_path)
        if 'MLR finished and shut down!' in stdout:
            break
    return


def run_ml_task(master_ip, inst_type, inst_count, epochs, cores, staleness, run, local_file_dir):

    inst_str = list(map(lambda x: str(x), inst_type))
    inst_str.append('machines')
    inst_str.append(str(inst_count))
    inst_string.append('run')
    inst_string.append(str(run))
    file_root = '_'.join(inst_str)
    remote_file_name = REMOTE_PATH + '/' + file_root
    argvs = ' '.join(epochs, cores, staleness)

    launch_machine_learning_job(master_ip, argvs, remote_file_name)
    wait_for_file_to_write(master_ip, remote_file_name, local_file_dir + '/' + file_root)
    return


def run_experiment(master_inst_type, mach_array, data_set_name, runs):

    #CONSTANTS
    epochs = str(40)
    cores = str(instance_type[1])
    staleness = str(3)

    sys.exit("END SCRIPT")

    #Use this to only build the images
    force_uncache(master_inst_type)
    #sys.exit("END SCRIPT")

    master_ip, master_id = launch_instance_with_metadata(master_inst_type, 'master')
    add_ssh_key_to_master(master_ip)
    push_launch_script_to_master(master_ip)

    local_file_dir = 'experiment_data/' + data_set_name + time_str()
    py_cmd('mkdir ' + local_file_dir)

    inst_types = read_instance_types()
    for inst_type in inst_types:
        py_cmd('mkdir ' + local_file_dir + '/' + inst_type[0])
        for i in mach_array:
            old_ips = check_instance_status('ips', 'running')
            launch_instances(i, instance_type[0], 'worker')
            ips = check_instance_status('ips', 'running')
            if len(ips) == len(old_ips):
                break
            ips.remove(master_ip)
            new_ips = filter(lambda x: x not in old_ips, ips)

            create_hostfiles(ips, new_ips)
            passwordless_ssh(master_ip)
            replace_hostfiles(master_ip)
            for j in range(runs):
                run_ml_task(master_ip, inst_type, len(ips), epochs, cores, staleness, j, local_file_dir)

        inst_ids = read_all_instances('ids')
        inst_ips = read_all_instances('ips')
        inst_ids.remove(master_id)
        inst_ips.remove(master_ip)
        terminate_instances(inst_ids, inst_ips)
        clean_master_known_hosts(master_ip)


#EXCLUDE PARTICULAR INSTANCES HERE
EXCLUDED_INSTANCE_TYPES = []


#RUN IT HERE!!
#Start with Clean Slate
inst_ids = read_all_instances('ids')
inst_ips = read_all_instances('ips')
terminate_instances(inst_ids, inst_ips)


set_globals()
run_experiment('m3.2xlarge', [1,1,2,4,8,16], 'mnist8m', 40)


