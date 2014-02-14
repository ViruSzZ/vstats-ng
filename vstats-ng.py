#!/usr/bin/env python2
#
# name: vstats-ng
# author: d@stavrovski.net
#
import os, sys

# path to vz stuff
user_beans  = "/proc/user_beancounters"
vzlist_bin  = "/usr/sbin/vzlist"
vz_confdir  = "/etc/vz/conf/"

####################### MAIN #######################
def main(argv):
    preChecks()
    if len(argv) == 1:
        vmid = fetchVmID(argv[0])
    else:
        vmid = None
    vs = parseVMStuff(vzlist_bin,vmid)
    printResults(vs)
##################### END MAIN #####################


###################### METHODS #####################
def preChecks():
    # check if we're on openvz
    if not os.path.isfile(user_beans):
        print "ERROR: I'm supposed to run on a Virtuozzo/OpenVZ host!"
        sys.exit(1)

    # is vzlist executable?
    is_executable = os.path.isfile(vzlist_bin) and os.access(vzlist_bin, os.X_OK)
    if not is_executable:
        print "ERROR: %r is not a file or did not have executable bit on it." % vzlist_bin
        sys.exit(1)

    # is vz conf dir present?
    if not os.path.isdir(vz_confdir):
        print "ERROR: %r does not exist or is not a directory." % vz_confdir
        sys.exit(1)

def fetchVmID(pattern):
    # pattern is actually a running VMID?
    if os.path.isdir('/proc/bc/'+pattern):
        return pattern

    import subprocess
    try:
        grep_raw = subprocess.Popen( 'grep -iolw ' + pattern + ' ' + vz_confdir + '*.conf', stdout=subprocess.PIPE, shell=True ).communicate()[0]
    except OSError:
        pass
    # no match found
    if not grep_raw:
        print "ERROR: No matching VMID has been found for %r" % pattern
        sys.exit(1)

    query = os.path.splitext(grep_raw)[0].split("\n")
    # more than one match?
    if len(query) > 1:
        vmids = []
        for veid in query:
            #if isinstance( veid, int ):
            if os.path.isdir( '/proc/bc/' + os.path.basename(os.path.splitext(veid)[0]) ):
                vmids.append( os.path.basename(os.path.splitext(veid)[0]) )
        return vmids

    vmid = os.path.basename( os.path.splitext(grep_raw)[0] )
    # check if /proc/bc/$VMID exist
    if not os.path.isdir('/proc/bc/'+vmid):
        print "ERROR: Matched VMID %r doesn't seem like it's running! try `vzlist -a -t %s`" % (vmid, vmid)
        sys.exit(1)

    return vmid

def parseVMStuff(vzlist,vmid):
    import subprocess
    import re

    # load up output of vzlist
    try:
        vz_fields = 'laverage,ip,veid,hostname,cpus,numproc,diskspace,physpages,ostemplate'
        if not vmid:
            vz_input  = subprocess.Popen( [vzlist, '-H', '-o', vz_fields], stdout=subprocess.PIPE ).communicate()[0]
        else:
            # process if multiple vmid's
            if isinstance(vmid, list):
                vmid = " ".join(vmid)
            vz_input = subprocess.Popen( vzlist + ' -H ' + vmid + ' -o ' + vz_fields, stdout=subprocess.PIPE, shell=True ).communicate()[0]
    except OSError:
        pass

    vz = [ line.split() for line in vz_input.split("\n") ]

    # no running containers
    if len(vz) <= 1:
        sys.exit(1)

    vs = {}

    # load-up our goodies
    for i in range( 0, len(vz) - 1, 1 ):

        # unexpeted input as vmid?
        if not os.path.isdir('/proc/bc/' + vz[i][2]):
            break

        # get mem-free
        vm_ram = open('/proc/bc/' + vz[i][2] + '/meminfo', 'r')
        for l, line in enumerate(vm_ram):
            # only second line
            if l == 1:
                ram_free = int(line.split()[1]) / 1024
            elif l > 1:
                break
        vm_ram.close()

        # determine if da, cpanel or webmin is used
        webmin  = '/vz/private/' + vz[i][2] + '/usr/libexec/webmin/miniserv.pl'
        cpanel  = '/vz/private/' + vz[i][2] + '/usr/local/cpanel/cpanel'
        da      = '/vz/private/' + vz[i][2] + '/usr/local/directadmin/directadmin'
        if os.path.isfile(webmin):
            panel = 'Webmin'
        elif os.path.isfile(cpanel):
            panel = 'cPanel/WHM'
        elif os.path.isfile(da):
            panel = 'DirectAdmin'
        else:
            panel = 'None'

        # is a resource hit by the vm?
        with open('/proc/bc/' + vz[i][2] + '/resources', 'r') as vz_proc:
            for line in vz_proc:
                val = re.search('([0-9]+)$', line)
                if val:
                    if int( val.group(1) ) != 0:
                        hit = 'YES'
                        break
                    else:
                        hit = '-'
        vz_proc.close()

        # load-up our goodies
        vs[ vz[i][2] ] = {
            'load'      : vz[i][0],
            'ip'        : vz[i][1],
            'host'      : vz[i][3],
            'no.cpu'    : vz[i][4],
            'no.proc'   : vz[i][5],
            'hdd'       : int(vz[i][6]) / 1024 / 1024,
            'ram'       : int(vz[i][7]) / 256, # asume page is 4K (x86/amd64)
            'ram.free'  : ram_free,
            'distro'    : re.sub('\.tar\.gz', '', vz[i][8]),
            'panel'     : panel,
            'hit'       : hit
        }

    return vs

def printResults(vs):
    os.system('clear')
    head_format = COLOR['DARK_YELLOW'] + "%-20s %-5s %-16s %-37s %-7s %-7s %-10s %-12s %-5s %-25s %-10s" + COLOR['RESET']
    body_format = "%-20s %-5s %-16s %-37s %-7s %-7s %-10s %-12s %-5s %-25s %-10s"
    print head_format % ("LOAD AVERAGE", "VMID", "IP ADDRESS", "HOSTNAME", "#CPU", "#PROC", "DISK(GB)", "RAM(u/f)MB", "HIT", "DISTRIBUTION", "CONTROL PANEL")
    print COLOR['GREY30'] + '-' * 168 + COLOR['RESET']

    for v in sorted(vs.keys()):
        ram = str(vs[v]['ram']) + ' / ' + str(vs[v]['ram.free'])
        print body_format % (vs[v]['load'], v, vs[v]['ip'], vs[v]['host'], vs[v]['no.cpu'], vs[v]['no.proc'], vs[v]['hdd'], ram, vs[v]['hit'], vs[v]['distro'], vs[v]['panel'])

    print "\nNumber of servers: %d" % len(vs.keys())
    print "Host Load Average: %.2f/%.2f/%.2f" % (os.getloadavg()[0], os.getloadavg()[1], os.getloadavg()[2])

# colorful output -- TODO
COLOR={
    'RESET'             : '\033[0m',  # RESET COLOR
    'BOLD'              : '\033[1m',
    'UNDERLINE'         : '\033[4m',
    'BLINK'             : '\033[5m',
    'INVERT'            : '\033[7m',
    'CONCEALD'          : '\033[8m',
    'STRIKE'            : '\033[9m',
    'GREY30'            : '\033[90m',
    'GREY40'            : '\033[2m',
    'GREY65'            : '\033[37m',
    'GREY70'            : '\033[97m',
    'GREY20_BG'         : '\033[40m',
    'GREY33_BG'         : '\033[100m',
    'GREY80_BG'         : '\033[47m',
    'GREY93_BG'         : '\033[107m',
    'DARK_RED'          : '\033[31m',
    'RED'               : '\033[91m',
    'RED_BG'            : '\033[41m',
    'LIGHT_RED_BG'      : '\033[101m',
    'DARK_YELLOW'       : '\033[33m',
    'YELLOW'            : '\033[93m',
    'YELLOW_BG'         : '\033[43m',
    'LIGHT_YELLOW_BG'   : '\033[103m',
    'DARK_BLUE'         : '\033[34m',
    'BLUE'              : '\033[94m',
    'BLUE_BG'           : '\033[44m',
    'LIGHT_BLUE_BG'     : '\033[104m',
    'DARK_MAGENTA'      : '\033[35m',
    'PURPLE'            : '\033[95m',
    'MAGENTA_BG'        : '\033[45m',
    'LIGHT_PURPLE_BG'   : '\033[105m',
    'DARK_CYAN'         : '\033[36m',
    'AUQA'              : '\033[96m',
    'CYAN_BG'           : '\033[46m',
    'LIGHT_AUQA_BG'     : '\033[106m',
    'DARK_GREEN'        : '\033[32m',
    'GREEN'             : '\033[92m',
    'GREEN_BG'          : '\033[42m',
    'LIGHT_GREEN_BG'    : '\033[102m',
    'BLACK'             : '\033[30m',
}

##################### EXECUTE MAIN #####################
if __name__ == '__main__':
    main(sys.argv[1:])