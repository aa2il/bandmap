#########################################################################################
#
# udp.py - Rev. 1.0
# Copyright (C) 2022-4 by Joseph B. Attili, aa2il AT arrl DOT net
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

import sys
from pprint import pprint
import zlib
from utilities import freq2band
from datetime import datetime
from collections import OrderedDict
import pytz

#########################################################################################

# UDP Message handler for bandmap
def bm_udp_msg_handler(self,sock,msg):
    id=sock.getpeername()
    print('BM UDP MSG HANDLER: id=',id,'\tmsg=',msg.rstrip())

    if False:
        print("P=")
        pprint(vars(self.P))
        print(' ')
    
    msgs=msg.split('\n')
    for m in msgs:
        mm=m.split(':')
        print('BM UDP MSG HANDLER: m=',m,'\tmm[0]=',mm[0])

        if mm[0]=='Name':
            
            # Name:Client_name
            if mm[1]=='?':
                print('BM UDP MSG HANDLER: Server name query')
                msg2='Name:BANDMAP\n'
                sock.send(msg2.encode())
            else:
                print('BM UDP MSG HANDLER: Server name is',mm[1])
            return
                
        elif mm[0]=='RunFreq' and mm[1] in ['UP','DOWN']:

            # Do nothing - this is too slow so its handled in the SDR for now
            print('BM UDP MSG HANDLER: RunFreq - Move along, Nothing to see here')
            return

            # Sift through spots an find a gap to run in
            frq=float(mm[2])
            band = freq2band(1e-3*frq)
            print('BM UDP MSG HANDLER: RunFreq - frq=',frq,'\tband=',band)
            spots = self.P.bm_gui.collect_spots(band,not mm[1]=='UP',OVERRIDE=True)
            print('\tspots=',spots)

            flast=None
            MIN_DF=1e-3*500
            for x in spots:
                f  = x.frequency
                if not flast:
                    flast = f
                df = abs( f - flast )
                print('\t',x.dx_call,'\t',flast,'\t',f,'\t',df)
                if df>MIN_DF:
                    if (mm[1]=='UP' and flast>frq and f>frq) or \
                       (mm[1]=='DOWN' and flast<frq and f<frq):
                        frq2=0.5*(f+flast)
                        msg='RunFreq:TRY:'+str(frq2)
                        print('BM UDP MSG HANDLER: RunFreq - Suggested freq=',frq2,
                              '\nSending msg=',msg)
                        #self.P.udp_server.Broadcast(msg)
                        sock.send(msg.encode())
                        return
                flast = f
            print('BM UDP MSG HANDLER: RunFreq - Unable to suggest a freq')
            return
                
        elif mm[0]=='SPOT':

            # SPOT:CALL:FREQ
            print('\nBM UDP MSG HANDLER: Received SPOT:',mm)
            call=mm[1]
            freq=float(mm[2])
            mode=mm[3]
            print('\t',call,freq,mode)
            UTC = pytz.utc
            now = datetime.utcnow().replace(tzinfo=UTC)
            line = 'DX de %-9s %8.1f  %-12s %-30s %4sZ' % \
                ('AA2IL'+'-#:',freq,call,mode+' 0 dB',
                 now.strftime("%H%M") )
            print(line)
            self.P.ClusterFeed.digest_spot(line)
            return
     
        elif mm[0]=='LOG':

            # LOG:CALL:BAND:MODE:DATE_OFF:TIME_OFF
            print('\nUDP: Received SPOT:',mm)
            qso = OrderedDict()
            qso['call']         = mm[1]
            qso['band']         = mm[2]
            qso['mode']         = mm[3]
            qso['qso_date_off'] = mm[4]
            qso['time_off']     = mm[5]
            self.P.qsos.append(qso)
            print('\tqso=',qso)
            self.P.ClusterFeed.lb_update()
            return
            
        elif mm[0]=='SpotList':
            
            if mm[1]=='Refresh':
                print('BM UDP MSG HANDLER: Received SpotList Refresh')
                return
            elif mm[1]=='?':
                band=self.P.GUI_BAND
            else:
                band=mm[1]
            
            if mm[1]=='?' or mm[2]=='?':
                spot_list_query(self.P,sock,band)
                
            return
                    
        print('UDP MSG HANDLER: Not sure what to do with this',mm)
     


def spot_list_query(P,sock=None,band=None):
    
    print('BM UDP SPOTLIST QUERY: band=',band)
    if not hasattr(P,'gui') and False:
        print('BM UDP SPOTLIST QUERY: No Gui?')
        return

    if not band:
        band=P.GUI_BAND
        print('\tband=',band)
    
    a=[]
    spots = P.bm_gui.collect_spots(band,OVERRIDE=True)
    for x in spots:
        color=x.color
        if color=='lightgreen':
            #continue
            color='lg'
        elif color=='yellow':
            color='y'
        elif color=='red':
            color='r'
        a.append(x.dx_call)
        a.append(x.frequency)
        try:
            a.append(color)
        except:
            match = P.ClusterFeed.B4(x,band)
            c,c2,age=P.ClusterFeed.spot_color(match,x)
            a.append(c2)
    a=str(a)
    msg2='SpotList:'+band+':'+a+'\n'
    #print('\nReply:',msg2)

    if len(msg2)>1000:
        # Compress text
        msg22 = zlib.compress(msg2.encode())
        
        # Check size of text b4 and after compression
        if True:
            a_size=sys.getsizeof(msg2)
            print('msg2=',msg2,'\nSize of original msg',a_size)
            a2_size=sys.getsizeof(msg22)
            print("Size of compressed msg:",a2_size)

        # Decompressing text
        #a3=zlib.decompress(msg22)
            
        #Check size of text after decompression
        #a3_size=sys.getsizeof(a3)
        #print("Size of decompressed text",a3_size,'\na3=',a3)
        #print("\nDifference of size= ", a_size-a2_size)

        print('BM UDP SPOTLIST QUERY: Sending compressed message ...')
        if sock:
            sock.send(msg22)
        else:
            P.udp_server.Broadcast(msg22)
        
    else:
        
        print('BM UDP SPOTLIST QUERY: Sending message ...')
        if sock:
            sock.send(msg2.encode())
        else:
            P.udp_server.Broadcast(msg2)
                    
    print('BM UDP SPOTLIST QUERY: Done.')
        
