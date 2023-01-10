#########################################################################################
#
# udp.py - Rev. 1.0
# Copyright (C) 2022-3 by Joseph B. Attili, aa2il AT arrl DOT net
#
# UDP messaging for bandmap.
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

from tcp_server import *
from pprint import pprint

#########################################################################################

# UDP Message handler for bandmap
def udp_msg_handler(self,sock,msg):
    id=sock.getpeername()
    print('UDP MSG HANDLER: id=',id,'\tmsg=',msg.rstrip())

    if False:
        print("P=")
        pprint(vars(self.P))
        print(' ')
    
    msgs=msg.split('\n')
    for m in msgs:
        print('UDP MSG HANDLER: m=',m,len(m))

        mm=m.split(':')
        if mm[0]=='Name':
            if mm[1]=='?':
                print('UDP MSG HANDLER: Server name query')
                msg2='Name:BANDMAP\n'
                sock.send(msg2.encode())
            else:
                print('UDP MSG HANDLER: Server name is',mm[1])
                
        elif mm[0]=='SpotList':
            band=mm[1]
            if mm[2]=='?':
                print('UDP MSG HANDLER: SpotList query',band)
                a=[]
                for x in self.P.gui.current:
                    a.append(x.dx_call)
                    a.append(x.frequency)
                    try:
                        a.append(x.color)
                    except:
                        a.append('white')
                msg2='SpotList:'+band+':'+str(a)+'\n'
                print('\tReply:',msg2)
                sock.send(msg2.encode())
            else:
                print('UDP MSG HANDLER: Not sure what to do with this',mm)
     
