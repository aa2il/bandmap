#!/usr/bin/python
############################################################################################

# Playpen - J.B.Attili - 2018

# Work area to get various components up and running.

# To Do - test if this works under python3

############################################################################################

import sys
from datetime import datetime, date, tzinfo  
import pytz
from dx.spot_processing import Station, Spot, WWV, Comment, ChallengeData
from adif import *
from pprint import pprint
from dx.cty import load_cty

UTC = pytz.utc
LOG_NAME='~/.fldigi/logs/aa2il_2018.adif'

print('HEY')

if True:
    from pyhamtools.locator import calculate_heading, calculate_heading_longpath
    bearing = calculate_heading("JN48QM", "QF67bf")
    print(bearing)
    #74.3136
    bearing2 = calculate_heading_longpath("JN48QM", "QF67bf")
    print(bearing2)
    #254.3136
    sys.exit(0)

# Playpen
if True:

    if False:
        # This is very slow bx it downloads the database each time
        # There appears to be a way to speed it up using REDIS but let's try something else
        from pyhamtools import LookupLib, Callinfo

        print('Hey 1')
        my_lookuplib = LookupLib(lookuptype="countryfile")
        print('Hey 2')
        cic = Callinfo(my_lookuplib)
        print('Hey 3')
        print((cic.get_all("DH1TW")))
        print('Hey 4')
        sys.exit(0)

    if True:

        # This seems pretty fast
        dxcc="6Y3T"
        dx_station = Station(dxcc)
        #print dx_station
        pprint(vars(dx_station))
        print()

        data = ChallengeData('~/AA2IL/states.xls')
        needed = data.needed_challenge(dx_station.country,'20M',0)
        print(('20M needed=',needed))
        needed = data.needed_challenge(dx_station.country,'2018',0)
        print(('2018 needed=',needed))
        
        sys.exit(0)

        dx_station = Station("KG4WH")
        print(dx_station)
        pprint(vars(dx_station))

        dx_station = Station("AA2IL")
        print(dx_station)
        pprint(vars(dx_station))

        dx_station = Station("DH1TW")
        print(dx_station)
        pprint(vars(dx_station))

        dx_station = Station("VA7IO")
        print(dx_station)
        pprint(vars(dx_station))

        # This one is broke - should return Canada
        dx_station = Station("CZ4A")
        print(dx_station)
        pprint(vars(dx_station))

        sys.exit(0)

    if True:
        print('Hey 1')
        cty_dir = '~/Python/data/'
	cty = load_cty(cty_dir+"cty.plist")              #Load Country File
        print('Hey 2')

        print(cty)
	#prefix = obtain_prefix(call)
        #print prefix
        sys.exit(0)
    
    print('Reading log...')
    qsos = parse_adif(LOG_NAME)
    print(('# QSOs in log=',len(qsos),type(qsos)))
    
    #calls = [ x['call'] for x in qsos ]
    #print calls
    now = datetime.utcnow().replace(tzinfo=UTC)
    print((now,now.replace(tzinfo=None)))
    #now2 = datetime.strptime(now.strftime("%Y%m%d"), "%Y%m%d")
    qsos2=[]
    for qso in qsos:
        date_off = datetime.strptime( qso["qso_date_off"]+" "+qso["time_off"] , "%Y%m%d %H%M%S") \
                           .replace(tzinfo=UTC)
        age = (now - date_off).total_seconds() # In seconds

        #age = (now - date_off).total_seconds() / 60. # In minutes
        #print date_off
        #print age
        #print age / (24*60.)       # In days
        #sys.exit(0)
        if age < 5*24*3600:
            qsos2.append(qso)

    print(('# recent QSOs in log=',len(qsos2),type(qsos2)))
    print('... Read log')
    sys.exit(0)

