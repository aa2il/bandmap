#########################################################################################
#
# cluster_feed.py - Rev. 1.0
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

# Function to read spots from the telnet connection
def cluster_feed(self):
    tn=self.tn
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
            print('\nCluster Feed: line=',line)
        else:
            print('\nCluster Feed: Blank line=',line)
            print('spot=',spot)

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
            except:
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
                #line2 = tn.read_until(b"\n")
                line2 = tn.read_until(b"\n",timeout=10).decode("utf-8") 
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
            tn.write(b"Y\n")              # send "Y"
            return 0

    # Process the spot
    if len(line)>0:
        scrolling(self,'DIGEST SPOT A')
        digest_spot(self,line)
        scrolling(self,'DIGEST SPOT B')
    return 1

        
# Function to read spots from the telnet connection
def digest_spot(self,line):

    tn=self.tn
    lb=self.lb
    VERBOSITY = self.P.DEBUG
            
    # Check for logged contact
    if "<adif_ver" in line:
        print('\nCluster Feed: LOGGED Contact Detected ...')
        qso=parse_adif(-1,line)
        #print('qso=',qso)
        self.qsos.append( qso[0] )
        #print('self.qsos=',self.qsos)
        self.lb_update()

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
            print('CLUSTER_FEED: *** CORRECTION - blank call?????',dx_call)
            pprint(vars(obj))
        elif len(dx_call)<3:
            print('CLUSTER_FEED: *** CORRECTION but dont know what to do - call=',dx_call)            
        elif dx_call in self.corrections:
            print('CLUSTER_FEED: *** NEED A CORRECTION ***',dx_call)
            dx_call = self.corrections[dx_call]
            obj.dx_call = dx_call
        elif dx_call[0]=='T' and dx_call[1:] in self.members:
            dx_call = dx_call[1:]
            obj.dx_call = dx_call
        elif len(dx_call)>=7 and dx_call[-3:] in ['CWT','SST','MST']:
            dx_call = dx_call[:-3]
            obj.dx_call = dx_call

        # Reject FT8/4 spots if we're in a contest
        keep=True
        m = self.mode.get()
        if self.P.CONTEST_MODE:
            if m=='CW' and obj.mode in ['FT4','FT8','DIGITAL']:
                keep=False

        # Reject calls that really aren't calls
        b = self.band.get()
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
                    self.tn.highlight_spot(dx_call,fg,bg)
                    #print('CLUSTER FEED: call=',obj.dx_call,'\tsnr=',obj.snr,'\tfg/bg=',fg,bg,'\t',obj.snr.isnumeric(),int(obj.snr),len(obj.snr))

            # Pull out info from the spot
            freq=float( obj.frequency )
            mode=obj.mode
            band=obj.band
            self.nspots+=1
            print('CLUSTER FEED: call=',obj.dx_call,'\tfreq=',freq,'\tmode=',mode,'\tband=',band,'\tnspots=',self.nspots)

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
            c,c2,age=self.spot_color(match,obj)
            obj.color=c
                
            # Check if this call is already there
            # Need some error trapping here bx we seem to get confused sometimes
            try:
                b = self.band.get()
            except:
                b = ''

            try:
                # Indices of all matches
                idx1 = [i for i,x in enumerate(self.SpotList)
                        if x.dx_call==dx_call and x.band==band and x.mode==mode]
                #if x.dx_call==dx_call and x.band==band]
            except:
                idx1 = []

            if len(idx1)>0:

                # Call already in list - Update spot info
                #if VERBOSITY>=2:
                print("CLUSTER FEED: Dupe call =",dx_call,'\tfreq=',freq,
                      '\tmode=',mode,'\tband=',band,'\tidx1=',idx1)
                for i in idx1:
                    if VERBOSITY>=2:
                        print('CLUSTER FEED A i=',i,self.SpotList[i].dx_call,
                              '\ttime=',self.SpotList[i].time,obj.time,
                              '\tfreq=',self.SpotList[i].frequency,obj.frequency)
                    self.SpotList[i].time=obj.time
                    self.SpotList[i].frequency=obj.frequency
                    self.SpotList[i].snr=obj.snr
                    self.SpotList[i].color=obj.color
                    if self.P.CLUSTER=='WSJT':
                        self.SpotList[i].df=obj.df
                    if VERBOSITY>=2:
                        print('CLUSTER FEED B i=',i,self.SpotList[i].dx_call,
                              '\ttime=',self.SpotList[i].time,obj.time,
                              '\tfreq=',self.SpotList[i].frequency,obj.frequency)

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
                            
                            i=idx[0]
                            self.current[i].time=obj.time
                            self.current[i].frequency=obj.frequency
                            self.current[i].snr=obj.snr
                            self.current[i].df=obj.df
                            self.current[i].color=obj.color
                        except:
                            error_trap('DIGEST SPOT: ?????')
                    else:
                        #print('Insert4')
                        lb.insert(idx2[0], "%-6.1f  %-10.19s  %+6.6s %-15.16s %+4.4s" % \
                                  (freq,dx_call,mode,cleanup(dxcc),obj.snr))
                    #lb.itemconfigure(idx2[0], background=bgc)
                    lb.itemconfigure(idx2[0], background=obj.color)
                    #scrolling(self,'DIGEST SPOT C')
                    
            else:
                    
                # New call - maintain a list of all spots sorted by freq 
                print("CLUSTER FEED: New call  =",dx_call,'\tfreq=',freq,
                      '\tmode=',mode,'\tband=',band)
                self.SpotList.append( obj )
                #                self.SpotList.sort(key=lambda x: x.frequency, reverse=False)

                # Show only those spots on the list that are from the desired band
                try:
                    BAND = int( self.band.get().replace('m','') )
                except:
                    error_trap('DIGEST SPOT: ?????')
                    print('band=',self.band)
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

                    # Cull out modes we are not interested in
                    xm = obj.mode
                    if xm in ['FT8','FT4','DIGITAL','JT65']:
                        xm='DIGI'
                    elif xm in ['SSB','LSB','USB','FM']:
                        xm='PH'
                    if xm not in self.P.SHOW_MODES:
                        #print('CLUSTER_FEED: Culling',xm,'spot - ', self.P.SHOW_MODES)
                        return True

                    # Cull dupes
                    if not self.P.SHOW_DUPES:
                        if obj.color=='red':
                            return True
                    
                    # Find insertion point - This might be where the sorting problem is - if two stations have same freq?
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
                    try:
                        # This triggered an error sometime
                        lb.itemconfigure(idx2[0], background=obj.color)
                        #scrolling(self,'DIGEST SPOT D')
                    except:
                        error_trap('DIGET SPOT: Error in configuring item bg color ????')
                        print('idx=',idx)
                        print('OBJ:')
                        pprint(vars(obj))

    # Check if we need to cull old spots
    self.LBsanity()
    dt = (datetime.now() - self.last_check).total_seconds()/60      # In minutes
    # print "dt=",dt
    if dt>1:
        cull_old_spots(self)
                    
    if VERBOSITY>=1:
        print('CLUSTER FEED B: nspots=',self.nspots,len(self.SpotList),len(self.current))
    return True

#########################################################################################

# Debug routine for scrolling issues
def scrolling(self,txt,verbosity=0):
    #print('SCROLLING:',txt,verbosity)

    sb=self.scrollbar.get()
    sz=self.lb.size()
    yview=self.lb.yview()
    y=yview[0]
    
    idx=int( y*sz +0.5 )
    val=self.lb.get(min(max(idx,0),sz-1))
    if verbosity>0:
        print('SCROLLING:',txt+': sz=',sz,'\tyview=',yview,
              '\n\ty=',y,'\tidx=',idx,'\tval=',val)

    return y

    
# Function to cull aged spots
def cull_old_spots(self):
    #logging.info("Calling Get_Freq ...")
    now = datetime.utcnow().replace(tzinfo=UTC)
    frq = self.sock.get_freq(VFO=self.VFO)
    #print('SpotList=',self.SpotList)
    #print("CULL OLD SPOTS - Rig freq=",frq,'\tnspots=',self.nspots,len(self.SpotList),len(self.current),
    #      '\nmax age=',self.P.MAX_AGE,'\tnow=',now)
    print("CULL OLD SPOTS - Rig freq=",frq,
          '\tnspots=',self.nspots,
          '\tlen SpotList=',len(self.SpotList),
          '\tlen Current=',len(self.current),
          '\n\tmax age=',self.P.MAX_AGE,
          '\tnow=',now)

    scrolling(self,'CULL OLD SPOTS A')

    NewList=[];
    BAND = int( self.band.get().replace('m','') )
    for x in self.SpotList:
        try:
            age = (now - x.time).total_seconds()/60      # In minutes
        except:
            error_trap('CULL_OLD_SPOTS: ????')
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
            print("CULL OLD SPOTS - Removed spot ",x.dx_call,'\t',x.time,x.frequency,x.band," age=",age)
            if (not OLD_WAY) and x.band==BAND:
                idx2 = [i for i,y in enumerate(self.current) 
                        if y.frequency == x.frequency and y.dx_call == x.dx_call]
                #print("Delete",idx2,idx2[0])
                del self.current[idx2[0]]
                self.lb.delete(idx2[0])

    # Update gui display
    scrolling(self,'CULL OLD SPOTS B')
    self.SpotList=NewList
    if OLD_WAY:
        self.SelectBands()
    scrolling(self,'CULL OLD SPOTS C')
    print("CULL OLD SPOTS - New nspots=",self.nspots,
          '\tlen SpotList=',len(self.SpotList),
          '\tlen Current=',len(self.current))
    self.last_check=datetime.now()
#    print self.last_check

