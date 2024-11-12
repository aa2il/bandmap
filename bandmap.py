#!/usr/bin/python3 -u
#########################################################################################
#
# bandmap.py - Rev. 1.0
# Copyright (C) 2021-4 by Joseph B. Attili, aa2il AT arrl DOT net
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

from rig_io import open_rig_connection
from bm_gui import BandMapGUI
from settings import *
from params import *
from dx.cluster_connections import connection,get_logger
from cluster_feed import test_telnet_connection
from dx.spot_processing import ChallengeData
from pprint import pprint
from get_node_list import *
from tcp_server import *
from bm_udp import *
from load_history import load_history
from utilities import get_Host_Name_IP,ping_test,Memory_Monitor
from watchdog import *

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

    # Memory monitor
    if True:
        if P.SERVER=="WSJT":
            P.MEM = Memory_Monitor('/tmp/BANDMAP_MEMORY_WSJT.TXT')
        else:
            P.MEM = Memory_Monitor('/tmp/BANDMAP_MEMORY.TXT')
    
    # Create GUI 
    bm_gui = BandMapGUI(None,P)
    P.bm_gui=bm_gui

    # Read list of nodes - work in progress
    if False:
        get_node_list(P)
        sys.exit(0)

    # Open connection to rig
    P.sock = open_rig_connection(P.CONNECTION,0,P.PORT,0,'BANDMAP',rig=P.RIG)
    if not P.sock.active:
        print('*** No connection to rig ***')
        #sys,exit(0)

    # Test internet connection - to be continued ...
    if P.SERVER!='NONE' and P.SERVER!="WSJT":
        print('Checking internet connection ...')
        P.host_name,P.host_ip=get_Host_Name_IP()
        print("\nHostname :  ", P.host_name)
        print("IP : ", P.host_ip,'\n')
        if P.host_ip=='127.0.0.1':
            P.INTERNET=False
            print('No internet connection :-(')
            #sys.exit(0)
        else:
            print('Local Internet connection appears to be alive ...')
            # Next try pinging something outside LAN
            P.INTERNET=ping_test('8.8.8.8')
            if P.INTERNET:
                print('\n... Outside Internet Connection appears to be alive also.')
            else:
                print('\n... No internet connection :-(')
                #sys.exit(0)

    # Read various auxilary data files
    P.bm_gui.read_aux_data()

    # Start thread with UDP server
    if P.BM_UDP_CLIENT:
        P.bm_gui.status_bar.setText('Opening UDP client ...')
        P.udp_server = TCP_Server(P,None,BANDMAP_UDP_PORT,Server=True,
                                  Handler=bm_udp_msg_handler)
        worker = Thread(target=P.udp_server.Listener, args=(),
                        name='Bandmap UDP Server' )
        worker.daemon=True
        worker.start()
        P.threads.append(worker)
        
    # WatchDog - runs in its own thread
    P.WATCHDOG = True
    #P.WATCHDOG = False
    if P.WATCHDOG:
        P.bm_gui.status_bar.setText("Spawning Watchdog ...")
        P.monitor = WatchDog(P,2000)

    # Let's go!
    P.bm_gui.status_bar.setText('And away we go!')
    P.bm_gui.run()
    if True:
        print("P=")
        pprint(vars(P))
        print(' ')
    P.bm_gui.root.mainloop()



