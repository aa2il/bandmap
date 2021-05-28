############################################################################################
#
# adif.py - Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Functions related to parsing ADIF files
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
############################################################################################

import re

############################################################################################

# Function to parse an ADIF logbook
def parse_adif(fn):
    raw = re.split('<eor>|<eoh>(?i)',open(fn).read() )
    raw.pop(0)  #remove header
    raw.pop()   #remove last empty item
    logbook =[]
    for record in raw:
        qso = {}
#        tags = re.findall('<(.*?):(\d+).*?>([^<\t\n\r\f\v\Z]+)',record)
        tags = re.findall('<(.*?):(\d+).*?>([^<\s]+)',record)
        for tag in tags:
            qso[tag[0].lower()] = tag[2][:int(tag[1])]
        logbook.append(qso)    
    return logbook

# Function to compute length of time for a qso
def qso_time(rec):
    if 'time_on' in rec :
        ton = rec["time_on"]
#        print "time on  = ",ton
    if 'time_off' in rec :
        toff = rec["time_off"]
#        print "time off = ",toff

    dt = 3600.*( int(toff[0:2]) - int(ton[0:2]) ) + 60.*(int(toff[2:4]) - int(ton[2:4])) + 1.*( int(toff[4:6]) - int(ton[4:6]) )
    return dt

