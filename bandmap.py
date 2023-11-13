#!/usr/bin/python3 -u
#########################################################################################
#
# bandmap.py - Rev. 1.0
# Copyright (C) 2021-3 by Joseph B. Attili, aa2il AT arrl DOT net
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
from gui import BandMapGUI
from settings import *
from params import *
from dx.cluster_connections import connection,get_logger
from cluster_feed import test_telnet_connection
from dx.spot_processing import ChallengeData
from pprint import pprint
from fileio import read_text_file
from get_node_list import *
from tcp_server import *
from udp import *
from load_history import load_history

#########################################################################################

VERSION='1.0'

#########################################################################################

# Begin executable
if __name__ == "__main__":

    print("\n\n***********************************************************************************")
    print("\nStarting Bandmap v'+VERSION+' ...")
    print('\nUse -echo flag to echo lines from zerver')

    # Process command line params
    P=PARAMS()
    
    # Create GUI 
    gui = BandMapGUI(P)
    P.gui=gui
    
    # Read list of nodes - work in progress
    if False:
        get_node_list(P)
        sys.exit(0)

    # Open xlmrpc connection to rig
    P.sock = open_rig_connection(P.CONNECTION,0,P.PORT,0,'BANDMAP',rig=P.RIG)
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
                
    elif P.SERVER=='NONE':
        P.tn = None
    else:
        P.tn = connection(P.TEST_MODE,P.CLUSTER,P.MY_CALL,P.WSJT_FNAME, \
                             ip_addr=P.WSJT_IP_ADDRESS,port=P.WSJT_PORT)

    if not P.TEST_MODE:
        if P.tn:
            OK=test_telnet_connection(P.tn)
            if not OK:
                sys.exit(0)
        else:
            if P.SERVER!='NONE':
                print('Giving up')
                sys.exit(0)
    
    # Read challenge data
    P.data = ChallengeData(P.CHALLENGE_FNAME)

    # Load data for highlighting CW ops members
    if P.CWOPS:
        fname='~/Python/history/data/Shareable CWops data.xlsx'
        HIST,fname2 = load_history(fname)
        P.gui.members=list( set( HIST.keys() ) )
        print('No. CW Ops Members:',len(P.gui.members))
        #print(self.members)
        #sys.exit(0)
    
    # Start thread with UDP server
    if P.UDP_CLIENT:
        P.udp_server = TCP_Server(P,None,BANDMAP_UDP_PORT,Server=True,
                                  Handler=udp_msg_handler)
        worker = Thread(target=P.udp_server.Listener, args=(),
                        name='Bandmap UDP Server' )
        worker.daemon=True
        worker.start()
        P.threads.append(worker)
        
    # Read list of friends
    P.gui.friends = []
    lines = read_text_file('Friends.txt',
                                KEEP_BLANKS=False,UPPER=True)
    for line in lines:
        c=line.split(',')[0]
        if c[0]!='#':
            P.gui.friends.append(c)
    print('FRIENDS=',P.gui.friends)
    #sys.exit(0)
                                   
    # Read lists of most wanted
    P.gui.most_wanted = read_text_file('Most_Wanted.txt',
                                    KEEP_BLANKS=False,UPPER=True)
    print('MOST WANTED=',P.gui.most_wanted)
    
    # Read lists of common errors
    corrections = read_text_file('Corrections.txt',
                                    KEEP_BLANKS=False,UPPER=True)
    print('Corrections=',corrections)
    P.gui.corrections={}
    for x in corrections:
        print(x)
        y=x.split(' ')
        P.gui.corrections[y[0]] = y[1]
    print('Corrections=',P.gui.corrections)

    # Let's go!
    P.gui.run()
    if True:
        print("P=")
        pprint(vars(P))
        print(' ')
    P.gui.root.mainloop()



