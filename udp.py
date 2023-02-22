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
import zlib

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
        mm=m.split(':')
        print('UDP MSG HANDLER: m=',m,'\tmm[0]=',mm[0])

        if mm[0]=='Name':
            
            if mm[1]=='?':
                print('UDP MSG HANDLER: Server name query')
                msg2='Name:BANDMAP\n'
                sock.send(msg2.encode())
            else:
                print('UDP MSG HANDLER: Server name is',mm[1])
            return
                
        elif mm[0]=='SpotList':
            
            if mm[1]=='Refresh':
                return
            elif mm[1]=='?':
                band=self.P.gui.band.get()
            else:
                band=mm[1]
            
            if mm[1]=='?' or mm[2]=='?':
                print('UDP MSG HANDLER: SpotList query',band)
                if not hasattr(self.P,'gui'):
                    continue
                a=[]
                for x in self.P.gui.current:
                    a.append(x.dx_call)
                    a.append(x.frequency)
                    try:
                        a.append(x.color)
                    except:
                        a.append('white')
                a=str(a)
                msg2='SpotList:'+band+':'+a+'\n'
                print('\nReply:',msg2)

                if len(msg)>1000:
                    # Check size of text
                    #a_size=sys.getsizeof(msg2)
                    #print('msg2=',msg2,'\nSize of original msg',a_size)

                    # Compress text
                    msg22 = zlib.compress(msg2.encode())

                    # Check size of text after compression
                    #a2_size=sys.getsizeof(msg22)
                    #print("Ssize of compressed msg:",a2_size)

                    # Decompressing text
                    #a3=zlib.decompress(msg22)

                    #Check size of text after decompression
                    #a3_size=sys.getsizeof(a3)
                    #print("Size of decompressed text",a3_size,'\na3=',a3)
                    #print("\nDifference of size= ", a_size-a2_size)
                    
                    sock.send(msg22)
                else:
                    sock.send(msg2.encode())
                    
            return
                    
        print('UDP MSG HANDLER: Not sure what to do with this',mm)
     
