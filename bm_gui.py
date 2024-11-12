#########################################################################################
#
# gui.py - Rev. 1.0
# Copyright (C) 2021-4 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui for dx cluster bandmap.
#
#########################################################################################
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
import json
import platform

from datetime import datetime
from dx.spot_processing import ChallengeData,Station

from dx.cluster_connections import *
from fileio import parse_adif, read_text_file
import webbrowser

if sys.version_info[0]==3:
    from tkinter import *
    import tkinter.font
else:
    from Tkinter import *
    import tkFont

from rig_io import bands
from rig_io.ft_tables import THIRTEEN_COLONIES
from cluster_feed import *
from settings import *
import logging               
from utilities import freq2band, error_trap
from widgets_tk import StatusBar
from tcp_server import open_udp_client,KEYER_UDP_PORT
from bm_udp import *

#########################################################################################

DEFAULT_BAND = '20m'
VERBOSITY=0

#########################################################################################

# Setup basic logging
logging.basicConfig(
    format="%(asctime)-15s [%(levelname)s] %(funcName)s:\t(message)s",
    level=logging.INFO)

#########################################################################################

# The GUI
class BandMapGUI:
    def __init__(self,root,P):

        # Init
        self.P = P
        self.nspots=0
        self.SpotList=[]
        self.current=[]
        self.last_check=datetime.now()
        self.qsos=[]
        self.VFO = P.RIG_VFO
        if self.P.FT4:
            self.FT_MODE='FT4'
        else:
            self.FT_MODE='FT8'
        self.Ready=False
        self.nerrors=0
        self.enable_scheduler=True
        self.last_error=''
        self.friends=[]
        self.most_wanted=[]
        self.corrections=[]
        P.members=[]
        self.calls1 = []
        self.sock = None
        self.old_mode = None

        # UDP stuff
        P.bm_udp_client=None
        P.bm_udp_ntries=0

        # Open a file to save all of the spots
        if P.SAVE_SPOTS:
            self.fp = open("all_spots.dat","w")
        else:
            self.fp=-1

        # Read "regular" logbook - need to update this
        # Might need to bring this out to bandmap.py
        if self.P.CWOPS and False:
            if True:
                print('\nCWops members worked:\n',self.P.data.cwops_worked)
                self.calls1 = []
                #sys.exit(0)
            elif '_6' in self.P.LOG_NAME:
                # For CQP
                fname99=self.P.LOG_NAME.replace('_6','')
                print('GUI: Reading regular log file',fname99)
                logbook = parse_adif(fname99)
                self.calls1 = [ qso['call'] for qso in logbook ]
                self.calls1 =list( set( self.calls1) )
            elif True:
                # After the CQP
                fname99=self.P.LOG_NAME.replace('.','_6.')
                print('GUI: Reading regular log file',fname99)
                logbook = parse_adif(fname99)
                self.calls1 = [ qso['call'] for qso in logbook ]
                self.calls1 =list( set( self.calls1) )
            else:
                self.calls1 = []
            print('GUI: CALLS1=',self.calls1,len(self.calls1))
            
        # Create the GUI - need to be able to distinguish between multiple copies of bandmap 
        if root:
            self.root=Toplevel(root)
            #self.hide()
        else:
            self.root = Tk()
            
        if P.SERVER=="WSJT":
            self.root.title("Band Map by AA2IL - " + P.SERVER)
        else:
            self.root.title("Band Map by AA2IL - Server " + P.SERVER)

        # Move to lower left corner of screen
        if P.BM_GEO==None:
            self.screen_width = self.root.winfo_screenwidth()
            self.screen_height = self.root.winfo_screenheight()
            print('Screen=',self.screen_width, self.screen_height)
            w=400
            h=self.screen_height
            sz=str(w)+'x'+str(h)+'+'+str(self.screen_width-400)+'+0'
        else:
            #bandmap.py -geo 400x790+1520+240
            sz=P.BM_GEO
        self.root.geometry(sz)

        # Add menu bar
        self.create_menu_bar()

        # Set band according to rig freq
        self.band   = StringVar(self.root)
        self.ant    = IntVar(self.root)
        self.ant.set(-1)
        self.mode   = StringVar(self.root)
        self.mode.set('')
        self.mode2   = StringVar(self.root)
        self.mode2.set(self.FT_MODE)
        
        # Buttons
        BUTframe = Frame(self.root)
        BUTframe.pack()

        # Buttons to select HF bands
        self.Band_Buttons=[]
        for bb in bands.keys():
            if bb=='2m':
                break
            b = int( bb.split("m")[0] )
            but=Radiobutton(BUTframe, 
                            text=bb,
                            indicatoron = 0,
                            variable=self.band, 
                            command=lambda: self.SelectBands(self.P.ALLOW_CHANGES),
                            value=bb)
            self.Band_Buttons.append( but )
                
            if not P.CONTEST_MODE or bands[bb]["CONTEST"]:
                but.pack(side=LEFT,anchor=W)

        # Another row of buttons to select mode & antenna
        #ModeFrame = Frame(self.root)
        #ModeFrame.pack(side=TOP)
        #subFrame1 = Frame(ModeFrame,relief=RIDGE,borderwidth=2)
        subFrame1 = Frame(self.toolbar,relief=FLAT,borderwidth=2,bg='red')
        subFrame1.pack(side=LEFT)
        if P.SERVER=="WSJT":
            for m in ['FT8','FT4','MSK144']:
                Radiobutton(subFrame1, 
                            text=m,
                            indicatoron = 0,
                            variable=self.mode2, 
                            command=lambda: self.SelectMode2(),
                            value=m).pack(side=LEFT,anchor=W)

        else:
            for m in ['CW','Data','SSB']:
                Radiobutton(subFrame1, 
                            text=m,
                            indicatoron = 0,
                            variable=self.mode, 
                            command=lambda: self.SelectMode(),
                            value=m).pack(side=LEFT,anchor=W)

        #subFrame2 = Frame(ModeFrame)
        subFrame2 = Frame(self.toolbar,relief=FLAT,borderwidth=2,bg='green')
        subFrame2.pack(side=LEFT)
        for a in [1,2,3]:
            Radiobutton(subFrame2, 
                        text='Ant'+str(a),
                        indicatoron = 0,
                        variable=self.ant, 
                        command=lambda: self.SelectAnt(),
                        value=a).pack(side=LEFT,anchor=W)

        if False:
            frm=ModeFrame
        else:
            frm=self.toolbar
            #frm=Frame(self.toolbar,relief=RIDGE,borderwidth=1)
            #frm.pack(side=LEFT)
        Button(frm,text="-1",
               command=lambda: self.FreqAdjust(-1) ).pack(side=LEFT,anchor=W)
        Button(frm,text="+1",
               command=lambda: self.FreqAdjust(+1) ).pack(side=LEFT,anchor=W)
        

        if P.CONTEST_MODE:
            Button(frm,text="<",
                   command=lambda: self.SetSubBand(1) ).pack(side=LEFT,anchor=W)
            Button(frm,text=">",
                   command=lambda: self.SetSubBand(3) ).pack(side=LEFT,anchor=W)

        # List box with a scroll bar
        self.LBframe = Frame(self.root)
        #self.LBframe.pack(side=LEFT,fill=BOTH,expand=1)
        self.LBframe.pack(fill=BOTH,expand=1)
        self.scrollbar = Scrollbar(self.LBframe, orient=VERTICAL)

        # Select a fixed-space font
        if platform.system()=='Linux':
            FAMILY="monospace"
        elif platform.system()=='Windows':
            #FAMILY="fixed"             # Doesn't come out fixed space?!
            FAMILY="courier"
        else:
            print('GUI INIT: Unknown OS',platform.system())
            sys.exit(0)
        if self.P.SMALL_FONT:
            SIZE=8
        else:
            SIZE=10 
        if sys.version_info[0]==3:
            self.lb_font = tkinter.font.Font(family=FAMILY,size=SIZE,weight="bold")
        else:
            self.lb_font = tkFont.Font(family=FAMILY,size=SIZE,weight="bold")
        self.lb   = Listbox(self.LBframe, yscrollcommand=self.scrollbar.set,font=self.lb_font)
        self.scrollbar.config(command=self.lb.yview)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        self.lb.pack(side=LEFT, fill=BOTH, expand=1)
        self.lb.bind('<<ListboxSelect>>', self.LBLeftClick)
#        self.lb.bind('<2>' if aqua else '<3>', lambda e: context_menu(e, menu))
        self.lb.bind('<Button-2>',self.LBCenterClick)
        self.lb.bind('<Button-3>',self.LBRightClick)

        # Trap the mouse wheel pseudo-events so we can handle them properly
        self.lb.bind('<Button-4>',self.scroll_updown)
        self.lb.bind('<Button-5>',self.scroll_updown)          
        self.scrollbar.bind('<Button-4>',self.scroll_updown)   
        self.scrollbar.bind('<Button-5>',self.scroll_updown)   

        # Status bar along the bottom
        self.status_bar = StatusBar(self.root)
        self.status_bar.setText("Howdy Ho!")
        self.status_bar.pack(fill=X,side=BOTTOM)
        
        # Make what we have so far visible
        self.root.update_idletasks()
        self.root.update()

        # Open spot server
        self.open_spot_server()
        

    # Function to actually get things going        
    def run(self):
    
        self.tn   = self.P.tn
        self.sock = self.P.sock

        # Put gui on proper desktop
        if self.P.DESKTOP!=None:
            cmd='wmctrl -r "'+self.root.title()+'" -t '+str(self.P.DESKTOP)
            os.system(cmd)

        if self.sock and self.sock.active:
            if VERBOSITY>0:
                logging.info("Calling Get band ...")
            f = 1e-6*self.sock.get_freq(VFO=self.VFO)     # Query rig at startup
            b = freq2band(f)
            self.rig_freq = 1e-3*f
        else:
            f = 0
            b = DEFAULT_BAND              # No conenction so just default
        print('BM_GUI: BAND.SET band=',b,'\tf=',f)
        self.band.set(b)
        self.rig_band=b
        print("Initial band=",b)
        
        if self.sock and self.sock.active:
            self.SelectMode('')
            self.SelectAnt(-1)
            self.SelectBands(True)
        
        print('Initial server=',self.P.SERVER)
        self.node.set(self.P.SERVER)
        
        self.Scheduler()
        self.WatchDog()


    # Callback to handle mouse wheel scrolling since Tk doesn't seem to do a very good job of it
    # The jumps in Tk are much to big and I can't figure out how to adjust so do this instead
    def scroll_updown(self, event):
        if event.num==4:
            n=-1   # int(-1*(event.delta/120))
        else:
            n=1   # int(-1*(event.delta/120))
        #print('MOUSE WHEEL ...........................................................................................',
        #      n,event.num,event.delta,'\n',event)
        self.lb.yview_scroll(n, "units")
        return "break"
        
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
        if self.sock==None:
            return

        b = self.band.get()
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
    def SelectAnt(self,a=None,b=None,VERBOSITY=0):
        if self.sock==None:
            print('SELECT ANT - No socket!')
            return
        
        if not a:
            a  = self.ant.get()
        if a==-1:
            
            if VERBOSITY>0:
                logging.info("Calling Get Ant ...")
                print("SELECT ANT: Calling Get Ant ...")
            a = self.sock.get_ant()
            self.ant.set(a)
            if VERBOSITY>0:
                print("SELECT ANT: Got Antenna =",a)
                
        elif a==-2:
            if VERBOSITY>0:
                logging.info("Checking Ant matches Band ...")
            if self.P.sock.rig_type2=='FTdx3000':
                if b in ['160m','80m']:
                    ant=3
                elif b in ['40m','20m','15m']:
                    ant=1
                elif b in ['30m','17m','12m','10m','6m']:
                    ant=2
                else:
                    ant=1
                self.P.sock.set_ant(ant,VFO=self.VFO)
                
        else:
            print("\n%%%%%%%%%% Select Antenna: Setting Antenna =",a,"%%%%%%%%")
            if VERBOSITY>0:
                logging.info("Calling Set Ant  ...")
            self.sock.set_ant(a,VFO=self.VFO)
            self.status_bar.setText("Selecting Antenna "+str(a))

    # Callback to handle mode changes for WSJT-X
    def SelectMode2(self,VERBOSITY=0):
        if VERBOSITY>0:
            print('\nSelectMode2: mode=',self.FT_MODE)

        if self.sock==None:
            print('SELECT MODE2 - No socket!')
            return
        
        try:
            self.FT_MODE=self.mode2.get()
            band = self.band.get()
            frq = bands[band][self.FT_MODE] + 1
        except:
            error_trap('GUI->SELECT MODE2: Problem setting new config')
            return
            
        print('\n***************************************** Well well well ...',self.FT_MODE,band,frq)
        self.P.tn.configure_wsjt(NewMode=self.FT_MODE)
        time.sleep(.1)
        self.sock.set_freq(frq,VFO=self.VFO)

        # Make sure monitor is turned on also
        GAIN=25
        self.sock.set_monitor_gain(25)
        
        return

    # Callback to handle mode changes for rig
    def SelectMode(self,m=None,VERBOSITY=0):
        if VERBOSITY>0:
            print('\nSelectMode: mode=',m)
            
        if self.sock==None:
            print('SELECT MODE - No socket!')
            return
        
        if m==None:
            m = self.mode.get()
            print('SelectMode-a: mode2=',m)

        if m=='':
            if VERBOSITY>0:
                logging.info("Calling Get Mode ...")
            m = self.sock.get_mode(VFO=self.VFO)
            #print('SelectMode:',m)
            if m==None:
                return
            if m=='RTTY' or m=='FT8' or m=='FT4' or m[0:3]=='PKT' or m=='DIGITIAL':
                m='Data'
            self.mode.set(m)
            if m!=self.old_mode:
                self.status_bar.setText("Mode Select: "+str(m))
                self.old_mode=m
            return

        # Translate mode request into something that FLDIGI understands
        #print('SelectMode-c:',m)
        if m in ['SSB','LSB','USB']:
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
        if not self.P.CONTEST_MODE:
            self.sock.set_mode(m,VFO=self.VFO,Filter='Auto')
            if m=='CW':
                self.sock.set_if_shift(0)

    # Function to collect spots for a particular band
    def collect_spots(self,band,REVERSE=False,OVERRIDE=False):

        print('COLLECT_SPOTS: band=',band,'\tReverse=',REVERSE,
              '\tOVERRIDE=',OVERRIDE,'\tCONTEST_MODE=', self.P.CONTEST_MODE)

        if 'cm' in band:
            iband=int( band.replace('cm','') )
        else:
            iband=int( band.replace('m','') )

        spots=[]
        for x in self.SpotList:
            keep= x and x.band == iband
            if self.P.DX_ONLY:
                # Retain only stations outside US or SESs
                keep = keep and (x.dx_station.country!='United States' or len(x.dx_call)==3 or \
                                 x.dx_call=='WM3PEN') 
            if self.P.NA_ONLY:
                # Retain only stations in North America
                keep = keep and x.dx_station.continent=='NA'

            if self.P.NEW_CWOPS_ONLY:
                # Retain only cwops stations not worked yet this year
                keep = keep and self.cwops_worked_status(x.dx_call)==1

            # Retain only modes we are interested in
            xm = x.mode
            if xm in ['FT8','FT4','DIGITAL','JT65']:
                xm='DIGI'
            elif xm in ['SSB','LSB','USB','FM']:
                xm='PH'
            #if keep and (xm not in self.P.SHOW_MODES):
            #    print('COLLECT_SPOTS: Culling',xm,'spot - ', self.P.SHOW_MODES)
            keep = keep and (xm in self.P.SHOW_MODES)

            # Check for dupes
            if keep:
                match = self.B4(x,band)
                c,c2,age=self.spot_color(match,x)
                x.color=c
                if not (self.P.SHOW_DUPES or OVERRIDE):
                    keep = keep and (c2!='r')
                #print('COLLECT SPOTS:',x.dx_call,c,c2,keep,band,match)
                #print('\tx.color=',x.color)

            # Keep spots that haven't been culled
            if keep:
                spots.append(x)
            
        spots.sort(key=lambda x: x.frequency, reverse=REVERSE)

        return spots


                
    # Callback to handle band changes
    def SelectBands(self,allow_change=False):

        VERBOSITY = self.P.DEBUG
        #VERBOSITY = 1
        if VERBOSITY>0:
            print('SELECT BANDS A: nspots=',self.nspots,
                  '\tlen SpotList=',len(self.SpotList),
                  '\tlen Current=',len(self.current))

        scrolling(self,'SELECT BANDS A')

        if not self.sock:
            print('\nGUI->SELECT BANDS: Not sure why but no socket yet ????')
            print('\tsock=',self.sock,'\n')
            #return
        
        try:
            band  = self.band.get()
        except:
            error_trap('GUI->SELECT BANDS: ????')
            print('\tband=',self.band)
            return
        
        if VERBOSITY>0:
            logging.info("Calling Get Band ...")
        if self.sock:
            frq2 = 1e-6*self.sock.get_freq(VFO=self.VFO)
        else:
            frq2=0
        band2 = freq2band(frq2)
        self.status_bar.setText("Band Select: "+str(band))
        
        print("You've selected ",band,' - Current rig band=',band2,\
              ' - allow_change=',allow_change,' - mode=',self.FT_MODE, \
              flush=True)

        # Check for band change
        if allow_change:
            b=band
            if self.P.CLUSTER=='WSJT':
                print('BM_GUI - Config WSJT ...',b,self.FT_MODE)
                self.P.tn.configure_wsjt(NewMode=self.FT_MODE)
                time.sleep(.1)
                try:
                    new_frq = bands[b][self.FT_MODE] + 1
                except:
                    error_trap('GUI->SELECT BANDS: Problem getting freq')
                    return
                if VERBOSITY>0:
                    logging.info("Calling Set Freq and Mode ...")
                print('SELECT BANDS: Setting freq=',new_frq,'and mode=',self.FT_MODE)
                if self.sock:
                    self.sock.set_freq(new_frq,VFO=self.VFO)
                    self.sock.set_mode(self.FT_MODE,VFO=self.VFO)
            else:
                if band != band2 and self.sock:
                    if VERBOSITY>0:
                        logging.info("Calling Set Band ...")
                    self.sock.set_band(band,VFO=self.VFO)

            # Make sure antenna selection is correct also
            self.SelectAnt(-2,band)
            
        # Extract a list of spots that are in the desired band
        self.current = self.collect_spots(band)
        y=scrolling(self,'SELECT BANDS B')
        
        # Get latest logbook
        now = datetime.utcnow().replace(tzinfo=UTC)
        if self.P.PARSE_LOG and len(self.qsos)==0:
            if self.P.LOG_NAME0:
                # Log for operator if different from current callsign
                # We won't keep reading this file so we set REVISIT=False
                print('\nGUI: Reading log file',self.P.LOG_NAME0)
                logbook = parse_adif(self.P.LOG_NAME0,REVISIT=False,verbosity=0)
                self.qsos += logbook
                print('QSOs in log=',len(logbook),len(self.qsos))

            # Log for current callsign
            # We will keep reading this file for new QSOs so we set REVISIT=True
            print('\nGUI: Reading log file',self.P.LOG_NAME)
            logbook = parse_adif(self.P.LOG_NAME,REVISIT=True,verbosity=0)
            self.qsos += logbook
            print('QSOs in log=',len(logbook),len(self.qsos))
            #sys.exit(0)

        if self.P.CWOPS:
            self.calls = self.calls1 + [ qso['call'] for qso in self.qsos ]
            self.calls=list( set( self.calls) )
            print('No. unique calls worked:',len(self.calls))
            #print(self.calls)
            
        # Re-populate list box with spots from this band
        # This seems to be the slow part
        #print 'Repopulate ...',len(self.current),len(self.qsos)
        self.lb.delete(0, END)
        n=0
        for x in self.current:
            #pprint(vars(x))
            dxcc=x.dx_station.country
            if self.P.CLUSTER=='WSJT':
                #print('Insert1')
                self.lb.insert(END, "%4d  %-10.10s  %+6.6s %-17.17s %+4.4s" % \
                               (int(x.df),x.dx_call,x.mode,cleanup(dxcc),x.snr))
            else:
                #print('Insert2')
                if x.mode=='CW':
                    val=x.wpm
                else:
                    #val=x.snr
                    val=''
                self.lb.insert(END, "%-6.1f  %-10.19s  %+6.6s %-15.15s %+4.4s" % \
                               (x.frequency,x.dx_call,x.mode,cleanup(dxcc),val))

            # JBA - Change background colors on each list entry
            self.lb.itemconfigure(END, background=self.current[n].color)
            n+=1

        # Reset lb view
        self.LBsanity()
        self.lb.yview_moveto(y)
        scrolling(self,'SELECT BANDS C')
        if VERBOSITY>0:
            print('SELECT BANDS B: nspots=',self.nspots,
                  '\tlen SpotList=',len(self.SpotList),
                  '\tlen Current=',len(self.current))

            
    def match_qsos(self,qso,x,b,now):
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
        
    # Function to determine spot color
    def spot_color(self,match,x):

        now = datetime.utcnow().replace(tzinfo=UTC)
        age = (now - x.time).total_seconds()/60      # In minutes
        dx_call=x.dx_call.upper()
        dx_station = Station(dx_call)
        if dx_station.country=='United States' and len(dx_station.appendix)>=2:
            dx_call=dx_station.homecall            # Strip out bogus appendices from state QPs
        cwops_status=self.cwops_worked_status(dx_call)

        # Set color depending criteria
        # c2 is the abbreviated version used to shorten the inter-process messages 
        # These need to be matched in pySDR/gui.py
        if match:
            c="red"
            c2='r'
        elif x.needed:
            c="magenta"
            c2='m'
        elif x.need_this_year:
            c="violet"
            c2='v'
        elif x.need_mode:
            c="pink"
            c2='p'
        elif dx_call in self.friends:
            c="lightskyblue" 
            c2='lb'
        elif dx_call in self.most_wanted:
            c="turquoise"
            c2='t'
        elif dx_call==self.P.MY_CALL:
            c="deepskyblue" 
            c2='b'
        elif self.P.CWOPS and cwops_status>0:
            if cwops_status==2:
                c="gold"
                c2='d'
            else:
                c='orange'
                c2='o'
        elif dx_call in THIRTEEN_COLONIES:
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
    
    
    # Why is this still around? - see cluster_feed.py
    def lb_update(self):
        b = self.band.get()
        print('LB_UPDATE: b=',b)
        now = datetime.utcnow().replace(tzinfo=UTC)
        idx=-1
        if len(self.current)==0:
            print('LB_UPDATE - Nothing to do.',self.current)
            return
        for x in self.current:
            idx+=1
            for qso in self.qsos:
                match = self.match_qsos(qso,x,b,now)
                call=qso['call']
                #print('LB_UPDATE:',call,x.dx_call,match)
                #match |= call==self.P.MY_CALL
                if match:
                    break
        #else:
        #    print('LB_UPDATE - Nothing to do.',self.current)
        #    return

        if idx>=0:
            c,c2,age=self.spot_color(match,x)
            self.lb.itemconfigure(idx, background=c)
            #print('LB_UPDATE:',dx_call,c)
                

    # Function to check if we've already worked a spotted station
    def B4(self,x,b):
            
        now = datetime.utcnow().replace(tzinfo=UTC)
        dx_call=x.dx_call.upper()
        nqsos=len(self.qsos)
        if VERBOSITY>0:
            print('B4: ... call=',dx_call,'\tband=',b,'nqsos=',nqsos)
        
        match=False
        if nqsos>0:
            for qso in self.qsos:
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

            

    # Function to set list box view
    def set_lbview(self,frq,MIDDLE=False):
        
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

            sb=self.scrollbar.get()
            sz=self.lb.size()
            yview=self.lb.yview()
            """
            print("LBSANITY: Closest=",ibest,
                  '\tf=',self.current[ibest].frequency,
                  '\tsize=',sz,
                  '\tsb=',sb,
                  '\tyview',yview)
            """
            #print('hght:',self.lb['height'])

            # Use to scrollbar to determine how many lines are visible
            d = yview[1]-yview[0]             # Fraction of list in view
            n = d*sz                          # No. line in view
            if MIDDLE:
                y = max( ibest*d/n - d/2. , 0)    # Top coord so view will be centered around ibest
            else:
                y = max( ibest*d/n , 0)           # Top coord will be centered around ibest
            self.lb.yview_moveto(y)

            self.lb.selection_clear(0,END)
            if False:
                # This was problematic
                self.lb.selection_set(ibest)
    
            
    # Make sure the entry closest to the rig freq is visible
    def LBsanity(self):
        VERBOSITY = self.P.DEBUG
        #print('LBSANITY ...')

        # Dont bother if using as WSJT companion
        #if not CONTEST_MODE or CLUSTER=='WSJT':
        if self.P.CLUSTER=='WSJT':
            print('LBSANITY - WS server - nothing to do')
            return

        # Don't bother if not on same band as the rig
        b1 = self.rig_band
        b2 = self.band.get()
        #print('LBSANITY: rig band=',b1,'\tband=',b2)
        if b1!=b2:
            if VERBOSITY>0:
                print('LBSANITY - Rig on different band - nothing to do')
            return

        # Don't bother if user doesn't want to keep rig freq centered
        if not self.P.KEEP_FREQ_CENTERED:
            #if VERBOSITY>0:
            #    print('LBSANITY - DONT KEEP CENTERED - nothing to do')

            y=scrolling(self,'LBSANITY',verbosity=0)
            self.lb.yview_moveto(y)
            
            return

        # Set lb view so its centered around the rig rig freq
        frq = self.rig_freq
        self.set_lbview(frq,True)


    # Callback to reset telnet connection
    def Reset(self):
        print("\n------------- Reset -------------",self.P.CLUSTER,'\n')
        self.status_bar.setText("RESET - "+self.P.CLUSTER)
        self.Clear_Spot_List()
        if self.P.BM_UDP_CLIENT and self.P.bm_udp_client and False:
            self.P.bm_udp_client.StartServer()
        if self.P.BM_UDP_CLIENT and self.P.bm_udp_server and False:
            self.P.bm_udp_server.StartServer()
        if self.tn:
            self.tn.close()
            self.enable_scheduler=False
            time.sleep(.1)
            
        try:
            self.tn = connection(self.P.TEST_MODE,self.P.CLUSTER, \
                                 self.P.MY_CALL,self.P.WSJT_FNAME)
            print("--- Reset --- Connected to",self.P.CLUSTER, self.enable_scheduler)
            OK=test_telnet_connection(self.tn)
        except:
            error_trap('GUI->RESET: Problem connecting to node'+self.P.CLUSTER)
            OK=False
            
        if not OK:
            print('--- Reset --- Now what Sherlock?!')
            self.status_bar.setText('Lost telnet connection?!')
        if not self.enable_scheduler or True:
            self.enable_scheduler=True
            self.nerrors=0
            self.Scheduler()

    # Callback to clear all spots
    def Clear_Spot_List(self):
        print("\n------------- Clear Spot List -------------",self.P.CLUSTER,'\n')
        self.nspots=0
        self.SpotList=[];
        self.current=[]
        self.lb.delete(0, END)

        # JBA - MEM??? - Why are we re-reading this???? Disable and see what happens
        if False:
            self.P.data = ChallengeData(self.P.CHALLENGE_FNAME)

    # Wrapper to schedule events to read the spots
    def Scheduler(self):
        n = cluster_feed(self)
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
            
        if self.enable_scheduler:
            self.root.after(dt, self.Scheduler)   

    #########################################################################################

    # Watch Dog 
    def WatchDog(self):
        print('BM WATCH DOG ...')
        
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
            try:
                if self.sock:
                    self.rig_freq = 1e-3*self.sock.get_freq(VFO=self.VFO)
                    self.rig_band = freq2band(1e-3*self.rig_freq)
            except:
                error_trap('WATCHDOG: Problem reading rig freq/band',True)

        try:
            if self.sock:
                self.SelectAnt(-1,VERBOSITY=0)
                self.SelectMode('',VERBOSITY=0)
        except:
            error_trap('WATCHDOG: Problem reading rig antenna/mode',True)

       # Try to connect to the keyer
        if self.P.BM_UDP_CLIENT:
            if not self.P.bm_udp_client:
                self.P.bm_udp_ntries+=1
                if self.P.bm_udp_ntries<=100:
                    self.P.bm_udp_client=open_udp_client(self.P,KEYER_UDP_PORT,
                                                      bm_udp_msg_handler)
                    if self.P.bm_udp_client:
                        print('BM GUI->WatchDog: Opened connection to KEYER.')
                        self.P.bm_udp_ntries=0
                else:
                    print('WATCHDOG: Unable to open UDP client (keyer) - too many attempts',self.P.bm_udp_ntries)

        # Check if socket is dead
        if self.sock and self.sock.ntimeouts>=10:
            print('\tWATCHDOG: *** Too many socket timeouts - port is probably closed - giving up -> sys.exit ***\n')
            sys.exit(0)

        # Re-schedule to do it all over again in 1-second
        self.root.update_idletasks()
        self.root.update()
        self.root.after(1*1000, self.WatchDog)

    #########################################################################################

    # Callback when an item in the listbox is selected
    def LBSelect(self,value,vfo):
        print('LBSelect: Tune rig to a spot - vfo=',vfo,value)
        self.status_bar.setText("Spot Select "+value)
        scrolling(self,'LBSelect')

        # Examine item that was selected
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
        # We do a second set freq since rig may offset by 700 Hz if we are in CW mode
        # There must be a better way to do this but this is what we do for now
        #print("LBSelect: Setting freq ",b[0])
        print("LBSelect: Setting freq=',b[0],'on VFO',vfo,'\tmode=',b[2].'\tcall ",b[1])
        if VERBOSITY>0:
            logging.info("Calling Set Freq ...")
        if self.sock:
            self.sock.set_freq(float(b[0]),VFO=vfo)
            if not self.P.CONTEST_MODE:
                print("LBSelect: Setting mode ",b[2])
                self.SelectMode(b[2])
                self.sock.set_freq(float(b[0]),VFO=vfo)            
            self.sock.set_call(b[1])

        # Make sure antenna selection is correct also
        band=freq2band(0.001*float(b[0]))
        self.SelectAnt(-2,band)

        # Send spot info to keyer
        if self.P.BM_UDP_CLIENT and self.P.bm_udp_client:
            self.P.bm_udp_client.Send('Call:'+b[1]+':'+vfo)

            
    def LBLeftClick(self,event):
        print('LBLeftClick ...')
        w=event.widget
        if len( w.curselection() ) > 0:
            index = int(w.curselection()[0])
            value = w.get(index)
            print('You selected item %d: "%s"' % (index, value))
            self.LBSelect(value,self.P.RIG_VFO)
        
    def LBRightClick(self,event):
        print('LBRightClick ...')
        index = event.widget.nearest(event.y)
        value = event.widget.get(index)
        print('You selected item %d: "%s"' % (index, value))
        self.status_bar.setText("Right Click "+value)

        #print(self.P.RIGHT_CLICK_TUNES_VFOB,self.P.SERVER)

        if not self.P.RIGHT_CLICK_TUNES_VFOB or self.P.SERVER=="WSJT":

            # This used to trigger a qrz call lookup
            b=value.strip().split()
            print("Looking up call: ",b[1])
        
            link = 'https://www.qrz.com/db/' + b[1]
            webbrowser.open_new_tab(link)

        else:

            # Tune VFO-B to spot freq
            print("Tuning VFO B to ",value)
            self.LBSelect(value,'B')
    

    def LBCenterClick(self,event):
        print('LBCenterClick: Delete an entry')

        index = event.widget.nearest(event.y)
        value = event.widget.get(index)
        b=value.strip().split()
        call=b[1]
        print('You selected item %d: %s - %s' % (index,value,call))
        self.status_bar.setText("Spot Delete "+value)

        del self.current[index]
        self.lb.delete(index)

        #print('\nCENTER CLICK B4:',len(self.SpotList),self.SpotList)
        idx=[]
        i=0
        for i in range(len(self.SpotList)):
            x=self.SpotList[i]
            if hasattr(x, 'dx_call') and x.dx_call==call:
                idx.append(i)
        idx.reverse()
        #print('idx=',idx)
        for i in idx:
            x=self.SpotList.pop(i)
        #print('\nCENTER CLICK AFTER:',len(self.SpotList),self.SpotList)
            
    #########################################################################################

    # For debug
    def donothing(self):
        win = Toplevel(self.root)
        button = Button(win, text="Do nothing button")
        button.pack()

    # Open dialog window for basic settings
    def Settings(self):
        self.SettingsWin = SETTINGS_GUI(self.root,self.P)
        return

    # Print out log
    def ShowLog(self):
        print('\nLOG::::::::::',self.P.PARSE_LOG)
        for qso in self.qsos:
            print(qso)
        print(' ')
        return

    # Select a new cluster
    def SelectNode(self):
        SERVER = self.node.get()
        print('SelectNode:',SERVER)
        if SERVER != self.P.SERVER:
            self.P.SERVER  = SERVER
            self.P.CLUSTER = self.P.NODES[SERVER]
            self.root.title("Band Map by AA2IL - Server " + SERVER)
            self.Reset()
            self.node.set(self.P.SERVER)

    # Toggle DX ONLY mode
    def toggle_dx_only(self):
        self.P.DX_ONLY=self.dx_only.get()
        self.SelectBands()

    # Toggle NA ONLY mode
    def toggle_na_only(self):
        self.P.NA_ONLY=self.na_only.get()
        self.SelectBands()

    # Toggle NEW CWOPS ONLY mode
    def toggle_new_cwops_only(self):
        self.P.NEW_CWOPS_ONLY=self.new_cwops_only.get()
        print('TOGGLE CWOPS: ',self.P.NEW_CWOPS_ONLY)
        self.SelectBands()
        
    # Toggle showing CW spots
    def toggle_cw(self):
        self.P.SHOW_CW=self.show_cw.get()
        print('TOGGLE CW: BEFORE show_cw=',self.P.SHOW_CW,'\t',self.P.SHOW_MODES)
        if self.P.SHOW_CW:
            self.P.SHOW_MODES.append('CW')
        else:
            self.P.SHOW_MODES.remove('CW')
        print('TOGGLE CW: AFTER  show_cw=',self.P.SHOW_CW,'\t',self.P.SHOW_MODES)
        self.SelectBands()
        self.status_bar.setText("Showing modes "+' '.join(self.P.SHOW_MODES))
        
    # Toggle showing RTTY spots
    def toggle_rtty(self):
        self.P.SHOW_RTTY=self.show_rtty.get()
        print('TOGGLE RTTY: BEFORE show_rtty=',self.P.SHOW_RTTY,'\t',self.P.SHOW_MODES)
        if self.P.SHOW_RTTY:
            self.P.SHOW_MODES.append('RTTY')
        else:
            self.P.SHOW_MODES.remove('RTTY')
        print('TOGGLE RTTY: AFTER  show_rtty=',self.P.SHOW_RTTY,'\t',self.P.SHOW_MODES)
        self.SelectBands()
        self.status_bar.setText("Showing modes "+' '.join(self.P.SHOW_MODES))
        
    # Toggle showing DIGI spots
    def toggle_digi(self):
        self.P.SHOW_DIGI=self.show_digi.get()
        print('TOGGLE DIGI: BEFORE show_digi=',self.P.SHOW_DIGI,'\t',self.P.SHOW_MODES)
        if self.P.SHOW_DIGI:
            self.P.SHOW_MODES.append('DIGI')
        else:
            self.P.SHOW_MODES.remove('DIGI')
        print('TOGGLE DIGI: AFTER  show_digi=',self.P.SHOW_DIGI,'\t',self.P.SHOW_MODES)
        self.SelectBands()
        self.status_bar.setText("Showing modes "+' '.join(self.P.SHOW_MODES))
        
    # Toggle showing PHONE spots
    def toggle_phone(self):
        self.P.SHOW_PHONE=self.show_phone.get()
        print('TOGGLE PHONE: BEFORE show_phone=',self.P.SHOW_PHONE,'\t',self.P.SHOW_MODES)
        if self.P.SHOW_PHONE:
            self.P.SHOW_MODES.append('PH')
        else:
            self.P.SHOW_MODES.remove('PH')
        print('TOGGLE PHONE: AFTER  show_phone=',self.P.SHOW_PHONE,'\t',self.P.SHOW_MODES)
        self.SelectBands()
        self.status_bar.setText("Showing modes "+' '.join(self.P.SHOW_MODES))
        
    # Toggle showing of needs for mode
    def toggle_need_mode(self):
        self.P.SHOW_NEED_MODE=self.show_need_mode.get()

    # Toggle keep freq centered
    def toggle_keep_centered(self):
        self.P.KEEP_FREQ_CENTERED=self.center_freq.get()

    # Toggle right click tunes VFO B
    def toggle_right_click_tunes_vfob(self):
        self.P.RIGHT_CLICK_TUNES_VFOB=self.right_click_tunes_vfob.get()

    # Toggle font used in list box
    def toggle_small_font(self):
        self.P.SMALL_FONT=self.small_font.get()
        if self.P.SMALL_FONT:
            SIZE=8
        else:
            SIZE=10 
        self.lb_font.configure(size=SIZE)
        self.lb.configure(font=self.lb_font)

        # Need to force a refresh to get the correct no. of rows in the list box
        # I haven't found a simple way to do this so we slightly change the window size,
        # refresh and change the size back
        """
        # This method causes the window to move slightly - dont know why???!!!
        #window.geometry("{}x{}+{}+{}".format(window_width, window_height, x-coord, y-coord))
        #root.geometry('%dx%d+%d+%d' % (w, h, x, y))

        geom  = self.root.geometry()
        geom1 = geom.split('x')
        geom2 = str( int(geom1[0])+1 ) +'x'+geom1[1]
        self.root.geometry(geom2)
        self.root.update()
        self.root.geometry(geom)
        self.root.update()
        geom3  = self.root.geometry()
        print('TOGGLE SMALL FONT: size=',SIZE,'\tgeom=',geom,geom2,geom3)
        """
        # The window doesn't move with this method but there is a momentary flash - ugh!
        #self.root.state('withdrawn')
        self.root.attributes('-zoomed', True)
        self.root.update()
        self.root.attributes('-zoomed', False)
        #self.root.state('normal')
        self.root.update()

    # Toggle showing already worked stations
    def toggle_dupes(self):
        self.P.SHOW_DUPES=self.show_dupes.get()
        self.SelectBands()

    # Toggle logging of raw spots
    def toggle_echo(self):
        self.P.ECHO_ON=self.echo_raw_spots.get()
        
    # Toggle showing of needs for this year
    def toggle_need_year(self):
        self.P.SHOW_NEED_YEAR=self.show_need_year.get()

    # Toggle contest mode
    def toggle_contest_mode(self):
        self.P.CONTEST_MODE=self.contest_mode.get()
        if self.P.CONTEST_MODE:
            self.status_bar.setText("Contest Mode ON")
        else:
            self.status_bar.setText("Contest Mode OFF")

        for but,bb in zip( self.Band_Buttons , bands.keys()):
            #print('bb=',bb)
            but.pack_forget()
            if not self.P.CONTEST_MODE or bands[bb]["CONTEST"]:
                but.pack(side=LEFT,anchor=W)
            

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

    #########################################################################################

    # Function to create menu bar
    def create_menu_bar(self):
        print('Creating Menubar ...')
        OLD_WAY=True
        OLD_WAY=False

        self.toolbar = Frame(self.root, bd=1, relief=RAISED)
        self.toolbar.pack(side=TOP, fill=X)
        if OLD_WAY:
            menubar  = Menu(self.root)
            menubar2 = menubar
        else:
            menubar  = Menubutton(self.toolbar,text='Options',relief='flat')
            menubar.pack(side=LEFT, padx=2, pady=2)
            menubar2 = menubar

        Menu1 = Menu(menubar, tearoff=0)
        Menu1.add_command(label="Clear", command=self.Clear_Spot_List)
        Menu1.add_command(label="Reset", command=self.Reset)

        # Sub-menu to pick server
        Menu2 = Menu(menubar2, tearoff=0)
        self.node = StringVar(self.root)
        #self.node.set(self.P.SERVER)
        for node in list(self.P.NODES.keys()):
            Menu2.add_radiobutton(label=node,
                                     value=node,
                                     variable=self.node,
                                     command=self.SelectNode )
        Menu1.add_cascade(label="Cluster", menu=Menu2)
        Menu1.add_separator()
        
        self.dx_only = BooleanVar(value=self.P.DX_ONLY)
        Menu1.add_checkbutton(
            label="DX Only",
            underline=0,
            variable=self.dx_only,
            command=self.toggle_dx_only
        )
        
        self.na_only = BooleanVar(value=self.P.NA_ONLY)
        Menu1.add_checkbutton(
            label="NA Only",
            underline=0,
            variable=self.na_only,
            command=self.toggle_na_only
        )
        
        self.new_cwops_only = BooleanVar(value=self.P.NEW_CWOPS_ONLY)
        Menu1.add_checkbutton(
            label="New CWops Only",
            underline=0,
            variable=self.new_cwops_only,
            command=self.toggle_new_cwops_only
        )
        
        self.contest_mode = BooleanVar(value=self.P.CONTEST_MODE)
        Menu1.add_checkbutton(
            label="Contest Mode",
            underline=0,
            variable=self.contest_mode,
            command=self.toggle_contest_mode
        )
        
        Menu1.add_separator()
        self.P.SHOW_CW = 'CW' in self.P.SHOW_MODES
        self.show_cw   = BooleanVar(value=self.P.SHOW_CW)
        Menu1.add_checkbutton(
            label="Show CW",
            underline=0,
            variable=self.show_cw,
            command=self.toggle_cw
        )
        
        self.P.SHOW_RTTY = 'RTTY' in self.P.SHOW_MODES
        self.show_rtty = BooleanVar(value=self.P.SHOW_RTTY)
        Menu1.add_checkbutton(
            label="Show RTTY",
            underline=0,
            variable=self.show_rtty,
            command=self.toggle_rtty
        )
        
        self.P.SHOW_DIGI = 'DIGI' in self.P.SHOW_MODES
        self.show_digi = BooleanVar(value=self.P.SHOW_DIGI)
        Menu1.add_checkbutton(
            label="Show DIGI",
            underline=0,
            variable=self.show_digi,
            command=self.toggle_digi
        )
        
        self.P.SHOW_PHONE = 'PH' in self.P.SHOW_MODES
        self.show_phone = BooleanVar(value=self.P.SHOW_PHONE)
        Menu1.add_checkbutton(
            label="Show PHONE",
            underline=0,
            variable=self.show_phone,
            command=self.toggle_phone
        )
        
        Menu1.add_separator()
        self.echo_raw_spots = BooleanVar(value=self.P.ECHO_ON)
        Menu1.add_checkbutton(
            label="Echo Raw Spots",
            underline=0,
            variable=self.echo_raw_spots,
            command=self.toggle_echo
        )
        
        self.show_dupes = BooleanVar(value=self.P.SHOW_DUPES)
        Menu1.add_checkbutton(
            label="Show Dupes",
            underline=0,
            variable=self.show_dupes,
            command=self.toggle_dupes
        )
        
        Menu1.add_separator()
        self.show_need_year = BooleanVar(value=self.P.SHOW_NEED_YEAR)
        Menu1.add_checkbutton(
            label="Show This Year",
            underline=0,
            variable=self.show_need_year,
            command=self.toggle_need_year
        )
        
        self.show_need_mode = BooleanVar(value=self.P.SHOW_NEED_MODE)
        Menu1.add_checkbutton(
            label="Show Mode Needs",
            underline=0,
            variable=self.show_need_mode,
            command=self.toggle_need_mode
        )
        
        self.center_freq = BooleanVar(value=self.P.KEEP_FREQ_CENTERED)
        Menu1.add_checkbutton(
            label="Keep Freq Centered",
            underline=0,
            variable=self.center_freq,
            command=self.toggle_keep_centered
        )
        
        self.small_font = BooleanVar(value=self.P.SMALL_FONT)
        Menu1.add_checkbutton(
            label="Small Font",
            underline=0,
            variable=self.small_font,
            command=self.toggle_small_font
        )
        
        self.right_click_tunes_vfob = BooleanVar(value=self.P.RIGHT_CLICK_TUNES_VFOB)
        Menu1.add_checkbutton(
            label="Right Click Tunes VFO B",
            underline=0,
            variable=self.right_click_tunes_vfob,
            command=self.toggle_right_click_tunes_vfob
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

        Menu1.add_separator()
        Menu1.add_command(label="Settings ...", command=self.Settings)
        Menu1.add_separator()
        Menu1.add_command(label="Show Log ...", command=self.ShowLog)
        Menu1.add_separator()
        Menu1.add_command(label="Exit", command=self.root.quit)        
        
        menubar.menu =  Menu1
        menubar["menu"]= menubar.menu  


    # Function to open spot server
    def open_spot_server(self):

        P=self.P

        # Open telnet connection to spot server
        print('SERVER=',P.SERVER,'\tMY_CALL=',P.MY_CALL)
        #sys,exit(0)
        if P.SERVER=='NONE': # or (P.SERVER!="WSJT" and not P.INTERNET):

            # No cluster node
            P.tn = None
        
        elif P.SERVER=='ANY':

            # Go down list of known nodes until we find one we can connect to
            KEYS=list(P.NODES.keys())
            print('NODES=',P.NODES)
            print('KEYS=',KEYS)
            
            P.tn=None
            inode=0
            while not P.tn and inode<len(KEYS):
                key = KEYS[inode]
                self.status_bar.setText("Attempting to open node "+P.NODES[key]+' ...')
                P.tn = connection(P.TEST_MODE,P.NODES[key],P.MY_CALL,P.WSJT_FNAME, \
                                  ip_addr=P.WSJT_IP_ADDRESS,port=P.WSJT_PORT)
                inode += 1
            if P.tn:
                P.CLUSTER=P.NODES[key]
                P.SERVER = key
            else:
                print('\n*** Unable to connect to any node - no internet? - giving up! ***\n')
                sys.exit(0)
                
        else:

            # Connect to specified node 
            self.status_bar.setText("Attempting to open "+P.CLUSTER+' ...')
            P.tn = connection(P.TEST_MODE,P.CLUSTER,P.MY_CALL,P.WSJT_FNAME, \
                              ip_addr=P.WSJT_IP_ADDRESS,port=P.WSJT_PORT)

        if not P.TEST_MODE:
            if P.tn:
                OK=test_telnet_connection(P.tn)
                if not OK:
                    print('OPEN_SPOT_SERVER: Whooops!  SERVER=',P.SERVER,'\tOK=',OK)
                    sys.exit(0)
            else:
                if P.SERVER!='NONE':
                    print('OPEN_SPOT_SERVER: Giving up!  SERVER=',P.SERVER,'\tOK=',OK)
                    sys.exit(0)

                    
    # Function to read various auiliary data files
    def read_aux_data(self):

        P=self.P

        # Read challenge data
        self.status_bar.setText('Reading DX Challenge data ...')
        P.data = ChallengeData(P.CHALLENGE_FNAME)

        # Load data for highlighting CW ops members
        if P.CWOPS:
            self.status_bar.setText('Reading CWops data ...')
            fname='~/Python/history/data/Shareable CWops data.xlsx'
            HIST,fname2 = load_history(fname)
            P.members=list( set( HIST.keys() ) )
            print('No. CW Ops Members:',len(P.members))
            #print(P.members)

            P.cwop_nums=set([])
            for m in P.members:
                P.cwop_nums.add( int( HIST[m]['cwops'] ) )
            P.cwop_nums = list( P.cwop_nums )
            #print(P.cwop_nums)
            #sys.exit(0)
    
        # Read list of friends
        self.status_bar.setText('Reading misc data ...')
        self.friends = []
        lines = read_text_file('Friends.txt',
                               KEEP_BLANKS=False,UPPER=True)
        for line in lines:
            c=line.split(',')[0]
            if c[0]!='#':
                self.friends.append(c)
        print('FRIENDS=',self.friends)
        #sys.exit(0)
                                   
        # Read lists of most wanted
        self.most_wanted = read_text_file('Most_Wanted.txt',
                                          KEEP_BLANKS=False,UPPER=True)
        print('MOST WANTED=',self.most_wanted)
    
        # Read lists of common errors
        corrections = read_text_file('Corrections.txt',
                                     KEEP_BLANKS=False,UPPER=True)
        print('Corrections=',corrections)
        self.corrections={}
        for x in corrections:
            print(x)
            y=x.split(' ')
            self.corrections[y[0]] = y[1]
        print('Corrections=',self.corrections)

                    
