#########################################################################################
#
# cluster_feed.py - Rev. 2.0
# Copyright (C) 2021-4 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Routines to grab spots from the dx cluster.
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

import sys
import re
import time
import pytz
from datetime import datetime
from dx.spot_processing import Spot
from pprint import pprint
from fileio import parse_adif
import logging               
from pywsjtx.simple_server import SimpleServer 
from utilities import freq2band, error_trap
from dx.cluster_connections import *
import threading
import queue

#########################################################################################

UTC = pytz.utc
OLD_WAY=True

#########################################################################################

# Setup basic logging
logging.basicConfig(
    format="%(asctime)-15s [%(levelname)s] %(funcName)s: %(message)s",
    level=logging.INFO)

# Function to fudge dxcc for display
def cleanup(dxcc):
    try:
        dxcc2=dxcc.replace('Republic of ','')
    except:
        dxcc2=dxcc
    return dxcc2

# The GUI
class ClusterFeed:
    def __init__(self,P,msec):

        # Init
        print('ClusterFeed Init ...')
        self.P = P
        self.nerrors=0
        self.last_error=''

        # Open spot server
        self.open_spot_server()

        # Open a file to save all of the spots
        if P.SAVE_SPOTS:
            self.fp = open("all_spots.dat","w")
        else:
            self.fp=-1

        # Create a buffer to communicate spots to gui thread
        P.q     = queue.Queue(maxsize=0)

        # Kick off cluster spot monitor
        dt=.001*msec
        self.Timer = threading.Timer(dt, self.Monitor)
        self.Timer.daemon=True                       # This prevents timer thread from blocking shutdown
        self.Timer.start()
        
        
    # Function to open spot server
    def open_spot_server(self):

        print('\nOpening Spot Server ...')
        P=self.P

        # Open telnet connection to spot server
        print('SERVER=',P.SERVER,'\tMY_CALL=',P.MY_CALL)
        #sys,exit(0)
        if P.SERVER=='NONE': # or (P.SERVER!="WSJT" and not P.INTERNET):

            # No cluster node
            self.tn = None
        
        elif P.SERVER=='ANY':

            # Go down list of known nodes until we find one we can connect to
            KEYS=list(P.NODES.keys())
            print('NODES=',P.NODES)
            print('KEYS=',KEYS)
            
            self.tn=None
            inode=0
            while not self.tn and inode<len(KEYS):
                key = KEYS[inode]
                self.P.bm_gui.status_bar.setText("Attempting to open node "+P.NODES[key]+' ...')
                self.tn = connection(P.TEST_MODE,P.NODES[key],P.MY_CALL,P.WSJT_FNAME, \
                                  ip_addr=P.WSJT_IP_ADDRESS,port=P.WSJT_PORT)
                inode += 1
            if self.tn:
                P.CLUSTER=P.NODES[key]
                P.SERVER = key
            else:
                print('\n*** Unable to connect to any node - no internet? - giving up! ***\n')
                sys.exit(0)
                
        else:

            # Connect to specified node 
            self.P.bm_gui.status_bar.setText("Attempting to open "+P.CLUSTER+' ...')
            self.tn = connection(P.TEST_MODE,P.CLUSTER,P.MY_CALL,P.WSJT_FNAME, \
                              ip_addr=P.WSJT_IP_ADDRESS,port=P.WSJT_PORT)

        if not P.TEST_MODE:
            if self.tn:
                OK=self.test_telnet_connection()
                if not OK:
                    print('OPEN_SPOT_SERVER: Whooops!  SERVER=',P.SERVER,'\tOK=',OK)
                    sys.exit(0)
            else:
                if P.SERVER!='NONE':
                    print('OPEN_SPOT_SERVER: Giving up!  SERVER=',P.SERVER,'\tOK=',OK)
                    sys.exit(0)

    # Function to test a telnet connection
    def test_telnet_connection(self):
        #tn=self.tn
        #print('tn=',tn,type(tn),isinstance(tn,SimpleServer))
        
        if not self.tn:
            print('TEST_TELNET_CONNECTION: *** ERROR *** Unexpected null connection')
            return False
        elif isinstance(self.tn,SimpleServer):
            print('TEST TELNET CONNECTION - Simpler server OK')
            return True    
    
        try:
            line=self.tn.read_very_eager().decode("utf-8")
            ntries=0
            while len(line)==0 and ntries<10:
                ntries+=1
                time.sleep(1)
                line=self.tn.read_very_eager().decode("utf-8")
            print('TEST TELNET CONNECTION - line=\n',line,'\tlen=',len(line))
            if len(line)==0:
                print('TEST TELNET CONNECTION - No response - giving up')
                return False
        except EOFError:
            print("TEST TELNET CONNECTION - EOFerror: telnet connection is closed")
            return False

        print('TEST TELNET CONNECTION - OK!')
        return True

    #
    def Monitor(self):

        #print('Cluster Monitor ...')
        n = self.cluster_feed()
        if n==0:
            if "telent connection closed" in self.last_error:
                self.enable_scheduler=False
                print('SCHEDULER - Attempting to reopen node ...')
                self.SelectNode()
            else:
                #print('SCHEDULER - Nothing returned')
                dt=200          # Wait a bit before querying cluster again
        else:
            dt=5      # We got a spot - see if there are more

        #print('Restarting Cluster Monitor - n=',n,'\tdt=',dt)
        self.Timer = threading.Timer(.001*dt, self.Monitor)
        self.Timer.setDaemon(True)   
        self.Timer.start()


    # Function to read spots from the telnet connection
    def cluster_feed(self):
        
        fp=self.fp
        VERBOSITY = self.P.DEBUG

        if VERBOSITY>=1:
            print('CLUSTER FEED A: nspots=',self.nspots,len(self.SpotList),len(self.current))

        if self.nerrors>10:
            print('CLUSTER_FEED: Too many errors - giving up!')
            return 0

        if self.P.TEST_MODE:

            # Read a line from the recorded spots file
            if not self.tn.closed:
                a=self.tn.readline()
                if a=='':
                    print('---- EOF ----')
                    self.tn.close()
                    return False
                else:
                    #                line=a[2:]
                    line=a
            else:
                line=''

        elif self.P.CLUSTER=='WSJT':

            spot = self.tn.get_spot2(None,0)
            line = self.tn.convert_spot(spot)
            if line:
                print('\nCluster Feed: line=',line)
            else:
                print('\nCluster Feed: Blank line=',line)
                print('spot=',spot)

            # Check for band changes
            if self.tn.nsleep>=1:
                band  = self.P.bm_gui.band.get()
                #logging.info("Calling Get band ...")
                frq2 = 1e-6*self.P.bm_gui.sock.get_freq(VFO=self.P.bm_gui.VFO)
                band2 = freq2band(frq2)
                #print('CLUSTER_FEED: band/band2=',band,band2)
                if band2==0 or not band2:
                    print('CLUSTER_FEED: Current band=',band,'\t-\tRig band=',band2)
                    tmp   = self.tn.last_band()
                    #band2 = int( tmp[0:-1] )
                    band2=tmp
                if band!=band2:
                    print('CLUSTER_FEED: BAND.SET band2=',band2)
                    self.P.bm_gui.band.set(band2)
                    self.P.bm_gui.SelectBands()

            # Check for antenna changes
            #self.SelectAnt(-1)
                
        else:

            # Read a line from the telnet connection
            if VERBOSITY>=2:
                print('CLUSTER FEED: Reading tn ...')
            if self.tn:
                try:
                    line = self.tn.read_until(b"\n",self.P.TIME_OUT).decode("utf-8")
                except Exception as e:
                    error_trap('CLUSTER_FEED:   ??????')
                    line = ''
                    self.nerrors+=1
                    self.last_error=str(e)
                
                if VERBOSITY>=2:
                    print('Line:',line)
            else:
                return 0
        
            if line=='': 
                #print('CLUSTER FEED: Time out ',self.P.TIME_OUT)
                return 0
            elif not "\n" in line:
                # Dont let timeout happen before we get entire line
                #print 'CLUSTER FEED: Partial line read'
                try:
                    line2 = self.tn.read_until(b"\n",timeout=10).decode("utf-8") 
                    line = line+line2
                except:
                    error_trap('CLUSTER_FEED: TIME_OUT2 or other issue ???')
                    print('line  =',line,type(line))
                    #print('line2 =',line2,type(line2))
                    return 0

        if len(line)>5:
            if self.P.ECHO_ON or VERBOSITY>=1:
                #print('>>> Cluster Feed:',line.rstrip())
                print('==> ',line.rstrip())
            if self.P.SAVE_SPOTS:
                fp.write(line.rstrip()+'\n')
                fp.flush()

            # Some clusters ask additional questions
            if line.find("Is this correct?")>=0:
                self.tn.write(b"Y\n")              # send "Y"
                return 0

        # Process the spot
        if len(line)>0:
            #self.P.bm_gui.scrolling('DIGEST SPOT A')
            #self.P.bm_gui.digest_spot(line)
            #self.P.bm_gui.scrolling('DIGEST SPOT B')
            self.P.q.put(line)
        return 1

        
    # Callback to reset telnet connection
    def Reset(self):
        print("\n------------- Reset -------------",self.P.CLUSTER,'\n')
        self.P.bm_gui.status_bar.setText("RESET - "+self.P.CLUSTER)
        self.P.bm_gui.Clear_Spot_List()
        """
        if self.P.BM_UDP_CLIENT and self.P.bm_udp_client and False:
            self.P.bm_udp_client.StartServer()
        if self.P.BM_UDP_CLIENT and self.P.bm_udp_server and False:
            self.P.bm_udp_server.StartServer()
        """
        if self.tn:
            self.tn.close()
            time.sleep(.1)
            
        try:
            self.tn = connection(self.P.TEST_MODE,self.P.CLUSTER, \
                                 self.P.MY_CALL,self.P.WSJT_FNAME)
            print("--- Reset --- Connected to",self.P.CLUSTER)
            OK=self.test_telnet_connection()
        except:
            error_trap('GUI->RESET: Problem connecting to node'+self.P.CLUSTER)
            OK=False
            
        if not OK:
            print('--- Reset --- Now what Sherlock?!')
            self.P.bm_gui.status_bar.setText('Lost telnet connection?!')

