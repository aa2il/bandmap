#!/usr/bin/python3 -u
#########################################################################################
#
# bandmap.py - Rev. 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Simple gui to sort & display dx cluster spots.  Indications as to the age of a spot and
# the "need" status of a spot's DXCC are also given.  The rig can be tuned to a spot by
# clicking on it.
#
# This code needs some libs, e.g. pytz, that may not already be installed.
# Use the package manager to install pip and then from the command line type
# sudo pip install pytz         (or pip3 for python3)
#
# The -u forces unubffered output on stdout making debug easier
#
# TO DO:
#   - During big contests, it seems to take some time for the gui to react - matching is slow?
#   - REALLY NEED TO CLEAN UP THIS RAT'S NEST!!!!
#
############################################################################################
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
#########################################################################################

from rig_io.socket_io import *
from bm_gui import *
import json
from tcp_client import *

#########################################################################################

# Sometimes when these don't work, its bx the login handshaking needs some work
NODES=OrderedDict()
NODES['PY3NZ']  = 'dxc.baependi.com.br:8000'        # dxwatch.com
NODES['NK7Z']   = 'nk7z-cluster.ddns.net:7373'      # Lots of spots!  RBN?
NODES['NC7J']   = 'dxc.nc7j.com'                    # Lots of spots, no FT8
NODES['W8AEF']  = 'paul.w8aef.com:7373'             # AZ - no FT8 - can turn it on
NODES['W3LPL']  = 'w3lpl.net:7373'                  # Ok - lots of spots, no FT8 dxc.w3lpl.net
NODES['N6WS']   = 'n6ws.no-ip.org:7300'             # Ok
NODES['K1TTT']  = 'k1ttt.net:7373'                  # (Peru, MA); Skimmer capable
NODES['W6RFU']  = 'ucsbdx.ece.ucsb.edu:7300'        # Ok - CQ Zones 1-5 spots only (i.e. US & Canada)
NODES['K3LR']   = 'dx.k3lr.com'                     # Doesnt work
NODES['AE5E']   = 'dxspots.com'                     # Ok - not many spots
NODES['N4DEN']  = 'dxc.n4den.us:7373'               # Ok
NODES['W6KK']   = 'w6kk.zapto.org:7300'             # Ok - USA and VE spots only, not many spots
NODES['N7OD']   = 'n7od.pentux.net'                 # Ok
NODES['WC4J']   = 'dxc.wc4j.net'                    # Doesnt work
NODES['WA9PIE'] = 'dxc.wa9pie.net:8000'             # HRD
NODES['K2LS']   = 'dxc.k2ls.com'                    # CQ Zones 1-8 spots only (i.e. NA) - not sure how to log in
NODES['W6CUA']  = 'w6cua.no-ip.org:7300'            # Not sure how to log on?
NODES['K7EK']   = 'www.k7ek.net:9000'               # Doesn't work?
NODES['K6EXO']  = 'k6exo.dyndns.org:7300'           # Doesn't work?
NODES['N6WS']   = 'n6ws.no-ip.org:7300'             # Not sure how to log on?
NODES['N7OD']   = 'n7od.pentux.net'                  # Not sure how to log on?
NODES['ANY']    = ''

################################################################################

# Structure to contain processing params
class PARAMS:
    def __init__(self):

        # Process command line args
        # Can add required=True to anything that is required
        arg_proc = argparse.ArgumentParser()
        arg_proc.add_argument('-contest', action='store_true',help='Conest Mode')
        arg_proc.add_argument('-ss', action='store_true',help='ARRL Sweepstakes')
        arg_proc.add_argument("-rig", help="Connection Type to Rig",
                              type=str,default="ANY",
                              choices=['FLDIGI','FLRIG','DIRECT','HAMLIB','ANY','NONE'])
        arg_proc.add_argument("-port", help="TCPIP port",
                              type=int,default=0)
        arg_proc.add_argument("-server", help="Server",
                              type=str,default="ANY",
                              choices=list(NODES.keys()) )
        #                      choices=list(NODES.keys())+NODES2)
        arg_proc.add_argument("-wsjt", help="wsjt", nargs='*', 
                              type=str,default=None)
        arg_proc.add_argument("-log", help="Log file (keep track of dupes)",
                              type=str,
                              default=None)
                              #default=None,nargs='*')
                              #default="~/logs/[MYCALL].adif")
                              #default="")    #,nargs='+')
        arg_proc.add_argument('-dx', action='store_true',help='Show only DX spots')
        arg_proc.add_argument('-buttons', action='store_true',help='Enable band buttons')
        arg_proc.add_argument('-udp', action='store_true',help='Start UDP client')
        arg_proc.add_argument('-ft4', action='store_true',help='Use FT4 freqs instead of FT8')
        arg_proc.add_argument("-vfo", help="VFO to follow",
                              type=str,default="A",
                              choices=['A','B'] )
        #arg_proc.add_argument('-noft8', action='store_true',help='Filter out FT8 spots')
        arg_proc.add_argument('-test', action='store_true',help='Test Mode')
        arg_proc.add_argument("-hours", help="Max no. hours for a dupe",
                              type=float,default=2*24)
        args = arg_proc.parse_args()

        self.RIG          = args.rig
        self.PORT         = args.port

        self.MAX_HOURS_DUPE = args.hours

        self.CONTEST_MODE = args.contest
        
        self.PARSE_LOG    = self.CONTEST_MODE and True
        self.PARSE_LOG    = True
        #self.PARSE_LOG    = self.CONTEST_MODE or len(args.log)>0
        
        self.TEST_MODE    = args.test
        self.CW_SS        = args.ss
        self.DX_ONLY      = args.dx
        self.UDP_CLIENT   = args.udp
        self.RIG_VFO      = args.vfo
        self.FT4          = args.ft4

        self.CHALLENGE_FNAME = os.path.expanduser('~/Python/data/states.xls')

        # See     http://www.ng3k.com/misc/cluster.html            for a list 
        self.SERVER=args.server.upper()
        self.WSJT_FNAME=None

        self.WSJT_IP_ADDRESS = '127.0.0.1'
        self.WSJT_PORT = 2237
        WSJT2=args.wsjt
        if WSJT2!=None:
            print("\nWSJT2=",WSJT2,len(WSJT2))
            self.WSJT_FNAME=os.path.expanduser("~/.local/share/WSJT-X")
            self.WSJT_FNAME+=" - "+WSJT2[0]
            self.WSJT_FNAME+="/ALL.TXT"
            self.CLUSTER='WSJT'
            self.SERVER='WSJT'
    
            if len(WSJT2)>=2:
                self.WSJT_PORT = int(WSJT2[1])
        
            print("WSJT_FNAME=", self.WSJT_FNAME)
            print("WSJT_PORT =", self.WSJT_IP_ADDRESS,self.WSJT_PORT)
            #sys.exit(0)
        else:
            self.CLUSTER=NODES[self.SERVER]
        #print('CLUSTER=',CLUSTER)

        if args.log==None:
            if args.wsjt==None:
                self.LOG_NAME = "~/logs/[MYCALL].adif"
            else:
                self.LOG_NAME = "~/.local/share/WSJT-X"
                if WSJT2!=None:
                    self.LOG_NAME+=" - "+WSJT2[0]
                self.LOG_NAME += "/wsjtx_log.adi"
        else:
            self.LOG_NAME = args.log
        print('LOG_NAME=',self.LOG_NAME)
        #sys.exit(0)
        

        if False:
            #print(len(args.log))
            print(args.log)
            print(WSJT2)
            print(self.SERVER)
            print(self.LOG_NAME)
            sys,exit(0)

        
        if args.server=='WA9PIE' or False:
            self.ECHO_ON=True
        else:
            self.ECHO_ON=False

        if self.CLUSTER=='WSJT':
            self.MAX_AGE=5
        else:
            self.MAX_AGE=15
    
        self.rootlogger = "dxcsucker"
        self.TIME_OUT=.01

        # Read config file
        self.RCFILE=os.path.expanduser("~/.bandmaprc")
        self.SETTINGS=None
        try:
            with open(self.RCFILE) as json_data_file:
                self.SETTINGS = json.load(json_data_file)
        except:
            print(self.RCFILE,' not found - need call!\n')
            s=SETTINGS(None,self)
            while not self.SETTINGS:
                try:
                    s.win.update()
                except:
                    pass
                time.sleep(.01)
            print('Settings:',self.SETTINGS)

        self.MY_CALL      = self.SETTINGS['MY_CALL']
        self.LOG_NAME     = os.path.expanduser( self.LOG_NAME.replace('[MYCALL]',self.MY_CALL ) )
        self.NODES        = NODES
        self.THREADS      = []

        if self.SERVER=="WSJT" or args.buttons:
            self.ALLOW_CHANGES=True
        else:
            self.ALLOW_CHANGES=False
        
        
#########################################################################################

# Begin executable
if __name__ == "__main__":

    print("\n\n***********************************************************************************")
    print("\nStarting Bandmap  ...")

    # Process command line params
    P=PARAMS()
    if True:
        print("P=")
        pprint(vars(P))
        print(' ')

    # Open a file to save all of the spots
    if not P.TEST_MODE and False:
        fp = open("/tmp/all_spots.dat","w")
    else:
        fp=-1

    # Open xlmrpc connection to fldigi
    P.sock = open_rig_connection(P.RIG,0,P.PORT,0,'BANDMAP')
    if not P.sock.active:
        print('*** No connection to rig ***')
        #sys,exit(0)

    # Open telnet connection to spot server
    logger = get_logger(P.rootlogger)
    print('SERVER=',P.SERVER,'\tMY_CALL=',P.MY_CALL)
    #sys,exit(0)
    if P.SERVER=='ANY':
        KEYS=list(NODES.keys())
        print('NODES=',NODES)
        print('KEYS=',KEYS)

        P.tn=None
        inode=0
        while not P.tn and inode<len(KEYS):
            key = KEYS[inode]
            P.tn = connection(P.TEST_MODE,NODES[key],P.MY_CALL,P.WSJT_FNAME, \
                                 ip_addr=P.WSJT_IP_ADDRESS,port=P.WSJT_PORT)
            inode += 1
        if P.tn:
            P.CLUSTER=NODES[key]
            P.SERVER = key
        else:
            print('\n*** Unable to connect to any node - no internet? - giving up! ***\n')
            sys.exit(0)
                
    else:
        P.tn = connection(P.TEST_MODE,P.CLUSTER,P.MY_CALL,P.WSJT_FNAME, \
                             ip_addr=P.WSJT_IP_ADDRESS,port=P.WSJT_PORT)

    if not P.tn:
        print('Giving up')
        sys.exit(0)
    
    # Read challenge data
    P.data = ChallengeData(P.CHALLENGE_FNAME)

    # Open UDP client
    if P.UDP_CLIENT:
        try:
            P.udp_client = TCP_Client(None,7474)
            worker = Thread(target=P.udp_client.Listener, args=(), name='UDP Server' )
            worker.setDaemon(True)
            worker.start()
            P.THREADS.append(worker)
        except Exception as e: 
            print(e)
            print('--- Unable to connect to UDP socket ---')
                
    # Create GUI 
    bm = BandMapGUI(P)

    bm.root.mainloop()



