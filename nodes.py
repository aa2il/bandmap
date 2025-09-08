################################################################################
#
# nodes.py - Rev 1.0
# Copyright (C) 2025 by Joseph B. Attili, joe DOT aa2il AT gmail DOT com
#
# List of cluster nodes for bandmap
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

