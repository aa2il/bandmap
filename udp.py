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
from utilities import freq2band
from datetime import datetime
from cluster_feed import digest_spot
import pytz

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
            
            # Name:Client_name
            if mm[1]=='?':
                print('UDP MSG HANDLER: Server name query')
                msg2='Name:BANDMAP\n'
                sock.send(msg2.encode())
            else:
                print('UDP MSG HANDLER: Server name is',mm[1])
            return
                
        elif mm[0]=='RunFreq' and mm[1] in ['UP','DOWN']:

            # Do nothing - this is too slow so its handled in the SDR for now
            print('UDP MSG HANDLER: RunFreq - Move along, Nothing to see here')
            return

            # Sift through spots an find a gap to run in
            frq=float(mm[2])
            band = freq2band(1e-3*frq)
            print('UDP MSG HANDLER: RunFreq - frq=',frq,'\tband=',band)
            spots = self.P.gui.collect_spots(band,not mm[1]=='UP')
            print('spots=',spots)

            flast=None
            MIN_DF=1e-3*500
            for x in spots:
                f  = x.frequency
                if not flast:
                    flast = f
                df = abs( f - flast )
                print(x.dx_call,'\t',flast,'\t',f,'\t',df)
                if df>MIN_DF:
                    if (mm[1]=='UP' and flast>frq and f>frq) or \
                       (mm[1]=='DOWN' and flast<frq and f<frq):
                        frq2=0.5*(f+flast)
                        msg='RunFreq:TRY:'+str(frq2)
                        print('UDP MSG HANDLER: RunFreq - Suggested freq=',frq2,
                              '\nSending msg=',msg)
                        #self.P.udp_server.Broadcast(msg)
                        sock.send(msg.encode())
                        return
                flast = f
            print('UDP MSG HANDLER: RunFreq - Unable to suggest a freq')
            return
                
        elif mm[0]=='SPOT':

            # SPOT:CALL:FREQ
            print('\nUDP: Received SPOT:',mm)
            call=mm[1]
            freq=float(mm[2])
            mode=mm[3]
            print(call,freq,mode)
            UTC = pytz.utc
            now = datetime.utcnow().replace(tzinfo=UTC)
            line = 'DX de %-9s %8.1f  %-12s %-30s %4sZ' % \
                ('AA2IL'+'-#:',freq,call,mode+' 0 dB',
                 now.strftime("%H%M") )
            print(line)
            digest_spot(self.P.gui,line)
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
                # spots = self.P.gui.current
                spots = self.P.gui.collect_spots(band)
                for x in spots:
                    a.append(x.dx_call)
                    a.append(x.frequency)
                    try:
                        a.append(x.color)
                    except:
                        #a.append('white')
                        match = self.P.gui.B4(x,band)
                        c,c2,age=self.P.gui.spot_color(match,x)
                        a.append(c2)
                a=str(a)
                msg2='SpotList:'+band+':'+a+'\n'
                #print('\nReply:',msg2)

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
     
