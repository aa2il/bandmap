#########################################################################################
#
# cluster_feed.py - Rev. 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
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
from utilities import freq2band

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


# Function to test a telnet connection
def test_telnet_connection(tn):
    #print('tn=',tn,type(tn),isinstance(tn,SimpleServer))
    if not tn:
        print('File cluster_feed.py')
        print('TEST_TELNET_CONNECTION: *** ERROR *** Unexpected null connection')
        return False
    elif isinstance(tn,SimpleServer):
        return True    
    
    try:
        line=tn.read_very_eager().decode("utf-8")
        ntries=0
        while len(line)==0 and ntries<10:
            ntries+=1
            time.sleep(1)
            line=tn.read_very_eager().decode("utf-8")
        print('TEST TELNET CONNECTION - line=\n',line)
        if len(line)==0:
            print('TEST TELNET CONNECTION - No response - giving up')
            return False
    except EOFError:
        print("TEST TELNET CONNECTION - EOFerror: telnet connection is closed")
        return False

    return True

# Function to read and process spots from the telnet connection
def cluster_feed(self):
    #    print 'Cluster Feed ....'
    tn=self.tn
    lb=self.lb
    fp=self.fp
    VERBOSITY = self.P.DEBUG

    if self.nerrors>10:
        print('CLUSTER_FEED: Too many errors - giving up!')
        return False

    if self.P.TEST_MODE:

        # Read a line from the recorded spots file
        if not self.tn.closed:
            a=tn.readline()
            if a=='':
                print('---- EOF ----')
                tn.close()
                return False
            else:
#                line=a[2:]
                line=a
        else:
            line=''

    elif self.P.CLUSTER=='WSJT':

        spot = tn.get_spot2(None,0)
        line = tn.convert_spot(spot)
        if line:
            print('Cluster Feed: line=',line)

        # Check for band changes
        if tn.nsleep>=1 and True:
            band  = self.band.get()
            #logging.info("Calling Get band ...")
            frq2 = 1e-6*self.sock.get_freq(VFO=self.VFO)
            band2 = freq2band(frq2)
            #print('CLUSTER_FEED: band/band2=',band,band2)
            if band2==0 or not band2:
                print('CLUSTER_FEED: Current band=',band,'\t-\tRig band=',band2)
                tmp   = tn.last_band()
                #band2 = int( tmp[0:-1] )
                band2=tmp
            if band!=band2:
                print('CLUSTER_FEED: BAND.SET band2=',band2)
                self.band.set(band2)
                self.SelectBands()

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
                print('*** Error in CLUSTER_FEED ***')
                #print('Error msg:\t',getattr(e, 'message', repr(e)))
                print(e)
                line = ''
                self.nerrors+=1
                self.last_error=str(e)
            if VERBOSITY>=2:
                print('Line:',line)
            elif len(line)>0 and False:
                print('===> '+line.strip())
        else:
            return True
        
        if line=='': 
            #print 'CLUSTER FEED: Time out ',TIME_OUT
            return True                # Time out
        elif not "\n" in line:
            # Dont let timeout happen before we get entire line
            #print 'CLUSTER FEED: Partial line read'
            try:
                #line2 = tn.read_until(b"\n")
                line2 = tn.read_until(b"\n",timeout=10).decode("utf-8") 
                line = line+line2
            except Exception as e:
                print(e)
                print('*** TIME_OUT2 or other issue on CLUSTER_FEED ***')
                print(getattr(e, 'message', repr(e)))
                print('line  =',line,type(line))
                print('line2 =',line2,type(line2))
                return True                # Time out

    # Process the spot
    if len(line)>5:
        if self.P.ECHO_ON or VERBOSITY>=1:
            #print('>>> Cluster Feed:',line.rstrip())
            print('==> ',line.rstrip())
        if self.P.SAVE_SPOTS:
            fp.write(line.rstrip()+'\n')
            fp.flush()

        # Some clusters ask additional questions
        if line.find("Is this correct?")>=0:
            tn.write(b"Y\n")              # send "Y"
            return True

    # Check for logged contact
    if "<adif_ver" in line:
        print('\nCluster Feed: LOGGED Contact Detected ...')
        qso=parse_adif(-1,line)
        #print('qso=',qso)
        self.qsos.append( qso[0] )
        #print('self.qsos=',self.qsos)
        self.lb_update()
            
    obj = Spot(line)
    if self.P.ECHO_ON and True:
        #print('OBJ:')
        pprint(vars(obj))
    sys.stdout.flush()

    # Check if we got a new spot
    if not hasattr(obj, 'dx_call'):

        print('Not sure what to do with this: ',line.strip())

    else:

        dx_call=obj.dx_call

        # Reject FT8/4 spots if we're in a contest
        keep=True
        if self.P.CONTEST_MODE:
            if obj.mode in ['FT4','FT8']:
                keep=False

        # Reject calls that really aren't calls
        b = self.band.get()
        if keep:
            if not dx_call or len(dx_call)<=2 or not obj.dx_station: 
                keep=False
            elif not obj.dx_station.country and not obj.dx_station.call_suffix:
                keep=False

            # Filter out NCDXF beacons
            elif 'NCDXF' in line or '/B' in dx_call:
                if VERBOSITY>=1:
                    print('Ignoring BEACON:',line.strip())
                keep=False

        if False:
            print('CLUSTER FEED:',line.strip())
            print('keep=',keep,'\tb=',b)
        
        if keep:
            if dx_call==self.P.MY_CALL or (self.P.ECHO_ON and False):
                print('keep:',line.strip())

            # Highlighting in WSJT-X window
            if self.P.CLUSTER=='WSJT':
                for qso in self.qsos:
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
                    tn.highlight_spot(dx_call,fg,bg)
                    #print('CLUSTER FEED: call=',obj.dx_call,'\tsnr=',obj.snr,'\tfg/bg=',fg,bg,'\t',obj.snr.isnumeric(),int(obj.snr),len(obj.snr))

            # Pull out info from the spot
            freq=float( obj.frequency )
            mode=obj.mode
            band=obj.band
            self.nspots+=1

            dxcc=obj.dx_station.country
            if dxcc==None and False:
                print('\nDXCC=NONE!!!!')
                pprint(vars(obj.dx_station))
                sys.exit(0)
            now = datetime.utcnow().replace(tzinfo=UTC)
            year=now.year
            obj.needed = self.P.data.needed_challenge(dxcc,str(band)+'M',0)
            obj.need_this_year = self.P.data.needed_challenge(dxcc,year,0) and self.P.SHOW_NEED_YEAR

            if mode in ['CW']:
                mode2='CW'
            elif mode in ['SSB','LSB','USB','FM','PH']:
                mode2='Phone'
            elif mode in ['DIGITAL','FT8','FT4','JT65','PSK']:
                mode2='Data'
            else:
                mode2='Unknown'
            #print('BURP: call=',dx_call,'\tmode=',mode,mode2)
            obj.need_mode = self.P.data.needed_challenge(dxcc,mode2,0) and self.P.SHOW_NEED_MODE
                
            # Check if this call is already there
            # Need some error trapping here bx we seem to get confused sometimes
            try:
                b = self.band.get()
            except:
                b = ''

            try:
                idx1 = [i for i,x in enumerate(self.SpotList)
                        if x.dx_call==dx_call and x.band==band]  # indices of all matches
            except:
                idx1 = []

            if len(idx1)>0:

                # Call already in list - Update spot time
                if VERBOSITY>=2:
                    print("Found call:",idx1,dx_call)
                for i in idx1:
                    #print self.SpotList[i].dx_call,self.SpotList[i].time,obj.time
                    self.SpotList[i].time=obj.time

                # Update list box entry - In progress
                idx2 = [i for i,x in enumerate(self.current) if x.dx_call == dx_call and x.band==b]
                if len(idx2)>0 and True:
                    bgc = self.lb.itemcget(idx2[0], 'background')
                    #print '&&&&&&&&&&&&&&&&&&&&&& Modifying ',idx2[0],dx_call,bgc
                    #print lb.get(idx2[0])
                    lb.delete(idx2[0])
                    if self.P.CLUSTER=='WSJT':
                        df = obj.df
                        try:
                            df=int(df)
                            #print('Insert3')
                            lb.insert(idx2[0], "%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                                      (df,dx_call,mode,cleanup(dxcc),obj.snr))
                        except:
                            pass
                    else:
                        #print('Insert4')
                        lb.insert(idx2[0], "%-6.1f  %-10.19s  %+6.6s %-15.16s %+4.4s" % \
                                  (freq,dx_call,mode,cleanup(dxcc),obj.snr))
                    lb.itemconfigure(idx2[0], background=bgc)
                    
            else:
                    
                # New call - maintain a list of all spots sorted by freq 
                ##                print "New call",dx_call,freq,mode,band
                self.SpotList.append( obj )
                #                self.SpotList.sort(key=lambda x: x.frequency, reverse=False)

                # Show only those spots on the list that are from the desired band
                try:
                    BAND = int( self.band.get().replace('m','') )
                except:
                    print('CLUSTERFEDD Error - band=',self.band)
                    return
                now = datetime.utcnow().replace(tzinfo=UTC)
                if band==BAND:
                    dxcc = obj.dx_station.country

                    # Cull out U.S. stations, except SESs
                    if self.P.DX_ONLY and dxcc=='United States' and len(obj.dx_call)>3:
                        return True

                    # Find insertion point - This might be where the sorting probelm is - if two stations have same freq?
                    #self.current.append( obj )
                    #self.current.sort(key=lambda x: x.frequency, reverse=False)
                    idx2 = [i for i,x in enumerate(self.current) if x.frequency > freq]
                    if len(idx2)==0:
                        idx2=[len(self.current)];
                    if False:
                        print('INSERT: len(current)=',len(self.current))
                        print('freq=',freq,dx_call)
                        print('idx2=',idx2)
                        for cc in self.current:
                            print(cc.dx_call,cc.frequency)
                    self.current.insert(idx2[0], obj )

                    if self.P.CLUSTER=='WSJT':
                        df = int( obj.df )
                        lb.insert(idx2[0], "%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                                  (df,dx_call,mode,cleanup(dxcc),obj.snr))
                    else:
                        lb.insert(idx2[0], "%-6.1f  %-10.10s  %+6.6s %-15.15s %+4.4s" % \
                                  (freq,dx_call,mode,cleanup(dxcc),obj.snr))

                    # Change background colors on each list entry
                    if VERBOSITY>=1:
                        print('CLUSTER_FEED: Calling LB_COLORS ... band=',band)
                    self.lb_colors('B',idx2[0],now,str(band)+'m',obj)

    # Check if we need to cull old spots
    dt = (datetime.now() - self.last_check).total_seconds()/60      # In minutes
    # print "dt=",dt
    if dt>1:
        cull_old_spots(self)
                    
    #    print "nspots=",self.nspots,len(self.SpotList)
    return True

#########################################################################################

# Function to cull aged spots
def cull_old_spots(self):
    #logging.info("Calling Get_Freq ...")
    frq = self.sock.get_freq(VFO=self.VFO)
    print("Culling old spots ... Rig freq=",frq,flush=True)

    now = datetime.utcnow().replace(tzinfo=UTC)
    NewList=[];
    BAND = int( self.band.get().replace('m','') )
    for x in self.SpotList:
        try:
            age = (now - x.time).total_seconds()/60      # In minutes
        except:
            print("ERROR in CULL_OLD_SPOTS:")
            age=0
            print('x=',x)
            #pprint(vars(x))
            print('now=',now)
            #print('x.time=',x.time)
            continue
            
#        print x.time,now,age
        if age<self.P.MAX_AGE and x!=None:
            NewList.append(x)
        else:
            print("Removed spot ",x.dx_call,x.frequency,x.band," age=",age)
            if (not OLD_WAY) and x.band==BAND:
                idx2 = [i for i,y in enumerate(self.current) 
                        if y.frequency == x.frequency and y.dx_call == x.dx_call]
                #print("Delete",idx2,idx2[0])
                del self.current[idx2[0]]
                self.lb.delete(idx2[0])

    # Update gui display
    self.SpotList=NewList
    if OLD_WAY:
        self.SelectBands()
    self.last_check=datetime.now()
#    print self.last_check

