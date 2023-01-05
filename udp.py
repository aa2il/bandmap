#########################################################################################
#
# udp.py - Rev. 1.0
# Copyright (C) 2022 by Joseph B. Attili, aa2il AT arrl DOT net
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

from tcp_client import *
#from tcp_server import *

#########################################################################################

# UDP Message handler for bandmap
def udp_msg_handler(self,sock,msg):
    id=sock.getpeername()
    print('UDP MSG HANDLER: id=',id,'\tmsg=',msg.rstrip())

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
                
     

    
# Function to open UDP client
def open_udp_client(P,port):

    if not port:
        port = 7474
        #port = KEYER_UDP_PORT
        #port = BANDMAP_UDP_PORT
    
    try:
        print('Opening UDP client ...')
        P.udp_client = TCP_Client(P,None,port,Client=True,
                                  Handler=udp_msg_handler)
        #P.udp_client = TCP_Server(P,None,port,Server=False,
        #Handler=udp_msg_handler)
        worker = Thread(target=P.udp_client.Listener,args=(), kwargs={}, name='UDP Client' )
        worker.setDaemon(True)
        worker.start()
        P.THREADS.append(worker)
        
        #P.udp_client.Connect(None,KEYER_UDP_PORT)
        
        return True
    except Exception as e: 
        print('OPEN UDP CLIENT: Exception Raised:',e)
        print('--- Unable to connect to UDP socket ---')
        P.udp_client = None
        return False
    
