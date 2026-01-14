#########################################################################################
#
# cluster_feed.py - Rev. 2.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
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

import os
import sys
import re
import time
import pytz
from datetime import datetime
from dx.spot_processing import Spot,Station
from pprint import pprint
from fileio import parse_adif
import logging               
from pywsjtx.simple_server import SimpleServer 
from utilities import freq2band, error_trap
from dx.cluster_connections import *
import threading
import queue
from rig_io.ft_tables import THIRTEEN_COLONIES

#########################################################################################

UTC = pytz.utc
OLD_WAY=True
DEFAULT_BAND = '20m'

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

# Object to manage telnet feed from dx cluster
class ClusterFeed:
    def __init__(self,P,msec):

        # Init
        print('ClusterFeed Init ...')
        self.P = P
        self.nerrors=0
        self.last_error=''
        self.lock = threading.Lock()             # Avoid collisions between various threads
        self.lock_to=2.0                         # Time out to acquire lock
        self.Reset_Flag = threading.Event()
        self.tn = None
        
        # Open spot server
        self.open_spot_server()

        # Open a file to save all of the spots
        if P.SAVE_SPOTS:
            pid = os.getpid()
            #fname ="/tmp/ALL_SPOTS.DAT"
            fname ="/tmp/ALL_SPOTS_"+str(pid)+".DAT"
            self.fp = open(fname,"w")
        else:
            self.fp=-1

        # Create a buffer to communicate spots to gui thread
        P.bm_q = queue.Queue(maxsize=0)

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
        if self.Reset_Flag.isSet():
            self.Reset_Flag.clear()
            self.Reset()
        
        n = self.cluster_feed()
        if n==0:
            if self.P.TEST_MODE:
                print('\n--- MONITOR: EOF! ---')
                return
            elif "telent connection closed" in self.last_error:
                self.enable_scheduler=False
                print('SCHEDULER - Attempting to reopen node ...')
                self.SelectNode()
            else:
                #print('SCHEDULER - Nothing returned')
                dt=200          # Wait a bit before querying cluster again
        else:
            # We got a spot - see if there are more
            if self.P.TEST_MODE:
                dt=5
            else:
                dt=5

        #print('Restarting Cluster Monitor - n=',n,'\tdt=',dt)
        self.Timer = threading.Timer(.001*dt, self.Monitor)
        self.Timer.setDaemon(True)   
        self.Timer.start()


    # Function to read spots from the telnet connection
    def cluster_feed(self):

        P=self.P
        fp=self.fp
        VERBOSITY = self.P.DEBUG

        if VERBOSITY>=1:
            print('CLUSTER FEED A: nspots=',P.nspots,len(P.SpotList),len(P.current))

        if self.nerrors>10:
            print('CLUSTER_FEED: Too many errors - giving up!',self.nerrors)
            return 0

        if self.P.TEST_MODE:

            # Read a line from the recorded spots file
            if not self.tn.closed:
                a=self.tn.readline()
                if a=='':
                    print('---- EOF ----')
                    self.tn.close()
                    return 0
                else:
                    #                line=a[2:]
                    line=a
            else:
                return 0
                line=''

            #print('CLUSTER_FEED: line=',line)
                
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
                band  = self.P.GUI_BAND
                #logging.info("Calling Get band ...")
                frq2 = 1e-6*self.P.sock.get_freq(VFO=self.P.RIG_VFO)
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
                except ConnectionResetError:
                    err = error_trap('CLUSTER_FEED: Whooops! Lost connection to cluster server ???')
                    print('err=',err)
                    self.tn=None
                except Exception as e:
                    err = error_trap('CLUSTER_FEED: Problem reading line from cluster server ...')
                    print('err=',err)
                    line = ''
                    self.nerrors+=1
                    self.last_error=str(e)

                    #if "telnet connection closed" in err[1]:
                    #    print("\tLooks like we've lost the connection to the server :-(")
                
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
        if len(line)>0 and self.P.data:
            self.digest_spot(line)
            
        return 1

        
    # Callback to reset telnet connection
    def Reset(self):
        print("\nCLUSTER FEED-> Reset --- Cluster=",self.P.CLUSTER,'\n')
        self.P.bm_gui.status_bar.setText("RESET - "+self.P.CLUSTER)
        self.nerrors=0
        self.P.bm_gui.Clear_Spot_List()

        # Close down existing connection
        if self.tn:
            self.tn.close()
            time.sleep(.1)
            
        try:
            self.tn = connection(self.P.TEST_MODE,self.P.CLUSTER, \
                                 self.P.MY_CALL,self.P.WSJT_FNAME)
            print("CLUSTER FEED->Reset --- Connected to",self.P.CLUSTER,'\ttn=',self.tn)
            OK=self.test_telnet_connection()
        except:
            error_trap('CLUSTER FEED->Reset --- Problem connecting to node'+self.P.CLUSTER)
            OK=False
            
        if not OK:
            print("CLUSTER FEED->Reset --- Now what Sherlock?! - Looks like we've lost the telnet connect ***\n")
            self.P.bm_gui.status_bar.setText('Lost telnet connection?!')
            self.tn = None



    # Function to read spots from the telnet connection
    def digest_spot(self,line):

        P=self.P
        VERBOSITY = self.P.DEBUG
        #if P.GUI_BAND==None:
        #    P.GUI_BAND = self.P.bm_gui.band.get()
            
        # Check for logged contact
        if "<adif_ver" in line:
            print('\nDIGEST SPOT: LOGGED Contact Detected ...')
            qso=parse_adif(-1,line)
            #print('qso=',qso)
            self.P.qsos.append( qso[0] )
            #print('self.qsos=',self.qsos)
            self.lb_update()

        if self.P.CLUSTER=='WSJT':
            print('SPOT:',line,len(line))
        obj = Spot(line)
        if obj.spotter_call!=P.MY_CALL:
            obj.snr=''

        if self.P.ECHO_ON:
            print('OBJ:')
            pprint(vars(obj))
        sys.stdout.flush()

        # Check if we got a new spot
        if not hasattr(obj, 'dx_call'):

            print('Not sure what to do with this: ',line.strip())

        else:

            dx_call=obj.dx_call

            # Fix common mistakes
            keep=True
            if dx_call==None:
                #print('DIGEST SPOT: *** CORRECTION - blank call?????',dx_call)
                #pprint(vars(obj))
                keep=False
            elif len(dx_call)<3:
                print('DIGEST SPOT: *** CORRECTION but dont know what to do - call=',dx_call)            
                keep=False
            elif dx_call in P.corrections:
                print('DIGEST SPOT: *** NEED A CORRECTION ***',dx_call)
                dx_call = P.corrections[dx_call]
                obj.dx_call = dx_call
            elif dx_call[0]=='T' and dx_call[1:] in self.P.members:
                dx_call = dx_call[1:]
                obj.dx_call = dx_call
            elif len(dx_call)>=7 and dx_call[-3:] in ['CWT','SST','MST']:
                dx_call = dx_call[:-3]
                obj.dx_call = dx_call

            # Reject FT8/4 spots if we're in a contest
            m = self.P.GUI_MODE
            if self.P.CONTEST_MODE:
                if m=='CW' and obj.mode in ['FT4','FT8','DIGITAL']:
                    keep=False

            # Reject calls that really aren't calls
            b = self.P.GUI_BAND
            if keep:
                if not dx_call or len(dx_call)<=2 or not obj.dx_station: 
                    keep=False
                elif not obj.dx_station.country and not obj.dx_station.call_suffix:
                    keep=False

                # Filter out NCDXF beacons
                elif 'NCDXF' in line or 'BEACON' in line or '/B' in dx_call:
                    if VERBOSITY>=1:
                        print('Ignoring BEACON:',line.strip())
                    keep=False
        
            if False:
                print('DIGEST SPOT:',line.strip())
                print('keep=',keep,'\tb=',b)
        
            if keep:
                if dx_call==self.P.MY_CALL or (self.P.ECHO_ON and False):
                    print('keep:',line.strip())

                acq=self.lock.acquire(timeout=self.lock_to)
                if not acq:
                    print('DIGEST_SPOT: Unable to acquire lock - giving up!')
                    print('line=',line.strip())
                    return
                    
                # Highlighting in WSJT-X window
                if self.P.CLUSTER=='WSJT':
                    for qso in self.P.qsos:
                        if self.P.CW_SS:
                            # Can only work each station once regardless of band in this contest
                            match = dx_call==qso['call']
                        else:
                            match = (dx_call==qso['call']) and (b==qso['band'])
                        if match:
                            break
                    else:
                        # Set background according to SNR to call attention to stronger sigs
                        fg=1                       # 1=Red
                        try:
                            snr=int(obj.snr)
                            if snr>=0:
                                bg=2              # 13=Light magenta, 2=Light Green
                            elif snr>=-15:
                                bg=10              # 18=Light purple, 10=light Green
                            else:
                                bg=0
                        except:
                            bg=0
                        self.P.ClusterFeed.tn.highlight_spot(dx_call,fg,bg)
                        #print('DIGEST SPOT: call=',obj.dx_call,'\tsnr=',obj.snr,
                        #'\tfg/bg=',fg,bg,'\t',obj.snr.isnumeric(),int(obj.snr),len(obj.snr))

                # Pull out info from the spot
                freq=float( obj.frequency )
                mode=obj.mode
                band=obj.band  # w/o m at end
                P.nspots+=1
                print('DIGEST SPOT: call=',obj.dx_call,'\tfreq=',freq,'\tmode=',mode,
                      '\tband=',band,'\tnspots=',P.nspots)

                dxcc=obj.dx_station.country
                if dxcc==None and False:
                    print('\nDXCC=NONE!!!!')
                    pprint(vars(obj.dx_station))
                    sys.exit(0)
                now = datetime.utcnow().replace(tzinfo=UTC)
                year=now.year
                obj.needed = self.P.data.needed_challenge(dxcc,str(band)+'M',0)
                obj.need_this_year = self.P.data.needed_challenge(dxcc,year,0) and self.P.SHOW_NEED_YEAR

                # Reconcile mode
                if mode in ['CW']:
                    mode2='CW'
                elif mode in ['SSB','LSB','USB','FM','PH']:
                    mode2='Phone'
                elif mode in ['DIGITAL','FT8','FT4','JT65','PSK']:
                    mode2='Data'
                else:
                    mode2='Unknown'
                obj.need_mode = self.P.data.needed_challenge(dxcc,mode2,0) and self.P.SHOW_NEED_MODE

                # Contest multipliers
                obj.new_mult=self.P.SCORING.new_multiplier(obj.dx_call,band)
            
                # Determine color for this spot
                match = self.B4(obj,str(band)+'m')
                c,c2,age=self.spot_color(match,obj)
                obj.color=c
                
                # Check if this call is already there
                # Need some error trapping here bx we seem to get confused sometimes
                try:
                    b = self.P.GUI_BAND
                except:
                    b = ''

                try:
                    # Indices of all matches
                    idx1 = [i for i,x in enumerate(P.SpotList)
                            if x.dx_call==dx_call and x.band==band and x.mode==mode]
                    #if x.dx_call==dx_call and x.band==band]
                except:
                    idx1 = []

                if len(idx1)>0:

                    # Call already in list - Update spot info
                    obj.cnt=+1
                    if VERBOSITY>=1:
                        print("DIGEST SPOT: Dupe call =",dx_call,'\tfreq=',freq,
                              '\tmode=',mode,'\tband=',band,'\tidx1=',idx1)
                    for i in idx1:
                        if VERBOSITY>=2:
                            print('\tA i=',i,P.SpotList[i].dx_call,
                                  '\ttime=',P.SpotList[i].time,obj.time,
                                  '\tfreq=',P.SpotList[i].frequency,obj.frequency)
                        P.SpotList[i].time=obj.time
                        P.SpotList[i].frequency=obj.frequency
                        P.SpotList[i].snr=obj.snr
                        P.SpotList[i].wpm=obj.wpm
                        P.SpotList[i].color=obj.color
                        if self.P.CLUSTER=='WSJT':
                            P.SpotList[i].df=obj.df
                        if VERBOSITY>=2:
                            print('\tB i=',i,P.SpotList[i].dx_call,
                                  '\ttime=',P.SpotList[i].time,obj.time,
                                  '\tfreq=',P.SpotList[i].frequency,obj.frequency)

                    # Update list box entry
                    idx2 = [i for i,x in enumerate(P.current) if x.dx_call == dx_call and x.band==b]
                    if len(idx2)>0:
                        self.P.bm_q.put( [idx2[0]] )
                        if self.P.CLUSTER=='WSJT':
                            df = obj.df
                            try:
                                df=int(df)
                                entry="%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                                    (df,dx_call,mode,cleanup(dxcc),obj.snr)
                                self.P.bm_q.put( [idx2[0], entry, obj.color] )
                            
                                i=idx[0]
                                P.current[i].time=obj.time
                                P.current[i].frequency=obj.frequency
                                P.current[i].snr=obj.snr
                                P.current[i].df=obj.df
                                P.current[i].color=obj.color
                            except:
                                error_trap('DIGEST SPOT: ?????')
                        else:
                            if mode in ['CW']:
                                val = obj.wpm
                            else:
                                val = obj.snr
                            entry="%-6.1f  %-10.19s  %+6.6s %-15.16s %+4.4s" % \
                                (freq,dx_call,mode,cleanup(dxcc),val)
                            self.P.bm_q.put( [idx2[0], entry, obj.color] )
                    
                else:
                    
                    # New call - maintain a list of all spots sorted by freq 
                    print("DIGEST SPOT: New call  =",dx_call,'\tfreq=',freq,
                          '\tmode=',mode,'\tband=',band)
                    obj.cnt=1
                    P.SpotList.append( obj )
                    #                P.SpotList.sort(key=lambda x: x.frequency, reverse=False)

                    # Show only those spots on the list that are from the desired band
                    try:
                        if self.P.GUI_BAND=='MW':
                            BAND=DEFAULT_BAND = '20m'
                        else:
                            BAND = int( self.P.GUI_BAND.replace('m','') )
                    except:
                        error_trap('DIGEST SPOT: ?????')
                        print('band=',self.P.GUI_BAND)
                        self.lock.release()
                        return
                    
                    now = datetime.utcnow().replace(tzinfo=UTC)
                    if band==BAND:

                        # Cull out U.S. stations, except SESs (Useful for chasing DX)
                        dxcc = obj.dx_station.country
                        if self.P.DX_ONLY and dxcc=='United States' and len(obj.dx_call)>3:
                            self.lock.release()
                            return True

                        # Cull out stations not in North America (useful for NAQP for example)
                        cont = obj.dx_station.continent
                        #print('cont=',cont)
                        if self.P.NA_ONLY and cont!='NA':
                            self.lock.release()
                            return True

                        # Cull out stations non-cwops or cwops we've worked this year - useful for ACA
                        status=self.cwops_worked_status(obj.dx_call)
                        if self.P.NEW_CWOPS_ONLY and status!=1:
                            self.lock.release()
                            return True                    

                        # Cull out modes we are not interested in
                        xm = obj.mode
                        if xm in ['FT8','FT4','DIGITAL','JT65']:
                            xm='DIGI'
                        elif xm in ['SSB','LSB','USB','FM']:
                            xm='PH'
                        if xm not in self.P.SHOW_MODES:
                            #print('DIGEST SPOT: Culling',xm,'spot - ', self.P.SHOW_MODES)
                            self.lock.release()
                            return True

                        # Cull dupes
                        if not self.P.SHOW_DUPES:
                            if obj.color=='red':
                                self.lock.release()
                                return True
                    
                        # Find insertion point - This might be where the sorting problem is - if two stations have same freq?
                        idx2 = [i for i,x in enumerate(P.current) if x.frequency > freq]
                        if len(idx2)==0:
                            idx2=[len(P.current)];
                        if False:
                            print('INSERT: len(current)=',len(P.current))
                            print('freq=',freq,dx_call)
                            print('idx2=',idx2)
                            for cc in P.current:
                                print(cc.dx_call,cc.frequency)
                        P.current.insert(idx2[0], obj )

                        if self.P.CLUSTER=='WSJT':
                            df = int( obj.df )
                            entry="%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                                (df,dx_call,mode,cleanup(dxcc),obj.snr)
                        else:
                            if mode in ['CW']:
                                val = obj.wpm
                            else:
                                val = obj.snr
                            entry="%-6.1f  %-10.10s  %+6.6s %-15.15s %+4.4s" % \
                                (freq,dx_call,mode,cleanup(dxcc),val)
                        self.P.bm_q.put( [idx2[0], entry, obj.color] )

                # Release lock
                self.lock.release()
                
        if VERBOSITY>=1:
            print('DIGEST SPOT: nspots=',P.nspots,len(P.SpotList),len(P.current))
        return True

            

    # Function to check if we've already worked a spotted station
    def B4(self,x,b):
            
        VERBOSITY = self.P.DEBUG
        now = datetime.utcnow().replace(tzinfo=UTC)
        dx_call=x.dx_call.upper()
        nqsos=len(self.P.qsos)
        if VERBOSITY>0:
            print('B4: ... call=',dx_call,'\tband=',b,'nqsos=',nqsos)
        
        match=False
        if nqsos>0:
            for qso in self.P.qsos:
                #print('QSO=',qso)
                if self.P.CW_SS:
                    # Can only work each station once regardless of band in this contest
                    match = dx_call==qso['call']
                else:
                    try:
                        match = (dx_call==qso['call']) and (b==qso['band'])
                    except: 
                        error_trap('GUI->MATCH QSOS: ?????')
                        match=False
                        print('dx_call=',dx_call)
                        print('qso=',qso)

                if match:
                    t1 = datetime.strptime(now.strftime("%Y%m%d %H%M%S"), "%Y%m%d %H%M%S") 
                    t2 = datetime.strptime( qso['qso_date_off']+" "+qso["time_off"] , "%Y%m%d %H%M%S")
                    delta=(t1-t2).total_seconds() / 3600
                    match = delta < self.P.MAX_HOURS_DUPE
                    if VERBOSITY>=2:
                        print('--- Possible dupe ',tag,' for',dx_call,'\tt12=',t1,t2,'\tdelta=',
                              delta,match)
                    if match:
                        print('*** Dupe ***',qso['call'],qso['band'])
                        break

        return match


    def match_qsos(self,qso,x,b,now):
        VERBOSITY = self.P.DEBUG
        
        if self.P.CW_SS:
            # Can only work each station once regardless of band in this contest
            match = x.dx_call==qso['call']
        else:
            try:
                match = (x.dx_call==qso['call']) and (b==qso['band'])
            except:
                error_trap('GUI->MATCH QSOS: ?????')
                match=False
                print('dx_call=',x.dx_call)
                print('qso=',qso)
                
        #print('\n------MATCH_QSOS: qso=',qso,x.dx_call,match)
        if match:
            t1 = datetime.strptime(now.strftime("%Y%m%d %H%M%S"), "%Y%m%d %H%M%S") 
            t2 = datetime.strptime( qso['qso_date_off']+" "+qso["time_off"] , "%Y%m%d %H%M%S")
            delta=(t1-t2).total_seconds() / 3600
            match = delta< self.P.MAX_HOURS_DUPE
            if VERBOSITY>=2:
                print('--- MATCH_QSOS: Possible dupe for',x.dx_call,'\tt12',t1,t2,'\tdelta=',delta,match)

        return match


    def lb_update(self):
        P=self.P
        b = P.GUI_BAND
        print('LB_UPDATE: band =',b)

        # Acquire lock
        acq=self.lock.acquire(timeout=self.lock_to)
        if not acq:
            print('LB UPDATE: Unable to acquire lock - giving up!')
            return
        
        if len(P.current)==0:
            print('LB_UPDATE - Nothing to do.',P.current)
            self.lock.release()
            return

        idx=-1
        now = datetime.utcnow().replace(tzinfo=UTC)
        for x in P.current:
            idx+=1
            for qso in self.P.qsos:
                match = self.match_qsos(qso,x,b,now)
                call=qso['call']
                #print('LB_UPDATE:',call,x.dx_call,match)
                #match |= call==self.P.MY_CALL
                if match:
                    break
                
        if idx>=0:
            c,c2,age=self.spot_color(match,x)
            #self.lb.itemconfigure(idx, background=c)
            self.P.bm_q.put( [idx,None, c] )
            #print('LB_UPDATE:',dx_call,c)
                
        # Release lock
        self.lock.release()
                

    # Function to determine spot color
    def spot_color(self,match,x):
        P=self.P

        now = datetime.utcnow().replace(tzinfo=UTC)
        age = (now - x.time).total_seconds()/60      # In minutes
        dx_call=x.dx_call.upper()
        dx_station = Station(dx_call)
        
        # Try to strip out bogus appendices from state QPs - not very effective!
        homecall   = dx_station.homecall
        if dx_station.country=='United States' and len(dx_station.appendix)>=2:
            dx_call=homecall
        cwops_status=self.cwops_worked_status(dx_call)

        # Set color depending criteria
        # c2 is the abbreviated version used to shorten the inter-process messages 
        # These need to be matched in pySDR/gui.py
        if match:
            c="red"
            c2='r'
        elif x.new_mult and self.P.SHOW_MULTS:
            c='coral'
            c2='c'
        elif x.needed:
            c="magenta"
            c2='m'
        elif x.need_this_year:
            print('SPOT COLOR: call=',dx_call,'\tdxcc=',dx_station.country)
            c="violet"
            c2='v'
        elif x.need_mode:
            c="pink"
            c2='p'
        elif dx_call in P.friends or homecall in P.friends:
            c="lightskyblue" 
            c2='lb'
        elif dx_call in P.most_wanted:
            c="turquoise"
            c2='t'
        elif dx_call==self.P.MY_CALL:
            c="deepskyblue" 
            c2='b'
        elif self.P.CWOPS and cwops_status>0:
            if cwops_status==2:
                # Worked
                if x.new_mult and self.P.SHOW_MULTS:
                    c='coral'
                    c2='c'
                else:
                    c="gold"
                    c2='d'
            else:
                # Not worked
                c='orange'
                c2='o'
        elif dx_call in THIRTEEN_COLONIES and False:
            c="lightskyblue" 
            c2='lb'
        else:
            if age<2:
                c="yellow"
                c2='y'
            else:
                c="lightgreen"
                c2='g'

        return c,c2,age
    
    
    
    # Function to return worked status of cwops stations
    #   0 = call is not a cwops member
    #   1 = call is a cwops member but hasn't been worked yet this year
    #   2 = call is a cwops member and been worked yet this year
    def cwops_worked_status(self,dx_call):
        if '/' in dx_call:
            dx_station = Station(dx_call)
            home_call = dx_station.homecall
        else:
            home_call = dx_call

        if (dx_call in self.P.members) or (home_call in self.P.members):
            if (dx_call in self.P.data.cwops_worked) or (home_call in self.P.data.cwops_worked):
                status=2
            else:
                status=1
        else:
            status=0

        #print('CWops WORKED STATUS: call=',dx_call,'\thome call=',home_call,'\tworked=',status)
        return status

    
