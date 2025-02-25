#! /usr/bin/python3 -u
################################################################################
#
# get_node_list.py - Rev 1.0
# Copyright (C) 2022 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Function to genearate a list of known cluster nodes
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
from collections import OrderedDict 
import xlrd
from unidecode import unidecode
from dx.spot_processing import Station
from pprint import pprint
from latlon2maiden import *
from numpy import isnan

################################################################################

def get_node_list(P):

    # Read list of nodes
    print('Reading List of Cluster Nodes - fname=',P.NODES_FNAME)
    book  = xlrd.open_workbook(P.NODES_FNAME,formatting_info=True)
    sheet1 = book.sheet_by_name('DX Nodes')
    print(sheet1.nrows,sheet1.ncols)

    nodes=OrderedDict()
    ready=False
    for i in range(1, sheet1.nrows):
        val=unidecode( sheet1.cell(i,0).value )
        #print(i,row)
        if 'K - United States' in val:
            print(i,val,' - There it is!')
            ready=True
            continue
        elif ready:
            done = True
            for j in range(1,sheet1.ncols):
                val=unidecode( str(sheet1.cell(i,j).value) )
                #print(i,sheet1.cell(i,j))
                done = done and val==''                    
            if done:
                print('Done.')
                break
            addr  = unidecode( sheet1.cell(i,0).value ).split()

            loc   = unidecode( sheet1.cell(i,1).value ).split('\n')
            #print(addr,loc)
            if len(loc)>1:
                gridsq=loc[1]
            else:
                gridsq=''

            lat,lon=maidenhead2latlon(gridsq)
            #print(gridsq,lat,lon)
            if isnan(lat):
                call = addr[0].split('-')[0]
                station = Station(call)
                gridsq=latlon2maidenhead(station.latitude,-station.longitude,6)

            dx=distance_maidenhead(P.SETTINGS['MY_GRID'],gridsq)
            if isnan(dx):
                print(dx)
                print(call)
                pprint(vars(station))
                print(gridsq)
                sys.exit(0)

            #port  = unidecode( sheet1.cell(i,2).value )
            sysop = unidecode( sheet1.cell(i,3).value )
            notes = unidecode( sheet1.cell(i,4).value )
                
            nodes[ addr[0] ] =  {'ipaddr'   : addr[-1] ,
                                 'location' : loc[0],
                                 'grid'     : gridsq,
                                 'sysop'    : sysop,
                                 'distance' : dx,
                                 'notes'    : notes}
            #print(addr[0],nodes[ addr[0] ])

    # Sort by distance to me
    nodes2=OrderedDict( sorted(nodes.items(), key= lambda x:x[1]['distance']))
    for key in nodes2.keys():
        print(key,nodes2[key])

