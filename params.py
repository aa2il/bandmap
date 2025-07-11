################################################################################
#
# Params.py - Rev 1.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
#
# Command line param parser for bandmap
#
################################################################################
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
################################################################################

import sys
import os
import argparse
from collections import OrderedDict 
from rig_io  import CONNECTIONS,RIGS
from settings import *
from dx import load_cty_info
from rig_io import HF_BANDS,VHF_BANDS,CONTEST_BANDS

################################################################################

# Sometimes when these don't work, its bx the login handshaking needs some work
NODES=OrderedDict()
#NODES['PY3NZ']  = 'dxc.baependi.com.br:8000'        # dxwatch.com - down?
#NODES['NK7Z']   = 'nk7z-cluster.ddns.net:7373'      # Lots of spots! - down?
NODES['NC7J']   = 'dxc.nc7j.com:7373'               # OK - AR cluster
NODES['W3LPL']  = 'w3lpl.net:7373'                  # Ok - lots of spots, no FT8 dxc.w3lpl.net

#telnet telnet.reversebeacon.net 7000
#telnet telnet.reversebeacon.net 7001
NODES['RBN']    = 'telnet.reversebeacon.net:7000'   # RBN - 7000 for CW & RTTY, 7001 for ft8

NODES['AE5E']   = 'dxspots.com'                     # 
NODES['VE7CC']  = 'dxc.ve7cc.net'                     # 
NODES['W9PA']   = 'dxc.w9pa.net:7373'               # Ok - lots of spots, no FT8 dxc.w3lpl.net
NODES['WC2L']   = 'dxc.wc2l.com'                    # 
NODES['K3LR']   = 'dx.k3lr.com'                     # 
NODES['WS7I']   = 'ws7i.ewarg.org:7300'               # OK - need to work on filtering - uses "non AR" cluster, can show FT8

NODES['W8AEF']  = 'paul.w8aef.com:7373'             # AZ - no FT8 - can turn it on
NODES['N6WS']   = 'n6ws.no-ip.org:7300'             # Ok
NODES['K1TTT']  = 'k1ttt.net:7373'                  # (Peru, MA); Skimmer capable
NODES['W6RFU']  = 'ucsbdx.ece.ucsb.edu:7300'        # Ok - CQ Zones 1-5 spots only (i.e. US & Canada)
NODES['AE5E']   = 'dxspots.com'                     # Ok - not many spots
NODES['N4DEN']  = 'dxc.n4den.us:7373'               # Ok
NODES['W6KK']   = 'w6kk.zapto.org:7300'             # Ok - USA and VE spots only, not many spots
NODES['N7OD']   = 'n7od.pentux.net'                 # Ok
NODES['WC4J']   = 'dxc.wc4j.net'                    # Doesnt work
NODES['WA9PIE'] = 'dxc.wa9pie.net:8000'             # HRD
NODES['K2LS']   = 'dxc.k2ls.com'                    # CQ Zones 1-8 spots only (i.e. NA) - not sure how to log in
NODES['W6CUA']  = 'w6cua.no-ip.org:7300'            # Not sure how to log on?
NODES['K7EK']   = 'www.k7ek.net:9000'               # Doesn't work?
NODES['K6EXO']  = 'k6exo.dyndns.org:7300'           # Doesn't work?
NODES['N6WS']   = 'n6ws.no-ip.org:7300'             # Not sure how to log on?
NODES['N7OD']   = 'n7od.pentux.net'                  # Not sure how to log on?
NODES['ANY']    = ''
NODES['NONE']   = ''

################################################################################

# Structure to contain processing params
class PARAMS:
    def __init__(self):

        # Process command line args
        # Can add required=True to anything that is required
        arg_proc = argparse.ArgumentParser()
        #arg_proc.add_argument('-contest', action='store_true',help='Contest Mode')
        arg_proc.add_argument('-contest', help='Contest Mode [contest name]',
                              type=str,default=None,nargs='*')
        arg_proc.add_argument('-ss', action='store_true',help='ARRL Sweepstakes')
        arg_proc.add_argument('-echo', action='store_true',help='Echo lines from server')
        arg_proc.add_argument("-rig", help="Connection Type to Rig",
                              type=str,default=["NONE"],nargs='+',
                              choices=CONNECTIONS+['NONE']+RIGS)
        arg_proc.add_argument("-port", help="TCPIP port",
                              type=int,default=0)
        arg_proc.add_argument("-cluster", help="Server",
                              type=str,default="ANY",
                              choices=list(NODES.keys()) )
        arg_proc.add_argument("-wsjt", help="wsjt", nargs='*', 
                              type=str,default=None)
        arg_proc.add_argument("-log", help="Log file (keep track of dupes)",
                              type=str,
                              default=None)
                              #default=None,nargs='*')
                              #default="~/logs/[MYCALL].adif")
                              #default="")    #,nargs='+')
        arg_proc.add_argument('-dx_only', action='store_true',
                              help='Show only DX spots')
        arg_proc.add_argument('-nodupes', action='store_true',
                              help='Dont show dupes')
        arg_proc.add_argument("-modes", help="Show only these modes",
                              type=str,default='ANY',nargs='*')
        arg_proc.add_argument('-na_only', action='store_true',
                              help='Show only spots from North America')
        arg_proc.add_argument('-buttons', action='store_true',
                              help='Enable band buttons')
        arg_proc.add_argument('-bm_udp', action='store_true',
                              help='Start UDP client')
        arg_proc.add_argument('-save', action='store_true',
                              help='Save All Spots')
        arg_proc.add_argument('-cwops', action='store_true',
                              help='Highlight CWops Members')
        arg_proc.add_argument('-show_mode', action='store_true',
                              help='Show mode needs')
        arg_proc.add_argument('-show_year', action='store_true',
                              help='Show dxcc needs for this year')
        arg_proc.add_argument('-vhf', action='store_true',
                              help='Show Only VHF Buttons')
        arg_proc.add_argument('-ft4', action='store_true',
                              help='Use FT4 freqs instead of FT8')
        arg_proc.add_argument('-small', action='store_true',
                              help='Use small font')
        arg_proc.add_argument('-center', action='store_true',
                              help='Keep list centered on rig freq')
        arg_proc.add_argument("-vfo", help="VFO to follow",
                              type=str,default="A",
                              choices=['A','B'] )
        #arg_proc.add_argument('-noft8', action='store_true',help='Filter out FT8 spots')
        arg_proc.add_argument('-bm_geo',type=str,default=None,
                              help='Geometry')
        arg_proc.add_argument('-test', action='store_true',help='Test Mode')
        arg_proc.add_argument("-hours", help="Max no. hours for a dupe",
                              type=float,default=2*24)
        arg_proc.add_argument("-age", help="Max no. minutes to keep a spot around",
                              type=int,default=None)
        arg_proc.add_argument('-desktop',type=int,default=None,
                              help='Desk Top Work Space No.')
        arg_proc.add_argument('-settings',action='store_true',
                              help='Open setting window')
        arg_proc.add_argument("-debug", help="Debug Level",
                              type=int,default=0)
        args = arg_proc.parse_args()

        self.gui             = None
        self.CONNECTION     = args.rig[0]
        if len(args.rig)>=2:
            self.RIG         = args.rig[1]
        else:
            self.RIG         = None
        self.PORT            = args.port

        self.MAX_HOURS_DUPE  = args.hours

        if args.contest==None:
            self.CONTEST_MODE = False
            self.CONTEST_NAME = None
        else:
            self.CONTEST_MODE = True
            if len(args.contest)>0:
                self.CONTEST_NAME = args.contest[0].upper()
            else:
                self.CONTEST_NAME = None

        self.DESKTOP        = args.desktop
        self.SMALL_FONT     = args.small or self.CONTEST_MODE
        self.STAND_ALONE    = True
        
        self.VHF_ONLY       = args.vhf
        if self.VHF_ONLY:
            self.BANDS = VHF_BANDS
            self.CONTEST_BANDS = VHF_BANDS
        else:
            self.BANDS = HF_BANDS+VHF_BANDS
            self.CONTEST_BANDS = CONTEST_BANDS
        
        self.BM_GEO         = args.bm_geo
        self.TEST_MODE      = args.test
        self.CW_SS          = args.ss
        self.CWOPS          = args.cwops
        self.DX_ONLY        = args.dx_only
        self.NA_ONLY        = args.na_only
        self.NEW_CWOPS_ONLY = False
        self.BM_UDP_CLIENT     = args.bm_udp
        self.SAVE_SPOTS     = args.save
        self.RIG_VFO        = args.vfo
        self.FT4            = args.ft4
        self.DEBUG          = args.debug
        self.SHOW_NEED_MODE = args.show_mode
        self.SHOW_NEED_YEAR = args.show_year
        self.SHOW_DUPES     = not args.nodupes
        self.GUI_BAND       = None
        self.GUI_MODE       = None

        valid_modes=['CW','RTTY','DIGI','PH']
        if type(args.modes) is list:
            self.SHOW_MODES = args.modes
        elif args.modes=='ANY':
            self.SHOW_MODES = valid_modes
        else:
            self.SHOW_MODES = [args.modes]
        for m in self.SHOW_MODES:
            if m not in valid_modes:
                print('PARAMS ERROR - Unrecognized mode:',m,'\nValid modes are',valid_modes)
                sys.exit(0)

        # See     http://www.ng3k.com/misc/cluster.html       for a list 
        self.SERVER=args.cluster.upper()
        self.WSJT_FNAME=None

        self.WSJT_IP_ADDRESS = '127.0.0.1'
        self.WSJT_PORT = 2237
        WSJT2=args.wsjt
        if WSJT2!=None:
            print("\nWSJT2=",WSJT2,len(WSJT2))
            self.WSJT_FNAME=os.path.expanduser("~/.local/share/WSJT-X")
            self.WSJT_FNAME+=" - "+WSJT2[0]
            self.WSJT_FNAME+="/ALL.TXT"
            self.CLUSTER='WSJT'
            self.SERVER='WSJT'
    
            if len(WSJT2)>=2:
                self.WSJT_PORT = int(WSJT2[1])
        
            print("WSJT_FNAME=", self.WSJT_FNAME)
            print("WSJT_PORT =", self.WSJT_IP_ADDRESS,self.WSJT_PORT)
            #sys.exit(0)
        else:
            self.CLUSTER=NODES[self.SERVER]
        #print('CLUSTER=',CLUSTER)

        if args.log==None:
            if args.wsjt==None:
                #self.LOG_NAME = "~/logs/[MYCALL].adif"
                self.LOG_NAME = "~/[OPERATOR]/[MYCALL].adif"
                #self.LOG_NAME = "~/logs/[OPERATOR].adif"
            else:
                self.LOG_NAME = "~/.local/share/WSJT-X"
                if WSJT2!=None:
                    self.LOG_NAME+=" - "+WSJT2[0]
                self.LOG_NAME += "/wsjtx_log.adi"
        else:
            self.LOG_NAME = args.log

        if False:
            #print(len(args.log))
            print(args.log)
            print(WSJT2)
            print(self.SERVER)
            print(self.LOG_NAME)
            sys,exit(0)
        
        self.ECHO_ON=args.echo
        if args.age:
            self.MAX_AGE=args.age
        elif self.CLUSTER=='WSJT':
            self.MAX_AGE=4               # Was 5
        else:
            self.MAX_AGE=5               # Was 10
    
        self.rootlogger = "dxcsucker"
        self.TIME_OUT=.01

        # Read config file
        self.SETTINGS,self.RCFILE = read_settings('.keyerrc')
        if args.settings:
            SettingsWin = SETTINGS_GUI(None,self,BLOCK=True)
            
        self.DATA_DIR=self.SETTINGS['MY_DATA_DIR']
        if self.DATA_DIR=='':
            self.DATA_DIR='~/Python/data'
        print('DATA_DIR=',self.DATA_DIR)

        self.MY_CALL      = self.SETTINGS['MY_CALL']
        self.OPERATOR     = self.SETTINGS['MY_OPERATOR']
        self.LOG_NAME     = self.LOG_NAME.replace('[OPERATOR]',self.OPERATOR)
        if self.OPERATOR!=self.MY_CALL:
            self.LOG_NAME0 = os.path.expanduser( self.LOG_NAME.replace('[MYCALL]',self.OPERATOR ) )
        else:
            self.LOG_NAME0 = None
        MY_CALL2          = self.MY_CALL.replace('/','_')
        self.LOG_NAME     = os.path.expanduser( self.LOG_NAME.replace('[MYCALL]',MY_CALL2 ) )
        self.NODES        = NODES
        self.threads      = []
        print('LOG_NAME=',self.LOG_NAME,'\tSTAND_ALONE=',self.STAND_ALONE)

        # Take care of non-standard location of support files
        load_cty_info(DIR=self.SETTINGS['MY_DATA_DIR'])
        
        if self.SERVER=="WSJT" or args.buttons:
            self.ALLOW_CHANGES=True
        else:
            self.ALLOW_CHANGES=False
        
        # The spreadsheets with the DXCC already worked data & node info
        MY_CALL3 = self.OPERATOR.split('/')[0]
        DATA_DIR = os.path.expanduser('~/'+MY_CALL3+'/')
        self.CHALLENGE_FNAME = DATA_DIR+'/states.xls'
        if not os.path.isfile(self.CHALLENGE_FNAME):
            self.CHALLENGE_FNAME = 'states.xls'
        if not os.path.isfile(self.CHALLENGE_FNAME):
            self.CHALLENGE_FNAME = None
        
        self.NODES_FNAME = DATA_DIR+'/states.xls'
        if not os.path.isfile(self.NODES_FNAME):
            self.NODES_FNAME = 'nodes.xls'

        self.KEEP_FREQ_CENTERED=args.center
        self.RIGHT_CLICK_TUNES_VFOB = self.SERVER!="WSJT"
