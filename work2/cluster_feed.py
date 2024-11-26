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
        P.q = queue.Queue(maxsize=0)

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

        P=self.P
        fp=self.fp
        VERBOSITY = self.P.DEBUG

        if VERBOSITY>=1:
            print('CLUSTER FEED A: nspots=',P.nspots,len(P.SpotList),len(P.current))

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
            self.digest_spot(line)
            
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



    # Function to read spots from the telnet connection
    def digest_spot(self,line):

        P=self.P
        #lb=P.bm_gui.lb
        VERBOSITY = self.P.DEBUG
            
        # Check for logged contact
        if "<adif_ver" in line:
            print('\nDIGEST SPOT: LOGGED Contact Detected ...')
            qso=parse_adif(-1,line)
            #print('qso=',qso)
            self.P.bm_gui.qsos.append( qso[0] )
            #print('self.qsos=',self.qsos)
            lb_update()

        if self.P.CLUSTER=='WSJT':
            print('SPOT:',line,len(line))
        obj = Spot(line)
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
            if dx_call==None:
                print('DIGEST SPOT: *** CORRECTION - blank call?????',dx_call)
                pprint(vars(obj))
            elif len(dx_call)<3:
                print('DIGEST SPOT: *** CORRECTION but dont know what to do - call=',dx_call)            
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
            keep=True
            m = self.P.bm_gui.mode.get()
            if self.P.CONTEST_MODE:
                if m=='CW' and obj.mode in ['FT4','FT8','DIGITAL']:
                    keep=False

            # Reject calls that really aren't calls
            b = self.P.bm_gui.band.get()
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

                # Highlighting in WSJT-X window
                if self.P.CLUSTER=='WSJT':
                    for qso in self.P.bm_gui.qsos:
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
                band=obj.band
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
            
                # Determine color for this spot
                match = self.B4(obj,str(band)+'m')
                c,c2,age=self.P.bm_gui.spot_color(match,obj)
                obj.color=c
                
                # Check if this call is already there
                # Need some error trapping here bx we seem to get confused sometimes
                try:
                    b = self.P.bm_gui.band.get()
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
                        #lb.delete(idx2[0])
                        self.P.q.put( [idx2[0]] )
                        if self.P.CLUSTER=='WSJT':
                            df = obj.df
                            try:
                                df=int(df)
                                entry="%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                                    (df,dx_call,mode,cleanup(dxcc),obj.snr)
                                self.P.q.put( [idx2[0], entry, obj.color] )
                            
                                i=idx[0]
                                P.current[i].time=obj.time
                                P.current[i].frequency=obj.frequency
                                P.current[i].snr=obj.snr
                                P.current[i].df=obj.df
                                P.current[i].color=obj.color
                            except:
                                error_trap('DIGEST SPOT: ?????')
                        else:
                            entry="%-6.1f  %-10.19s  %+6.6s %-15.16s %+4.4s" % \
                                (freq,dx_call,mode,cleanup(dxcc),obj.snr)
                            self.P.q.put( [idx2[0], entry, obj.color] )
                    
                else:
                    
                    # New call - maintain a list of all spots sorted by freq 
                    print("DIGEST SPOT: New call  =",dx_call,'\tfreq=',freq,
                          '\tmode=',mode,'\tband=',band)
                    P.SpotList.append( obj )
                    #                P.SpotList.sort(key=lambda x: x.frequency, reverse=False)

                    # Show only those spots on the list that are from the desired band
                    try:
                        BAND = int( self.P.bm_gui.band.get().replace('m','') )
                    except:
                        error_trap('DIGEST SPOT: ?????')
                        print('band=',self.P.bm_gui.band)
                        return
                    
                    now = datetime.utcnow().replace(tzinfo=UTC)
                    if band==BAND:

                        # Cull out U.S. stations, except SESs (Useful for chasing DX)
                        dxcc = obj.dx_station.country
                        if self.P.DX_ONLY and dxcc=='United States' and len(obj.dx_call)>3:
                            return True

                        # Cull out stations not in North America (useful for NAQP for example)
                        cont = obj.dx_station.continent
                        #print('cont=',cont)
                        if self.P.NA_ONLY and cont!='NA':
                            return True

                        # Cull out stations non-cwops or cwops we've worked this year - useful for ACA
                        status=self.P.bm_gui.cwops_worked_status(obj.dx_call)
                        if self.P.NEW_CWOPS_ONLY and status!=1:
                            return True                    

                        # Cull out modes we are not interested in
                        xm = obj.mode
                        if xm in ['FT8','FT4','DIGITAL','JT65']:
                            xm='DIGI'
                        elif xm in ['SSB','LSB','USB','FM']:
                            xm='PH'
                        if xm not in self.P.SHOW_MODES:
                            #print('DIGEST SPOT: Culling',xm,'spot - ', self.P.SHOW_MODES)
                            return True

                        # Cull dupes
                        if not self.P.SHOW_DUPES:
                            if obj.color=='red':
                                return True
                    
                        # Find insertion point - This might be where the sorting problem is - if two stations have same freq?
                        #P.current.append( obj )
                        #P.current.sort(key=lambda x: x.frequency, reverse=False)
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
                            entry="%-6.1f  %-10.10s  %+6.6s %-15.15s %+4.4s" % \
                                (freq,dx_call,mode,cleanup(dxcc),obj.snr)
                        self.P.q.put( [idx2[0], entry, obj.color] )
                    
        # Check if we need to cull old spots
        self.P.bm_gui.LBsanity()
        dt = (datetime.now() - self.P.bm_gui.last_check).total_seconds()/60      # In minutes
        if dt>1:
            self.P.bm_gui.cull_old_spots()
                    
        if VERBOSITY>=1:
            print('DIGEST SPOT: nspots=',P.nspots,len(P.SpotList),len(P.current))
        return True

            

    # Function to check if we've already worked a spotted station
    def B4(self,x,b):
            
        VERBOSITY = self.P.DEBUG
        now = datetime.utcnow().replace(tzinfo=UTC)
        dx_call=x.dx_call.upper()
        nqsos=len(self.P.bm_gui.qsos)
        if VERBOSITY>0:
            print('B4: ... call=',dx_call,'\tband=',b,'nqsos=',nqsos)
        
        match=False
        if nqsos>0:
            for qso in self.P.bm_gui.qsos:
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

    
