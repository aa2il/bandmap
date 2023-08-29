#########################################################################################
#
# gui.py - Rev. 1.0
# Copyright (C) 2021-3 by Joseph B. Attili, aa2il AT arrl DOT net
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
from fileio import parse_adif
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
from load_history import load_history
from utilities import freq2band
from udp import *

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
        self.nerrors=0
        self.enable_scheduler=True
        self.last_error=''
        self.rig_freq = self.sock.get_freq(VFO=self.VFO) / 1000.
        self.friends=[]
        self.most_wanted=[]
        self.corrections=[]

        # UDP stuff
        P.udp_client=None
        P.udp_ntries=0
        
        # Load data for highlighting CW ops members
        if self.P.CWOPS:
            fname='~/Python/history/data/Shareable CWops data.xlsx'
            HIST,fname2 = load_history(fname)
            self.members=list( set( HIST.keys() ) )
            print('No. CW Ops Members:',len(self.members))
            #print(self.members)
            #sys.exit(0)
        else:
            self.members=[]
        
        # Open a file to save all of the spots
        if P.SAVE_SPOTS:
            self.fp = open("all_spots.dat","w")
        else:
            self.fp=-1

        # Create the GUI - need to be able to distinguish between multiple copies of bandmap 
        self.root = Tk()
        if P.SERVER=="WSJT":
            self.root.title("Band Map by AA2IL - " + P.SERVER)
        else:
            self.root.title("Band Map by AA2IL - Server " + P.SERVER)

        # Move to lower left corner of screen
        if P.GEO==None:
            self.screen_width = self.root.winfo_screenwidth()
            self.screen_height = self.root.winfo_screenheight()
            print('Screen=',self.screen_width, self.screen_height)
            w=400
            h=self.screen_height
            sz=str(w)+'x'+str(h)+'+'+str(self.screen_width-400)+'+0'
        else:
            #bandmap.py -geo 400x790+1520+240
            sz=P.GEO
        self.root.geometry(sz)

        # Add menu bar
        self.create_menu_bar()

        # Set band according to rig freq
        self.band   = StringVar(self.root)
        self.ant    = IntVar(self.root)
        self.ant.set(-1)
        self.mode   = StringVar(self.root)
        self.mode.set('')
        if self.sock.active:
            if VERBOSITY>0:
                logging.info("Calling Get band ...")
            f = 1e-6*self.sock.get_freq(VFO=self.VFO)     # Query rig at startup
            b = freq2band(f)
        else:
            f = 0
            b = DEFAULT_BAND              # No conenction so just default
        print('BM_GUI: BAND.SET band=',b,'\tf=',f)
        self.band.set(b)
        self.rig_band=b
        print("Initial band=",b)

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
        #for m in modes:
        #for m in ['CW','Data','SSB','LSB','USB']:
        for m in ['CW','Data','SSB']:
            Radiobutton(subFrame1, 
                        text=m,
                        indicatoron = 0,
                        variable=self.mode, 
                        command=lambda: self.SelectMode(),
                        value=m).pack(side=LEFT,anchor=W)
        self.SelectMode('')

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
        self.SelectAnt(-1)

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

        # List box
        self.LBframe = Frame(self.root)
        self.LBframe.pack(side=LEFT,fill=BOTH,expand=1)

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

        # And away we go
        self.SelectBands(True)
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
    def SelectAnt(self,a=None,b=None):
        if not a:
            a  = self.ant.get()
        if a==-1:
            if VERBOSITY>0:
                logging.info("Calling Get Ant ...")
            a = self.sock.get_ant()
            self.ant.set(a)
            #print "\n%%%%%%%%%% Select Antenna: Got Antenna =",a,"%%%%%%%%"
        elif a==-2:
            if VERBOSITY>0:
                logging.info("Checking Ant matches Band ...")
            if self.P.sock.rig_type2=='FTdx3000':
                if b in ['160m','80m']:
                    ant=3
                elif b in ['40m','20m','15m']:
                    ant=1
                elif b in ['30m','17m','12m','10m','6m']:
                    ant=3    # Ant 2 is broken
                else:
                    ant=1
                self.P.sock.set_ant(ant,VFO=self.VFO)
                
        else:
            print("\n%%%%%%%%%% Select Antenna: Setting Antenna =",a,"%%%%%%%%")
            if VERBOSITY>0:
                logging.info("Calling Set Ant  ...")
            self.sock.set_ant(a,VFO=self.VFO)

    # Callback to handle mode changes
    def SelectMode(self,m=None):
        if VERBOSITY>0:
            print('\nSelectMode: mode=',m)
        if m==None:
            m = self.mode.get()
            print('SelectMode-a: mode2=',m)

        if m=='':
            if VERBOSITY>0:
                logging.info("Calling Get Mode ...")
            m = self.sock.get_mode(VFO=self.VFO)
            #print('SelectMode-b:',m)
            if m=='RTTY' or m=='FT8' or m=='FT4' or m[0:3]=='PKT' or m=='DIGITIAL':
                m='Data'
            self.mode.set(m)
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

    #Function to collect spots for a particular band
    def collect_spots(self,band,REVERSE=False):

        print('COLLECT_SPOTS: band=',band,'\tReverse=',REVERSE,'\tCONTEST_MODE=', self.P.CONTEST_MODE)

        if 'cm' in band:
            iband=int( band.replace('cm','') )
        else:
            iband=int( band.replace('m','') )
            
        if self.P.CONTEST_MODE:

            m = self.mode.get()
            print('COLLECT_SPOTS: m=',m)
            if self.P.DX_ONLY:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == iband and \
                       x.dx_station.country!='United States' and (m not in ['CW'] or x.mode not in ['FT8','FT4','DIGITAL']) ] 
            elif self.P.NA_ONLY:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == iband and \
                       x.dx_station.continent=='NA' and (m not in ['CW'] or x.mode not in ['FT8','FT4','DIGITAL']) ] 
            else:
                idx = [i for i,x in enumerate(self.SpotList) if x.band == iband and \
                       (m not in ['CW'] or x.mode not in ['FT8','FT4','DIGITAL']) ]
                
        else:
            
            if self.P.DX_ONLY:
                # Retain only stations outside US or SESs
                idx = [i for i,x in enumerate(self.SpotList) if x and x.band == iband and \
                       (x.dx_station.country!='United States' or len(x.dx_call)==3 or \
                        x.dx_call=='WM3PEN')] 
            elif self.P.NA_ONLY:
                # Retain only stations in North America
                idx = [i for i,x in enumerate(self.SpotList) if x and x.band == iband and \
                       x.dx_station.continent=='NA']
            else:
                idx = [i for i,x in enumerate(self.SpotList) if x and x.band == iband]
            
        spots = [self.SpotList[i] for i in idx]
        spots.sort(key=lambda x: x.frequency, reverse=REVERSE)

        return spots


                
    # Callback to handle band changes
    def SelectBands(self,allow_change=False):

        VERBOSITY = self.P.DEBUG
        VERBOSITY = 1
        if VERBOSITY>0:
            print('SELECT BANDS A: nspots=',self.nspots,
                  '\tlen SpotList=',len(self.SpotList),
                  '\tlen Current=',len(self.current))

        scrolling(self,'SELECT BANDS A')
        
        try:
            band  = self.band.get()
        except:
            print('SELECT BANDS Error - band=',self.band)
            return
        
        if VERBOSITY>0:
            logging.info("Calling Get Band ...")
        frq2 = 1e-6*self.sock.get_freq(VFO=self.VFO)
        band2 = freq2band(frq2)
        
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
                except Exception as e: 
                    print(e)
                    return
                print('BM_GUI - Config WSJT ...',b,self.FT_MODE,new_frq)
                if VERBOSITY>0:
                    logging.info("Calling Set Freq and Mode ...")
                self.sock.set_freq(new_frq,VFO=self.VFO)
                self.sock.set_mode(self.FT_MODE,VFO=self.VFO)
            else:
                if band != band2:
                    if VERBOSITY>0:
                        logging.info("Calling Set Mode ...")
                    self.sock.set_band(band,VFO=self.VFO)

            # Make sure antenna selection is correct also
            self.SelectAnt(-2,band)
            
        # Extract a list of spots that are in the desired band
        self.current = self.collect_spots(band)
        y=scrolling(self,'SELECT BANDS B')
        
        # Get latest logbook
        now = datetime.utcnow().replace(tzinfo=UTC)
        if self.P.PARSE_LOG:
            logbook = parse_adif(self.P.LOG_NAME,REVISIT=True)
            self.qsos += logbook
            print('################################# QSOs in log=',
                  len(logbook),len(self.qsos))
            #if len(self.qsos)==0:
            #    self.P.PARSE_LOG=False
            #print('qsos=',self.qsos)
            #print('qsos[0]=',self.qsos[0])
            #sys.exit(0)

        if self.P.CWOPS:
            self.calls = [ qso['call'] for qso in self.qsos ]
            self.calls=list( set( self.calls) )
            print('No. unique calls works:',len(self.calls))
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
            if VERBOSITY>0:
                print('SELECT BANDS: Calling LB_COLORS ... band=',band)
            self.current[n].color=self.lb_colors('A',END,now,band,x)
            n+=1

        # Reset lb view
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
                match=False
                print('\n!@#$%^!&&*#^#^ MATCH ERROR',x.dx_call)
                print('qso=',qso)
                print('!@#$%^!&&*#^#^ MATCH ERROR\n')
                
        #print('\n------MATCH_QSOS: qso=',qso,x.dx_call,match)
        if match:
            t1 = datetime.strptime(now.strftime("%Y%m%d %H%M%S"), "%Y%m%d %H%M%S") 
            t2 = datetime.strptime( qso['qso_date_off']+" "+qso["time_off"] , "%Y%m%d %H%M%S")
            delta=(t1-t2).total_seconds() / 3600
            match = delta< self.P.MAX_HOURS_DUPE
            if VERBOSITY>=2:
                print('--- MATCH_QSOS: Possible dupe for',x.dx_call,'\tt12',t1,t2,'\tdelta=',delta,match)

        return match

    # Function to determine spot color
    def spot_color(self,match,x):

        now = datetime.utcnow().replace(tzinfo=UTC)
        age = (now - x.time).total_seconds()/60      # In minutes
        dx_call=x.dx_call.upper()
        dx_station = Station(dx_call)
        if dx_station.country=='United States' and len(dx_station.appendix)>=2:
            dx_call=dx_station.homecall            # Strip out bogus appendices from state QPs
        if self.P.CWOPS and '/' in dx_call:
            dx_station = Station(dx_call)
            home_call = dx_station.homecall
        else:
            home_call = dx_call

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
        elif self.P.CWOPS and ( (dx_call in self.members) or (home_call in self.members) ):
            if dx_call in self.calls:
                c="gold"
                c2='g'
            else:
                c='orange'
                c2='o'
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
                    except Exception as e: 
                        print(e)
                        match=False
                        print('\n!@#$%^!&&*#^#^ MATCH ERROR',dx_call)
                        print('qso=',qso)
                        print('!@#$%^!&&*#^#^ MATCH ERROR\n')
                #print('\n------B4: qso=',qso,dx_call,match)
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

            

    # Change background colors on each list entry
    def lb_colors(self,tag,idx,now,band,x):

        if isinstance(band,int):
            print('LB_COLORS: ******** Missing m ********',band)
            band = str(band)+'m'

        match = self.B4(x,band)
        c,c2,age=self.spot_color(match,x)
        
        #print('@@@@@@@@@@@@@@@@ LB_COLORS: tag=',tag,'\tcall=',dx_call,
        #      '\tc=',c,'\tage=',age)
        self.lb.itemconfigure(idx, background=c)
        if VERBOSITY>0:
            print('... LB_COLORS: tag=',tag,'\tcall=',dx_call,'\tcolor=',c,
                  '\tage=',age,'\tmatch=',match)
                
        # Make sure the entry closest to the rig freq is visible
        #print '... Repopulated'
        #logging.info("Calling LBsanity - band="+str(band)+" ...")
        self.LBsanity()
        #print(" ")

        return c2


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
        self.Clear_Spot_List()
        if self.P.UDP_CLIENT and self.P.udp_client and False:
            self.P.udp_client.StartServer()
        if self.P.UDP_CLIENT and self.P.udp_server and False:
            self.P.udp_server.StartServer()
        if self.tn:
            self.tn.close()
            self.enable_scheduler=False
            time.sleep(.1)
        self.tn = connection(self.P.TEST_MODE,self.P.CLUSTER, \
                             self.P.MY_CALL,self.P.WSJT_FNAME)
        print("--- Reset --- Connected to",self.P.CLUSTER, self.enable_scheduler)
        OK=test_telnet_connection(self.tn)
        if not OK:
            print('--- Reset --- Now what Sherlock?!')
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
        
        self.P.data = ChallengeData(self.P.CHALLENGE_FNAME)
#        print "Howdy Ho!",self.nspots

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
            self.root.after(dt, self.Scheduler)        # Was 100

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
            self.rig_freq = 1e-3*self.sock.get_freq(VFO=self.VFO)
            self.rig_band = freq2band(1e-3*self.rig_freq)

        self.SelectAnt(-1)
        self.SelectMode('')

        #self.root.update()
        self.root.update_idletasks()
        self.root.after(1*1000, self.WatchDog)

    #########################################################################################

    # Callback when an item in the listbox is selected
    def LBSelect(self,value,vfo):
        print('LBSelect: Tune rig to a spot - vfo=',vfo,value)
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
        self.sock.set_freq(float(b[0]),VFO=vfo)
        if not self.P.CONTEST_MODE:
            print("LBSelect: Setting mode ",b[2])
            #self.sock.mode.set(b[2],VFO=vfo)
            self.SelectMode(b[2])
            self.sock.set_freq(float(b[0]),VFO=vfo)            
        self.sock.set_call(b[1])

        # Make sure antenna selection is correct also
        band=freq2band(0.001*float(b[0]))
        self.SelectAnt(-2,band)

        # Send spot info to keyer
        if self.P.UDP_CLIENT:
            if not self.P.udp_client:
                self.P.udp_ntries+=1
                if self.P.udp_ntries<=10:
                    self.P.udp_client=open_udp_client(self.P,KEYER_UDP_PORT,
                                                      udp_msg_handler)
                    if self.P.udp_client:
                        print('GUI->LBSelect: Opened connection to KEYER.')
                        self.P.udp_ntries=0
                else:
                    print('Unable to open UDP client - too many attempts',self.P.udp_ntries)

            if self.P.udp_client:
                self.P.udp_client.Send('Call:'+b[1]+':'+vfo)

            
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

        if False:
            # This used to trigger a qrz call lookup
            # Keep this for now in case we want this capability later
            b=value.strip().split()
            print("Looking up call: ",b[1])
        
            link = 'https://www.qrz.com/db/' + b[1]
            webbrowser.open_new_tab(link)

        else:
            # Now is tunes VFO-B
            # Perhaps we can have a flag to select which action we want??
            self.LBSelect(value,'B')
    

    def LBCenterClick(self,event):
        print('LBCenterClick: Delete an entry')

        index = event.widget.nearest(event.y)
        value = event.widget.get(index)
        b=value.strip().split()
        call=b[1]
        print('You selected item %d: %s - %s' % (index,value,call))

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

    # Toggle DX ONLY mode
    def toggle_dx_only(self):
        self.P.DX_ONLY=self.dx_only.get()
        print('TOGGLE BOGGLE',self.P.DX_ONLY)

    # Toggle NA ONLY mode
    def toggle_na_only(self):
        self.P.NA_ONLY=self.na_only.get()
        print('TOGGLE BOGGLE',self.P.NA_ONLY)

    # Toggle showing of needs for mode
    def toggle_need_mode(self):
        self.P.SHOW_NEED_MODE=self.show_need_mode.get()
        print('TOGGLE BOGGLE',self.P.SHOW_NEED_MODE)

    # Toggle keep freq centered
    def toggle_keep_centered(self):
        self.P.KEEP_FREQ_CENTERED=self.center_freq.get()
        print('TOGGLE BOGGLE',self.P.KEEP_FREQ_CENTERED)

    # Toggle font used in list box
    def toggle_small_font(self):
        self.P.SMALL_FONT=self.small_font.get()
        if self.P.SMALL_FONT:
            SIZE=8
        else:
            SIZE=10 
        print('TOGGLE BOGGLE',self.P.SMALL_FONT,SIZE)
        self.lb_font.configure(size=SIZE)
        self.lb.configure(font=self.lb_font)

        # Need to force a refresh to get the correct no. of rows in the list box
        geom=self.root.geometry()
        h=self.root.winfo_height()
        w=self.root.winfo_width()
        print('TOGGLE SMALL FONT: size=',SIZE,'\tgeom=',geom,h,w)
        sz=str(w)+'x'+str(int(h+1))
        self.root.geometry(sz)
        sz=str(w)+'x'+str(h)
        self.root.geometry(sz)
        
    # Toggle showing of needs for this year
    def toggle_need_year(self):
        self.P.SHOW_NEED_YEAR=self.show_need_year.get()
        print('TOGGLE BOGGLE',self.P.SHOW_NEED_YEAR)

    # Toggle contest mode
    def toggle_contest_mode(self):
        self.P.CONTEST_MODE=self.contest_mode.get()
        print('TOGGLE BOGGLE',self.P.CONTEST_MODE)

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

    def click_bait(self):
        try:
            self.n+=1
        except:
            self.n=0
        print('CLICK BAIT',self.n)

    #########################################################################################

    # Function to create menu bar
    def create_menu_bar(self):
        print('Creating Menubar ...')
        OLD_WAY=True
        OLD_WAY=False
        MENU_ITEMS=1

        self.toolbar = Frame(self.root, bd=1, relief=RAISED)
        self.toolbar.pack(side=TOP, fill=X)
        if OLD_WAY:
            menubar  = Menu(self.root)
            menubar2 = menubar
        else:
            menubar  = Menubutton(self.toolbar,text='Options',relief='flat')
            menubar.pack(side=LEFT, padx=2, pady=2)
            if MENU_ITEMS==1:
                menubar2 = menubar
            else:
                menubar2 = Menubutton(self.toolbar,text='Cluster',relief='flat')
                menubar2.pack(side=LEFT, padx=2, pady=2)

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
        
        self.na_only = BooleanVar(value=self.P.NA_ONLY)
        Menu1.add_checkbutton(
            label="NA Only",
            underline=0,
            variable=self.na_only,
            command=self.toggle_na_only
        )
        
        self.contest_mode = BooleanVar(value=self.P.CONTEST_MODE)
        Menu1.add_checkbutton(
            label="Contest Mode",
            underline=0,
            variable=self.contest_mode,
            command=self.toggle_contest_mode
        )
        
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

        # Sub-menu to pick server
        Menu2 = Menu(menubar2, tearoff=0)
        self.node = StringVar(self.root)
        self.node.set(self.P.SERVER)
        for node in list(self.P.NODES.keys()):
            Menu2.add_radiobutton(label=node,
                                     value=node,
                                     variable=self.node,
                                     command=self.SelectNode )

        if MENU_ITEMS==1:
            Menu1.add_separator()
            Menu1.add_cascade(label="Cluster", menu=Menu2)
        
        Menu1.add_separator()
        Menu1.add_command(label="Settings ...", command=self.Settings)
        Menu1.add_separator()
        Menu1.add_command(label="Show Log ...", command=self.ShowLog)
        Menu1.add_separator()
        Menu1.add_command(label="Exit", command=self.root.quit)        
        
        if OLD_WAY:
            menubar.add_cascade(label="Options", menu=Menu1)
            if MENU_ITEMS==2:
                menubar.add_cascade(label="Cluster", menu=Menu2)
            #menubar.add_command(label="Click Me", command=self.click_bait)
            self.root.config(menu=menubar)
        else:
            menubar.menu =  Menu1
            menubar["menu"]= menubar.menu  
            if MENU_ITEMS==2:
                menubar2.menu =  Menu2
                menubar2["menu"]= menubar2.menu  


