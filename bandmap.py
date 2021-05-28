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

import sys
import os
import re
import pytz
import time
import atexit
import socket
import argparse

from pytz import timezone
from datetime import datetime, date, tzinfo       #,time
from dx.spot_processing import Station, Spot, WWV, Comment, ChallengeData

if sys.version_info[0]==3:
    from tkinter import *
    import tkinter.font
else:
    from Tkinter import *
    import tkFont
    
from pprint import pprint
from operator import itemgetter
from dx.cluster_connections import *
from rig_io.socket_io import *
from adif import *
from collections import OrderedDict 
import webbrowser

#########################################################################################

# Sometimes when these don't work, its bx the login handshaking needs some work
NODES=OrderedDict()
NODES['PY3NZ'] = 'dxc.baependi.com.br:8000'        # DXWATCH.COM!!!
NODES['NK7Z']  = 'nk7z-cluster.ddns.net:7373'      # Lots of spots!  RBN?
NODES['NC7J']  = 'dxc.nc7j.com'                    # Lots of spots, no FT8
NODES['W8AEF'] = 'paul.w8aef.com:7373'             # AZ - no FT8 - can turn it on
NODES['W3LPL'] = 'w3lpl.net:7373'                  # Ok - lots of spots, no FT8 dxc.w3lpl.net
NODES['N6WS']  = 'n6ws.no-ip.org:7300'             # Ok
NODES['K1TTT'] = 'k1ttt.net:7373'                  # (Peru, MA); Skimmer capable
NODES['W6RFU'] = 'ucsbdx.ece.ucsb.edu:7300'        # Ok - CQ Zones 1-5 spots only (i.e. US & Canada)
NODES['K3LR']  = 'dx.k3lr.com'                     # Doesnt work
NODES['AE5E']  = 'dxspots.com'                     # Ok - not many spots
NODES['N4DEN'] = 'dxc.n4den.us:7373'               # Ok
NODES['W6KK']  = 'w6kk.zapto.org:7300'             # Ok - USA and VE spots only, not many spots
NODES['N7OD']  = 'n7od.pentux.net'                 # Ok
NODES['WC4J']  = 'dxc.wc4j.net'                    # Doesnt work
NODES['WA9PIE']  = 'dxc.wa9pie.net:8000'           # HRD
NODES['ANY']   = ''

##CLUSTER='dxc.k2ls.com'              # CQ Zones 1-8 spots only (i.e. NA) - not sure how to log in
##CLUSTER='w6cua.no-ip.org:7300'     # Not sure how to log on?
##CLUSTER='www.k7ek.net:9000'        # Doesn't work?
##CLUSTER='k6exo.dyndns.org:7300'     # Doesn't work?
##CLUSTER='n6ws.no-ip.org:7300'        # Not sure how to log on?
##CLUSTER='n7od.pentux.net'          # Not sure how to log on?

#NODES2=['WSJT','WSJT2','WSJT3','WSJT4','WSJT5','WSJT6','WSJT7',\
#        'WSJT34','WSJT44','WSJT54']

#print 'NODES=',NODES
#print NODES.keys()+NODES2
#sys.exit(0)

# Process command line args
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
                      default="/home/joea/logs/AA2IL.adif")
#                      default="/home/joea/.fldigi/logs/aa2il_2020.adif")
arg_proc.add_argument('-dx', action='store_true',help='Show only DX spots')
#arg_proc.add_argument('-noft8', action='store_true',help='Filter out FT8 spots')
arg_proc.add_argument('-test', action='store_true',help='Test Mode')
args = arg_proc.parse_args()

CONTEST_MODE = args.contest
TEST_MODE    = args.test
CW_SS        = args.ss
DX_ONLY      = args.dx

#LOG_DIR  = '/home/joea/.fldigi/logs/'
#LOG_NAME = LOG_DIR + args.log
LOG_NAME = args.log

CHALLENGE_FNAME = os.path.expanduser('~/Python/data/states.xls')

############################################################################################

# User params
UTC = pytz.utc
rootlogger = "dxcsucker"
DELAY=100
TIME_OUT=.01
OLD_WAY=True

#PARSE_LOG=True
#PARSE_LOG=False
PARSE_LOG=CONTEST_MODE and True

#FLDIGI_HOST = '127.0.0.1';
#FLDIGI_PORT = 7362;              # FLDIGI
#FLDIGI_PORT = 12345;              # FLRIG

# See     http://www.ng3k.com/misc/cluster.html            for a list 
SERVER=args.server.upper()
WSJT_FNAME=None

WSJT_IP_ADDRESS = '127.0.0.1'
WSJT_PORT = 2237
WSJT2=args.wsjt
if WSJT2!=None:
    print("\nWSJT2=",WSJT2,len(WSJT2))
    WSJT_FNAME=os.path.expanduser("~/.local/share/WSJT-X")
    WSJT_FNAME+=" - "+WSJT2[0]
    WSJT_FNAME+="/ALL.TXT"
    CLUSTER='WSJT'
    SERVER='WSJT'
    
    if len(WSJT2)>=2:
        WSJT_PORT = int(WSJT2[1])
        
    print("WSJT_FNAME=", WSJT_FNAME)
    print("WSJT_PORT =", WSJT_IP_ADDRESS,WSJT_PORT)
    #sys.exit(0)
else:
    CLUSTER=NODES[SERVER]
#print('CLUSTER=',CLUSTER)

if args.server=='WA9PIE' or True:
    ECHO_ON=True
else:
    ECHO_ON=False

if CLUSTER=='WSJT':
    MAX_AGE=5
else:
    MAX_AGE=15
    

#########################################################################################

# Init
fp=-1

def cleanup(dxcc):
    try:
        dxcc2=dxcc.replace('Republic of ','')
    except:
        dxcc2=dxcc
    return dxcc2

# Create gui
class BandMapGUI:
    def __init__(self,CLUSTER):

        # Create the GUI
        self.root = Tk()
        self.root.title("Band Map by AA2IL - " + SERVER)
        sz="400x1200"
        self.root.geometry(sz)

        # Init
        self.CLUSTER=CLUSTER
        self.nspots=0
        self.SpotList=[]
        self.current=[]
        self.last_check=datetime.now()
        self.qsos=[]

        # Set band according to rig freq
        self.band   = IntVar(self.root)
        self.ant    = IntVar(self.root)
        self.ant.set(-1)
        self.mode   = StringVar(self.root)
        self.mode.set('')
#        self.band.set(DEFAULT_BAND)
        b = sock.get_band()
        self.band.set(b)
        print("Initial band=",b)

        # Buttons
        BUTframe = Frame(self.root)
        BUTframe.pack()

        # Buttons to select HF bands
        for bb in list(bands.keys()):
            if bb=='2m':
                break
            b = int( bb.split("m")[0] )
            if not CONTEST_MODE or bands[bb]["CONTEST"]:
                Radiobutton(BUTframe, 
                            text=bb,
                            indicatoron = 0,
                            variable=self.band, 
                            command=lambda: self.SelectBands(True),
                            value=b).pack(side=LEFT,anchor=W)

        # Another row of buttons to select mode & antenna
        ModeFrame = Frame(self.root)
        ModeFrame.pack(side=TOP)
        Button(ModeFrame,text="Clear", \
               command=self.Clear_Spot_List ).pack(side=LEFT,anchor=W)
        if self.CLUSTER!='WSJT':
            Button(ModeFrame,text="Reset", \
                   command=self.Reset ).pack(side=LEFT,anchor=W)

        subFrame1 = Frame(ModeFrame)
        subFrame1.pack(side=LEFT)
        #for m in modes:
        for m in ['CW','Data','SSB','LSB','USB']:
            Radiobutton(subFrame1, 
                        text=m,
                        indicatoron = 0,
                        variable=self.mode, 
                        command=lambda: self.SelectMode(),
                        value=m).pack(side=LEFT,anchor=W)
        self.SelectMode('')

        subFrame2 = Frame(ModeFrame)
        subFrame2.pack(side=LEFT)
        for a in [1,2,3]:
            Radiobutton(subFrame2, 
                        text='Ant'+str(a),
                        indicatoron = 0,
                        variable=self.ant, 
                        command=lambda: self.SelectAnt(),
                        value=a).pack(side=LEFT,anchor=W)
        self.SelectAnt(-1)

        Button(ModeFrame,text="-1",
               command=lambda: self.FreqAdjust(-1) ).pack(side=LEFT,anchor=W)
        Button(ModeFrame,text="+1",
               command=lambda: self.FreqAdjust(+1) ).pack(side=LEFT,anchor=W)
        

        if CONTEST_MODE:
            Button(ModeFrame,text="<",
                   command=lambda: self.SetSubBand(1) ).pack(side=LEFT,anchor=W)
            Button(ModeFrame,text=">",
                   command=lambda: self.SetSubBand(3) ).pack(side=LEFT,anchor=W)

        # List box
        LBframe = Frame(self.root)
        LBframe.pack(side=LEFT,fill=BOTH,expand=1)

        scrollbar = Scrollbar(LBframe, orient=VERTICAL)

        if sys.version_info[0]==3:
            lb_font = tkinter.font.Font(family="monospace",size=10,weight="bold")
        else:
            lb_font = tkFont.Font(family="monospace",size=10,weight="bold")
        self.lb   = Listbox(LBframe, yscrollcommand=scrollbar.set,font=lb_font)
        scrollbar.config(command=self.lb.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.lb.pack(side=LEFT, fill=BOTH, expand=1)
        self.lb.bind('<<ListboxSelect>>', LBSelect)
#        self.lb.bind('<2>' if aqua else '<3>', lambda e: context_menu(e, menu))
        self.lb.bind('<Button-2>',LBCenterClick)
        self.lb.bind('<Button-3>',LBRightClick)

        # Open telnet connection to spot server
        logger = get_logger(rootlogger)
        print('SERVER=',SERVER)
        if SERVER=='ANY':
            KEYS=list(NODES.keys())
            print('NODES=',NODES)
            print('KEYS=',KEYS)

            self.tn=None
            inode=0
            while not self.tn:
                key = KEYS[inode]
                self.tn = connection(TEST_MODE,NODES[key],WSJT_FNAME,ip_addr=WSJT_IP_ADDRESS,port=WSJT_PORT)
                inode += 1
            self.root.title("Band Map by AA2IL - Server " + key )
            self.CLUSTER=NODES[key]
                
        else:
            self.tn = connection(TEST_MODE,CLUSTER,WSJT_FNAME,ip_addr=WSJT_IP_ADDRESS,port=WSJT_PORT)

        if not self.tn:
            print('Giving up')
            sys.exit(0)

        # And away we go
        self.Scheduler()
        self.WatchDog()

    # Adjust rig freq 
    def FreqAdjust(self,df):
        frq = sock.get_freq() / 1000.
        sock.set_freq(frq+df)

    # Set rig freq to lo or hi end of mode subband
    def SetSubBand(self,iopt):

        b = str( self.band.get() )+'m'
        m = sock.get_mode()
        if m=='AM':
            m='SSB'
        if iopt==1:
            print('m=',m)
            frq = bands[b][m+'1'] * 1000
        elif iopt==2:
            frq1 = bands[b][m+'1'] * 500
            frq2 = bands[b][m+'2'] * 500
            frq  = frq1+frq2
        elif iopt==3:
            frq = bands[b][m+'2'] * 1000
        print("\nSetSubBand:",iopt,b,m,frq)
        sock.set_freq(float(frq/1000.))

    # Callback to select antenna
    def SelectAnt(self,a=None):
        if not a:
            a  = self.ant.get()
        if a==-1:
            a = sock.get_ant()
            self.ant.set(a)
            #print "\n%%%%%%%%%% Select Antenna: Got Antenna =",a,"%%%%%%%%"
        else:
            print("\n%%%%%%%%%% Select Antenna: Setting Antenna =",a,"%%%%%%%%")
            sock.set_ant(a)

    # Callback to handle mode changes
    def SelectMode(self,m=None):
        #print('\nSelectMode:',m)
        if m==None:
            m = self.mode.get()
            print('SelectMode-a:',m)

        if m=='':
            m = sock.get_mode()
            #print('SelectMode-b:',m)
            if m=='RTTY' or m=='FT8' or m=='FT4' or m[0:3]=='PKT' or m=='DIGITIAL':
                m='Data'
            self.mode.set(m)
            return

        # Translate mode request into somthing FLDIGI understands
        #print('SelectMode-c:',m)
        if m=='SSB':
            #        buf=get_response(s,'w BY;EX1030\n');            # Audio from MIC (front)
            frq = sock.get_freq() / 1000.
            if frq<10000:
                m='LSB'
            else:
                m='USB'
        elif m=='Data' or m=='DIGITA':
            m='RTTY'
        #print("SelecteMode-d:",m)
        sock.set_mode(m)
        if False:
            sock.set_mode(m)
            m = sock.get_mode()
            print('SelectMode-e:',m)

    # Callback to handle band changes
    def SelectBands(self,allow_change=False):

        print('SELECT BANDS:')
        #try:
        band  = self.band.get()
        #except:
        #    print('SelectBands - Woops!')
        #    return
        band2 = sock.get_band()
        
        print("You've selected ",band,'m - Current rig band=',band2,"m",' - allow_change=',allow_change,flush=True)

        # Check for band change
        if allow_change and CLUSTER=='WSJT':
            b=str(band)+'m'
            if band != band2 and False:
                sock.set_band(b)
            new_frq = bands[b]['FT8'] + 1
            sock.set_freq(new_frq)
            sock.set_mode('FT8')

        # Extract a list of spots that are in the desired band
        if CONTEST_MODE:
            #for x in self.SpotList:
            #    print '-',x.mode,'-',x.mode!='FT8'
            if DX_ONLY:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band and \
                       x.dx_station.country!='United States' and x.mode!='FT8'] 
            else:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band and x.mode!='FT8'] 
        else:
            if DX_ONLY:
                # Retain only stations outside US or SESs
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band and \
                       (x.dx_station.country!='United States' or len(x.dx_call)==3) ] 
            else:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band]
            
        self.current = [self.SpotList[i] for i in idx]
        self.current.sort(key=lambda x: x.frequency, reverse=False)

        # Get latest logbook
        now = datetime.utcnow().replace(tzinfo=UTC)
        if PARSE_LOG:
            self.qsos = parse_adif(LOG_NAME)
            print('################################# QSOs in log=',len(self.qsos))
            #print('qsos=',self.qsos)
            print('qsos[0]=',self.qsos[0])
            #sys.exit(0)
        else:
            self.qsos = {}

        # Re-populate list box with spots from this band
        # This seems to be the slow part
        #print 'Repopulate ...',len(self.current),len(self.qsos)
        self.lb.delete(0, END)
        for x in self.current:
            #pprint(vars(x))
            dxcc=x.dx_station.country
            if CLUSTER=='WSJT':
                #print('Insert1')
                self.lb.insert(END, "%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                               (int(x.df),x.dx_call,x.mode,cleanup(dxcc),x.snr))
            else:
                #print('Insert2')
                self.lb.insert(END, "%-6.1f  %-10.19s  %+6.6s %-15.15s %+4.4s" % \
                               (x.frequency,x.dx_call,x.mode,cleanup(dxcc),x.snr))

            # Change background colors on each list entry
            self.lb_colors('A',END,now,band,x)


    # Change background colors on each list entry
    def lb_colors(self,tag,idx,now,band,x):
            
        match=False
        if PARSE_LOG:
            b=str(band)+'m'
            for qso in self.qsos:
                if CW_SS:
                    match = x.dx_call==qso['call']
                else:
                    try:
                        match = (x.dx_call==qso['call']) and (b==qso['band'])
                    except:
                        match=False
                        print('\n!@#$%^!&&*#^#^ MATCH ERROR',dx_call)
                        print('qso=',qso)
                        print('!@#$%^!&&*#^#^ MATCH ERROR\n')
                if match:
                    delta = datetime.strptime(now.strftime("%Y%m%d"), "%Y%m%d") - \
                            datetime.strptime(qso['qso_date_off']   , "%Y%m%d")
                    print('--- Possible dupe ',tag,' for',x.dx_call,'\tdelta=',delta,delta.days)
                    match = delta.days < 2
                    if match:
                        break

        age=None
        if match:
            print('*** Dupe ***',qso['call'],qso['band'])
            c="red"
        elif x.needed:
            c="magenta"
        elif x.need_this_year:
            c="violet"
        else:
            age = (now - x.time).total_seconds()/60      # In minutes
            if age<2:
                c="yellow"
            else:
                c="lightgreen"

        #print('@@@@@@@@@@@@@@@@ LB_COLORS:',tag,x.dx_call,c,age)
        self.lb.itemconfigure(idx, background=c)
                
        # Make sure the entry closest to the rig freq is visible
        #print '... Repopulated'
        self.LBsanity()

            
    # Make sure the entry closest to the rig freq is visible
    def LBsanity(self):

        # Dont bother if using as WSJT companion
        #if not CONTEST_MODE or CLUSTER=='WSJT':
        if CLUSTER=='WSJT':
            return

        # Dont bother if not on same band
        b1 = sock.get_band()      # Rig band
        b2 = self.band.get()
        #print 'LBSANITY:',b1,b2
        if b1!=b2:
            return

        # Get rig freq
        frq = sock.get_freq() / 1000.
        dfbest=1e9
        ibest=-1
        idx=0

        # Keep track of entry that is closest to current rig freq
        for x in self.current:
            df=abs( x.frequency-frq )
            #            print idx,x.frequency,frq,df,ibest
            if df<dfbest:
                dfbest=df
                ibest=idx
            idx=idx+1

        # Make sure its visible and highlight it
        if ibest>-1:
#            print "closest=",ibest,self.current[ibest].frequency
            self.lb.see(ibest)
            self.lb.selection_clear(0,END)
            if False:
                # This was problematic
                self.lb.selection_set(ibest)


    # Callback to reset telnet connection
    def Reset(self):
        print("--- Reset ---",self.CLUSTER)
        self.Clear_Spot_List()
        if self.tn:
            self.tn.close()
        self.tn = connection(TEST_MODE,self.CLUSTER,WSJT_FNAME)

    # Callback to clear all spots
    def Clear_Spot_List(self):
        global data
        self.nspots=0
        self.SpotList=[];
        self.current=[]
        self.lb.delete(0, END)
        
        data = ChallengeData(CHALLENGE_FNAME)
#        print "Howdy Ho!",self.nspots

    # Wrapper to schedule events to read the spots
    def Scheduler(self):
        OK = ClusterFeed(self)
        self.root.after(100, self.Scheduler)

    # Watch Dog 
    def WatchDog(self):
        #print 'Watch Dog...'
        
        # Check for antenna and mode changes
        self.SelectAnt(-1)
        self.SelectMode('')

        #self.root.update()
        self.root.update_idletasks()
        self.root.after(1*1000, self.WatchDog)

#########################################################################################

# Callback when an item in the listbox is selected
def LBSelect(evt):
    print('LBSelect: Left Click - tune rig to a spot')

    # Dont do it if we're running WSJT
    if CLUSTER=='WSJT':
        return
    
    # Note here that Tkinter passes an event object to onselect()
    w = evt.widget
    if len( w.curselection() ) > 0:
        index = int(w.curselection()[0])
        value = w.get(index)
        print('You selected item %d: "%s"' % (index, value))

        b=value.strip().split()
        if b[2]=='FT8' or b[2]=='FT4':
            b[0] = float(b[0])+1

        # Note - need to set freq first so get on right band, then set the mode
        print("LBSelect: Setting freq ",b[0])
        sock.set_freq(float(b[0]))
        if not CONTEST_MODE:
            print("LBSelect: Setting mode ",b[2])
            #sock.mode.set(b[2])
            bm.SelectMode(b[2])
            
        print("LBSelect: Setting call ",b[1])
        sock.set_call(b[1])

def LBRightClick(event):
    print('LBRightClick: QRZ?')

    index = event.widget.nearest(event.y)
    value = event.widget.get(index)
    print('You selected item %d: "%s"' % (index, value))

    b=value.strip().split()
    print("Looking up call: ",b[1])
        
    link = 'https://www.qrz.com/db/' + b[1]
    #webbrowser.open(link, new=2)
    webbrowser.open_new_tab(link)
    

def LBCenterClick(event):
    print('LBCenterClick: Delete an entry')

    index = event.widget.nearest(event.y)
    value = event.widget.get(index)
    b=value.strip().split()
    call=b[1]
    print('You selected item %d: "%s"' % (index, value,call))

    del bm.current[index]
    bm.lb.delete(index)

    idx=[]
    i=0
    for x in self.SpotList:
        if x.call==call:
            SpotList[i]=None
        else:
            i+=1
            
#########################################################################################

# Function to read and process spots from the telnet connection
def ClusterFeed(self):
    #    print 'ClusterFeed ....'
    tn=self.tn
    lb=self.lb

    if TEST_MODE:

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

    elif CLUSTER=='WSJT':

        spot = tn.get_spot2(None,0)
        line = tn.convert_spot(spot)
        if line:
            print(line)

        # Check for band changes
        if tn.nsleep>=1 and True:
            band  = self.band.get()
            band2 = sock.get_band()
            #print('CLUSTER_FEED: band/band2=',band,band2)
            if band2==0 or not band2:
                print('CLUSTER_FEED: Current band=',band,'\t-\tRig band=',band2)
                tmp   = tn.last_band()
                band2 = int( tmp[0:-1] )
            if band!=band2:
                print('CLUSTER_FEED: band2=',band2)
                self.band.set(band2)
                self.SelectBands()

        # Check for antenna changes
        #self.SelectAnt(-1)
                
    else:

        # Read a line from the telnet connection
        #print 'CLUSTER FEED: Reading tn...'
        if self.tn:
            try:
                line = tn.read_until(b"\n",TIME_OUT).decode("utf-8") 
            except Exception as e:
                print('*** TIME_OUT1 or other issue on CLUSTER_FEED ***')
                print(getattr(e, 'message', repr(e)))
                line = ''
        else:
            return True
        if line=='': 
            #print 'CLUSTER FEED: Time out ',TIME_OUT
            return True                # Time out
        elif not "\n" in line:
            # Dont let timeout happen before we get entire line
            #print 'CLUSTER FEED: Partial line read'
            try:
                line2 = tn.read_until("\n")
                line = line+line2
            except Exception as e:
                print('*** TIME_OUT2 or other issue on CLUSTER_FEED ***')
                print(getattr(e, 'message', repr(e)))
                return True                # Time out

    # Process the spot
    if len(line)>5:
        if ECHO_ON:
            print('>>>',line.rstrip())
        if not TEST_MODE and False:
            fp.write(line+'\n')
            fp.flush()

        # Some clusters ask additional questions
        if line.find("Is this correct?")>=0:
            tn.write("Y\n")              # send "Y"
            return True  
            
    obj = Spot(line)
    sys.stdout.flush()

    # Check if we got a new spot
    if hasattr(obj, 'dx_call'):

        dx_call=getattr(obj, "dx_call")

        # Reject FT8 spots if we're in a contest
        keep=True
        if CONTEST_MODE:
            mode = getattr(obj, "mode")
            if mode=='FT8':
                keep=False

        # Reject calls that really aren't calls
        if keep:
            if not dx_call or len(dx_call)<=2 or not obj.dx_station:
                keep=False
            elif not obj.dx_station.country and not obj.dx_station.call_suffix:
                keep=False

            # Filter out NCDXF beacons
            elif 'NCDXF' in line:
                print('Ignoring BEACON:',line)
                keep=False        
        
        if keep:
            if dx_call=="AA2IL":
                print(line.strip())
            
            freq=float( getattr(obj, "frequency") )
            mode=getattr(obj, "mode")
            band=getattr(obj, "band")
            self.nspots+=1

            dxcc=obj.dx_station.country
            if dxcc==None and False:
                print('\nDXCC=NONE!!!!')
                pprint(vars(obj.dx_station))
                sys.exit(0)
            obj.needed = data.needed_challenge(dxcc,str(band)+'M',0)
            obj.need_this_year = data.needed_challenge(dxcc,2020,0) and False
                
            # Check if this call is already there
            #print [x for x in SpotList if x.dx_call == dx_call]               # list of all matches
            #print any(x.dx_call == dx_call for x in SpotList)                 # if there is any matches

            ### JBA
            ###idx1 = [i for i,x in enumerate(self.SpotList) if x.dx_call == dx_call]  # indices of all matches
            try:
                b = self.band.get()
            except:
                b = 0
                
            idx1 = [i for i,x in enumerate(self.SpotList) if x.dx_call==dx_call and x.band==band]  # indices of all matches

            if len(idx1)>0:

                # Call already in list - Update spot time
                print("Found call:",idx1,dx_call)
                for i in idx1:
                    #print self.SpotList[i].dx_call,self.SpotList[i].time,obj.time
                    self.SpotList[i].time=obj.time

                # Update list box entry - In progress
                #b = self.band.get()
                idx2 = [i for i,x in enumerate(self.current) if x.dx_call == dx_call and x.band==b]
                if len(idx2)>0 and True:
                    bgc = self.lb.itemcget(idx2[0], 'background')
                    #print '&&&&&&&&&&&&&&&&&&&&&& Modifying ',idx2[0],dx_call,bgc
                    #print lb.get(idx2[0])
                    lb.delete(idx2[0])
                    if CLUSTER=='WSJT':
                        df = getattr(obj, "df")
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
                BAND = self.band.get()
                now = datetime.utcnow().replace(tzinfo=UTC)
                if band==BAND:
                    dxcc = obj.dx_station.country

                    # Cull out U.S. stations, except SESs
                    if DX_ONLY and dxcc=='United States' and len(obj.dx_call)>3:
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

                    if CLUSTER=='WSJT':
                        df = int( getattr(obj, "df") )
                        #print('Insert5')
                        lb.insert(idx2[0], "%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                                  (df,dx_call,mode,cleanup(dxcc),obj.snr))
                    else:
                        #print('Insert6')
                        lb.insert(idx2[0], "%-6.1f  %-10.10s  %+6.6s %-15.15s %+4.4s" % \
                                  (freq,dx_call,mode,cleanup(dxcc),obj.snr))

                    # Change background colors on each list entry
                    self.lb_colors('B',idx2[0],now,band,obj)

    # Check if we need to cull old spots
    dt = (datetime.now() - self.last_check).total_seconds()/60      # In minutes
    # print "dt=",dt
    if dt>1:
        cull_old_spots(self)
                    
    #    print "nspots=",self.nspots,len(self.SpotList)
    #print '.... ClusterFeed 2'
    return True

#########################################################################################

# Function to cull aged spots
def cull_old_spots(self):
    frq = sock.get_freq()
    print("Culling old spots ... Rig freq=",frq,flush=True)

    now = datetime.utcnow().replace(tzinfo=UTC)
    NewList=[];
    BAND = self.band.get()
    for x in self.SpotList:
        try:
            age = (now - x.time).total_seconds()/60      # In minutes
        except:
            print("ERROR in CULL_OLD_SPOTS:")
            age=0
            pprint(vars(x))
            print(now)
            print(x.time)
            
#        print x.time,now,age
        if age<MAX_AGE:
            NewList.append(x)
        else:
            print("Removed spot ",x.dx_call,x.frequency,x.band," age=",age)
            if (not OLD_WAY) and x.band==BAND:
                idx2 = [i for i,y in enumerate(self.current) 
                        if y.frequency == x.frequency and y.dx_call == x.dx_call]
                print("Delete",idx2,idx2[0])
                del self.current[idx2[0]]
                self.lb.delete(idx2[0])

    # Update gui display
    self.SpotList=NewList
    if OLD_WAY:
        self.SelectBands()
    self.last_check=datetime.now()
#    print self.last_check

#########################################################################################

# Begin executable
if __name__ == "__main__":

    print("\n\n***********************************************************************************")
    print("\nStarting Bandmap  ...")

    # Open a file to save all of the spots
    if not TEST_MODE and False:
        fp = open("/tmp/all_spots.dat","w")

    # Open xlmrpc connection to fldigi
    sock = open_rig_connection(args.rig,0,args.port,0,'BANDMAP')
    if not sock.active:
        print('*** No connection to rig ***')
    #sys,exit(0)

    # Create GUI 
    data = ChallengeData(CHALLENGE_FNAME)
    bm = BandMapGUI(CLUSTER)
    bm.root.mainloop()



