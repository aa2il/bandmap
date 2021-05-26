###############################################################################

# ADIF.py - J.B.Attili - 2018

# Functions related to parsing ADIF files

###############################################################################

import re

###############################################################################

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

