#! /usr/bin/python3 -u
################################################################################
#
# WatchDog.py - Rev 1.0
# Copyright (C) 2021-5 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
#
# Watchdog timer for bandmap.
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

import threading
from utilities import error_trap
import os
import psutil
import time

################################################################################

VERBOSITY=0

################################################################################

class WatchDog:
    def __init__(self,P,msec):
        print('Watch Dog Starting ....')

        self.P = P
        self.dt =.001*msec
        P.SHUTDOWN = False

        # Kick off watchdog monito
        P.Timer = threading.Timer(self.dt, self.Monitor)
        P.Timer.daemon=True                       # This prevents timer thread from blocking shutdown
        P.Timer.start()
        
        
    def Monitor(self):
        P=self.P
        print('WATCHDOG - Tic Tok ...')
    
        # Check if another thread shut down - this isn't complete yet
        if P.SHUTDOWN:
            if P.Timer:
                print('WatchDog - Cancelling timer ...')
                P.Timer.cancel()
            P.WATCHDOG = False
            P.Timer=None
            print('WatchDog - Shut down.')

        # Monitor memory usage
        if P.MEM:
            P.MEM.take_snapshot()

        # Check on telnet cluster connection
        if not P.ClusterFeed.tn:
            print('\tWhooops - no cluster feed!!!!!!!!!!!!!!!!!!')
            
        # Reset timer
        if VERBOSITY>0:
            print("WatchDog - Timer ...")
        if not P.SHUTDOWN:   # and not P.Stopper.isSet():
            P.Timer = threading.Timer(self.dt, self.Monitor)
            P.Timer.setDaemon(True)                       # This prevents timer thread from blocking shutdown
            P.Timer.start()
        else:
            P.Timer=None
            print('... Watch Dog quit')
            P.WATCHDOG = False
        
        
