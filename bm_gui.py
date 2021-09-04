#########################################################################################
#
# bmgui.py - Rev. 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui for dx cluster bandmap
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
import time
import socket
import argparse
import json

#from pytz import timezone
from datetime import datetime
from dx.spot_processing import ChallengeData

from pprint import pprint
from dx.cluster_connections import *
#from adif import *
from fileio import parse_adif
from collections import OrderedDict 
import webbrowser

if sys.version_info[0]==3:
    from tkinter import *
    import tkinter.font
else:
    from Tkinter import *
    import tkFont

from rig_io.ft_tables import bands
from cluster_feed import *
from settings import *
import logging               

#########################################################################################

MAX_DAYS_DUPE = 2   # 7    # Was 2
DEFAULT_BAND = 20
VERBOSITY=0

#########################################################################################

# Setup basic logging
logging.basicConfig(
    format="%(asctime)-15s [%(levelname)s] %(funcName)s:\t(message)s",
    level=logging.INFO)

# The GUI
class BandMapGUI:
    def __init__(self,P):

        # Init
        self.P = P
        self.nspots=0
        self.SpotList=[]
        self.current=[]
        self.last_check=datetime.now()
        self.qsos=[]
        self.sock=P.sock
        self.tn = P.tn
        self.VFO = P.RIG_VFO
        if self.P.FT4:
            self.FT_MODE='FT4'
        else:
            self.FT_MODE='FT8'
        self.Ready=False

        # Create the GUI - need to be able to distinguish between multiple copies of bandmap 
        self.root = Tk()
        if P.SERVER=="WSJT":
            self.root.title("Band Map by AA2IL - " + P.SERVER)
        else:
            self.root.title("Band Map by AA2IL - Server " + P.SERVER)
        sz="400x1200"
        self.root.geometry(sz)

        # Add menu bar
        if True:
            self.create_menu_bar()

        # Set band according to rig freq
        self.band   = IntVar(self.root)
        self.ant    = IntVar(self.root)
        self.ant.set(-1)
        self.mode   = StringVar(self.root)
        self.mode.set('')
        if self.sock.active:
            if VERBOSITY>0:
                logging.info("Calling Get band ...")
            b = self.sock.get_band(VFO=self.VFO)     # Query rig at startup
        else:
            b = DEFAULT_BAND              # No conenction so just default
        self.band.set(b)
        self.rig_band=b
        print("Initial band=",b)

        # Buttons
        BUTframe = Frame(self.root)
        BUTframe.pack()

        # Buttons to select HF bands
        for bb in list(bands.keys()):
            if bb=='2m':
                break
            b = int( bb.split("m")[0] )
            if not P.CONTEST_MODE or bands[bb]["CONTEST"]:
                Radiobutton(BUTframe, 
                            text=bb,
                            indicatoron = 0,
                            variable=self.band, 
                            command=lambda: self.SelectBands(self.P.ALLOW_CHANGES),
                            value=b).pack(side=LEFT,anchor=W)

        # Another row of buttons to select mode & antenna
        ModeFrame = Frame(self.root)
        ModeFrame.pack(side=TOP)
        if False:
            Button(ModeFrame,text="Clear", \
                   command=self.Clear_Spot_List ).pack(side=LEFT,anchor=W)
            if P.CLUSTER!='WSJT':
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
        

        if P.CONTEST_MODE:
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
        self.lb.bind('<<ListboxSelect>>', self.LBSelect)
#        self.lb.bind('<2>' if aqua else '<3>', lambda e: context_menu(e, menu))
        self.lb.bind('<Button-2>',self.LBCenterClick)
        self.lb.bind('<Button-3>',self.LBRightClick)

        # And away we go
        self.SelectBands(True)
        self.Scheduler()
        self.WatchDog()

    # Adjust rig freq 
    def FreqAdjust(self,df):
        if VERBOSITY>0:
            logging.info("Calling Get Freq ...")
        self.rig_freq = self.sock.get_freq(VFO=self.VFO) / 1000.
        if VERBOSITY>0:
            logging.info("Calling Set Freq ...")
        self.sock.set_freq(self.rig_freq+df,VFO=self.VFO)

    # Set rig freq to lo or hi end of mode subband
    def SetSubBand(self,iopt):

        b = str( self.band.get() )+'m'
        if VERBOSITY>0:
            logging.info("Calling Get Mode ...")
        m = self.sock.get_mode(VFO=self.VFO)
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
        if VERBOSITY>0:
            logging.info("Calling Set Freq ...")
        self.sock.set_freq(float(frq/1000.),VFO=self.VFO)

    # Callback to select antenna
    def SelectAnt(self,a=None):
        if not a:
            a  = self.ant.get()
        if a==-1:
            if VERBOSITY>0:
                logging.info("Calling Get Ant ...")
            a = self.sock.get_ant()
            self.ant.set(a)
            #print "\n%%%%%%%%%% Select Antenna: Got Antenna =",a,"%%%%%%%%"
        else:
            print("\n%%%%%%%%%% Select Antenna: Setting Antenna =",a,"%%%%%%%%")
            if VERBOSITY>0:
                logging.info("Calling Set Ant  ...")
            self.sock.set_ant(a,VFO=self.VFO)

    # Callback to handle mode changes
    def SelectMode(self,m=None):
        #print('\nSelectMode:',m)
        if m==None:
            m = self.mode.get()
            print('SelectMode-a:',m)

        if m=='':
            if VERBOSITY>0:
                logging.info("Calling Get Mode ...")
            m = self.sock.get_mode(VFO=self.VFO)
            #print('SelectMode-b:',m)
            if m=='RTTY' or m=='FT8' or m=='FT4' or m[0:3]=='PKT' or m=='DIGITIAL':
                m='Data'
            self.mode.set(m)
            return

        # Translate mode request into somthing FLDIGI understands
        #print('SelectMode-c:',m)
        if m=='SSB':
            #        buf=get_response(s,'w BY;EX1030\n');            # Audio from MIC (front)
            if VERBOSITY>0:
                logging.info("Calling Get Freq ...")
            self.rig_freq = self.sock.get_freq(VFO=self.VFO) / 1000.
            if self.rig_freq<10000:
                m='LSB'
            else:
                m='USB'
        elif m=='Data' or m=='DIGITAL':
            m='RTTY'
        #print("SelecteMode-d:",m)
        if VERBOSITY>0:
            logging.info("Calling Set Mode ...")
        self.sock.set_mode(m,VFO=self.VFO)

    # Callback to handle band changes
    def SelectBands(self,allow_change=False):

        print('SELECT BANDS:')
        band  = self.band.get()
        if VERBOSITY>0:
            logging.info("Calling Get Band ...")
        band2 = self.sock.get_band(VFO=self.VFO)
        
        print("You've selected ",band,'m - Current rig band=',band2,"m",\
              ' - allow_change=',allow_change,' - mode=',self.FT_MODE, \
              flush=True)

        # Check for band change
        if allow_change:
            b=str(band)+'m'
            if self.P.CLUSTER=='WSJT':
                self.P.tn.configure_wsjt(NewMode=self.FT_MODE)
                time.sleep(.1)
                new_frq = bands[b][self.FT_MODE] + 1
                if VERBOSITY>0:
                    logging.info("Calling Set Freq and Mode ...")
                self.sock.set_freq(new_frq,VFO=self.VFO)
                self.sock.set_mode(self.FT_MODE,VFO=self.VFO)
            else:
                if band != band2:
                    if VERBOSITY>0:
                        logging.info("Calling Set Mode ...")
                    self.sock.set_band(b,VFO=self.VFO)

            # Make sure antenna selection is correct also
            if self.P.sock.rig_type2=='FTdx3000':
                if b in ['80m']:
                    ant=3
                elif b in ['40m','20m','15m']:
                    ant=1
                elif b in ['30m','17m','12m','10m','6m']:
                    ant=2
                else:
                    ant=1
                self.P.sock.set_ant(ant,VFO=self.VFO)

        # Extract a list of spots that are in the desired band
        if self.P.CONTEST_MODE:
            #for x in self.SpotList:
            #    print '-',x.mode,'-',x.mode!='FT8'
            if self.P.DX_ONLY:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band and \
                       x.dx_station.country!='United States' and x.mode not in ['FT8','FT4'] ] 
            else:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band and x.mode not in ['FT8','FT4'] ] 
        else:
            if self.P.DX_ONLY:
                # Retain only stations outside US or SESs
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band and \
                       (x.dx_station.country!='United States' or len(x.dx_call)==3 or \
                        x.dx_call=='WM3PEN')] 
            else:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == band]
            
        self.current = [self.SpotList[i] for i in idx]
        self.current.sort(key=lambda x: x.frequency, reverse=False)

        # Get latest logbook
        now = datetime.utcnow().replace(tzinfo=UTC)
        if self.P.PARSE_LOG:
            self.qsos = parse_adif(self.P.LOG_NAME)
            print('################################# QSOs in log=',
                  len(self.qsos))
            if len(self.qsos)==0:
                self.P.PARSE_LOG=False
            #print('qsos=',self.qsos)
            #print('qsos[0]=',self.qsos[0])
            #sys.exit(0)
        #else:
        #    self.qsos = {}

        # Re-populate list box with spots from this band
        # This seems to be the slow part
        #print 'Repopulate ...',len(self.current),len(self.qsos)
        self.lb.delete(0, END)
        for x in self.current:
            #pprint(vars(x))
            dxcc=x.dx_station.country
            if self.P.CLUSTER=='WSJT':
                #print('Insert1')
                self.lb.insert(END, "%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                               (int(x.df),x.dx_call,x.mode,cleanup(dxcc),x.snr))
            else:
                #print('Insert2')
                self.lb.insert(END, "%-6.1f  %-10.19s  %+6.6s %-15.15s %+4.4s" % \
                               (x.frequency,x.dx_call,x.mode,cleanup(dxcc),x.snr))

            # Change background colors on each list entry
            self.lb_colors('A',END,now,band,x)


    def match_qsos(self,qso,x,b,now):
        if self.P.CW_SS:
            # Can only work each station once regardless of band in this contest
            match = x.dx_call==qso['call']
        else:
            try:
                match = (x.dx_call==qso['call']) and (b==qso['band'])
            except:
                match=False
                print('\n!@#$%^!&&*#^#^ MATCH ERROR',x.dx_call)
                print('qso=',qso)
                print('!@#$%^!&&*#^#^ MATCH ERROR\n')
                
        #print('\n------MATCH_QSOS: qso=',qso,x.dx_call,match)
        if match:
            delta = datetime.strptime(now.strftime("%Y%m%d"), "%Y%m%d") - \
                datetime.strptime(qso['qso_date_off']   , "%Y%m%d")
            print('--- MATCH_QSOS: Possible dupe for',x.dx_call,'\tdelta=',delta,delta.days)
            match = delta.days < MAX_DAYS_DUPE

        return match
    

    def lb_update(self):
        b = str(self.band.get())+'m'
        now = datetime.utcnow().replace(tzinfo=UTC)
        idx=-1
        for x in self.current:
            idx+=1
            for qso in self.qsos:
                match = self.match_qsos(qso,x,b,now)
                call=qso['call']
                print('LB_UPDATE:',call,x.dx_call,match)
                if match:
                    break

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
        self.lb.itemconfigure(idx, background=c)
                
                

    # Change background colors on each list entry
    def lb_colors(self,tag,idx,now,band,x):
            
        match=False
        #if self.P.PARSE_LOG:
        if len(self.qsos)>0:
            b=str(band)+'m'
            for qso in self.qsos:
                #print('QSO=',qso)
                if self.P.CW_SS:
                    # Can only work each station once regardless of band in this contest
                    match = x.dx_call==qso['call']
                else:
                    try:
                        match = (x.dx_call==qso['call']) and (b==qso['band'])
                    except Exception as e: 
                        print(e)
                        match=False
                        print('\n!@#$%^!&&*#^#^ MATCH ERROR',x.dx_call)
                        print('qso=',qso)
                        print('!@#$%^!&&*#^#^ MATCH ERROR\n')
                #print('\n------LB_COLORS: qso=',qso,x.dx_call,match)
                if match:
                    delta = datetime.strptime(now.strftime("%Y%m%d"), "%Y%m%d") - \
                            datetime.strptime(qso['qso_date_off']   , "%Y%m%d")
                    print('--- Possible dupe ',tag,' for',x.dx_call,'\tdelta=',
                          delta,delta.days,delta.days<MAX_DAYS_DUPE)
                    match = delta.days < MAX_DAYS_DUPE
                    if match:
                        print('MATCHED!!!')
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
        #logging.info("Calling LBsanity - band="+str(band)+" ...")
        self.LBsanity()
        print("")

            
    # Make sure the entry closest to the rig freq is visible
    def LBsanity(self):

        # Dont bother if using as WSJT companion
        #if not CONTEST_MODE or CLUSTER=='WSJT':
        if self.P.CLUSTER=='WSJT':
            return

        # Dont bother if not on same band as the rig
        b1 = self.rig_band
        b2 = self.band.get()
        #print 'LBSANITY:',b1,b2
        if b1!=b2:
            return

        # Get rig freq
        frq = self.rig_freq
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
        print("--- Reset ---",self.P.CLUSTER)
        self.Clear_Spot_List()
        if self.tn:
            self.tn.close()
        self.tn = connection(self.P.TEST_MODE,self.P.CLUSTER, \
                             self.P.MY_CALL,self.P.WSJT_FNAME)

    # Callback to clear all spots
    def Clear_Spot_List(self):
        self.nspots=0
        self.SpotList=[];
        self.current=[]
        self.lb.delete(0, END)
        
        self.P.data = ChallengeData(self.P.CHALLENGE_FNAME)
#        print "Howdy Ho!",self.nspots

    # Wrapper to schedule events to read the spots
    def Scheduler(self):
        OK = cluster_feed(self)
        self.root.after(100, self.Scheduler)

    # Watch Dog 
    def WatchDog(self):
        #print 'Watch Dog...'
        
        # Check for antenna or mode or band changes
        # Should combine these two
        if VERBOSITY>0:
            logging.info("Calling Get Band & Freq ...")
        if self.P.SERVER=="WSJT":
            tmp = self.tn.wsjt_status()
            #print('WatchDog:',tmp)
            if all(tmp):
                if not self.Ready:
                    print('WatchDog - Ready to go ....')
                    self.P.tn.configure_wsjt(NewMode=self.FT_MODE)
                    self.Ready=True

                self.rig_freq = tmp[0]
                self.rig_band = tmp[1]
                self.FT_MODE  = tmp[2]
            
        else:
            self.rig_band = self.sock.get_band(VFO=self.VFO)
            self.rig_freq = self.sock.get_freq(VFO=self.VFO) / 1000.

        self.SelectAnt(-1)
        self.SelectMode('')

        #self.root.update()
        self.root.update_idletasks()
        self.root.after(1*1000, self.WatchDog)

    #########################################################################################

    # Callback when an item in the listbox is selected
    def LBSelect(self,evt):
        print('LBSelect: Left Click - tune rig to a spot')

        # Note here that Tkinter passes an event object to onselect()
        w = evt.widget
        if len( w.curselection() ) > 0:
            index = int(w.curselection()[0])
            value = w.get(index)
            print('You selected item %d: "%s"' % (index, value))

            b=value.strip().split()
            if b[2]=='FT8' or b[2]=='FT4':
                b[0] = float(b[0])+1

            # If we're running WSJT, tune to a particular spot
            if self.P.CLUSTER=='WSJT':
                df = b[0]
                dx_call = b[1]
                #print('\n========================= LBSelect:',b,'\n')
                self.P.tn.configure_wsjt(RxDF=df,DxCall=dx_call)
                return

            # Note - need to set freq first so get on right band, then set the mode
            #rint("LBSelect: Setting freq ",b[0])
            if VERBOSITY>0:
                logging.info("Calling Set Freq ...")
            self.sock.set_freq(float(b[0]),VFO=self.VFO)
            if not self.P.CONTEST_MODE:
                print("LBSelect: Setting mode ",b[2])
                #self.sock.mode.set(b[2],VFO=self.VFO)
                self.SelectMode(b[2])
            
            print("LBSelect: Setting call ",b[1])
            self.sock.set_call(b[1])
            if self.P.UDP_CLIENT:
                self.P.udp_client.Send('Call:'+b[1])
                

            
    def LBRightClick(self,event):
        print('LBRightClick: QRZ?')

        index = event.widget.nearest(event.y)
        value = event.widget.get(index)
        print('You selected item %d: "%s"' % (index, value))

        b=value.strip().split()
        print("Looking up call: ",b[1])
        
        link = 'https://www.qrz.com/db/' + b[1]
        #webbrowser.open(link, new=2)
        webbrowser.open_new_tab(link)
    

    def LBCenterClick(self,event):
        print('LBCenterClick: Delete an entry')

        index = event.widget.nearest(event.y)
        value = event.widget.get(index)
        b=value.strip().split()
        call=b[1]
        print('You selected item %d: %s - %s' % (index,value,call))

        del self.current[index]
        self.lb.delete(index)

        idx=[]
        i=0
        for x in self.SpotList:
            if hasattr(x, 'dx_call'):
                dx_call=getattr(x, "dx_call")
                if dx_call==call:
                    self.SpotList[i]=None
                else:
                    i+=1
            
    #########################################################################################

    # For debug
    def donothing(self):
        win = Toplevel(self.root)
        button = Button(win, text="Do nothing button")
        button.pack()

    # Open dialog window for basic settings
    def Settings(self):
        self.SettingsWin = SETTINGS(self.root,self.P)
        return

    # Print out log
    def ShowLog(self):
        print('\nLOG::::::::::',self.P.PARSE_LOG)
        for qso in self.qsos:
            print(qso)
        print('')
        return

    # Select a new cluster
    def SelectNode(self):
        SERVER = self.node.get()
        print('SelectNode:',SERVER)
        if SERVER != self.P.SERVER:
            self.P.SERVER  = SERVER
            self.P.CLUSTER = self.P.NODES[SERVER]
            self.Reset()

    def toggle_dx_only(self):
        self.P.DX_ONLY=self.dx_only.get()
        print('TOGGLE BOGGLE',self.P.DX_ONLY)

    """
    # Not quite done with this yet
    def toggle_ft4(self):
        self.P.FT4=self.ft4.get()
        if self.P.FT4:
            self.FT_MODE='FT4'
        else:
            self.FT_MODE='FT8'
        print('TOGGLE BOGGLE',self.P.FT4,self.FT_MODE)
    """

    def create_menu_bar(self):
        print('Creating Menubar ...')
                   
        menubar = Menu(self.root)
        Menu1 = Menu(menubar, tearoff=0)
        Menu1.add_command(label="Clear", command=self.Clear_Spot_List)
        Menu1.add_command(label="Reset", command=self.Reset)

        self.dx_only = BooleanVar(value=self.P.DX_ONLY)
        Menu1.add_checkbutton(
            label="DX Only",
            underline=0,
            variable=self.dx_only,
            command=self.toggle_dx_only
        )
        
        """
        # Not quite done with this yet
        self.ft4 = BooleanVar(value=self.P.FT4)
        Menu1.add_checkbutton(
            label="FT4",
            underline=0,
            variable=self.ft4,
            command=self.toggle_ft4
        )
        """
        
        nodemenu = Menu(self.root, tearoff=0)
        self.node = StringVar(self.root)
        self.node.set(self.P.SERVER)
        #print( self.node.get() , self.P.SERVER )
        for node in list(self.P.NODES.keys()):
            nodemenu.add_radiobutton(label=node,
                                     value=node,
                                     variable=self.node,
                                     command=lambda: self.SelectNode() )
        
        Menu1.add_cascade(label="Nodes", menu=nodemenu)
        Menu1.add_separator()
        Menu1.add_command(label="Settings ...", command=self.Settings)
        Menu1.add_separator()
        Menu1.add_command(label="Show Log ...", command=self.ShowLog)
        Menu1.add_separator()
        Menu1.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="Cluster", menu=Menu1)

        self.root.config(menu=menubar)

