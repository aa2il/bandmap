#! /usr/bin/python3
################################################################################
#
# tcp_client.py - Rev 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
#    Simple tcp server to effect allow clients to communicate to app.
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
import socket 
import select
from threading import Thread,Event
import time

################################################################################

# TCP Client object
class TCP_Client(Thread):
    
    def __init__(self,host,port,BUFFER_SIZE = 1024): 
        Thread.__init__(self) 
        if not host:
            host='127.0.0.1'
        self.host=host
        self.port=port
        self.BUFFER_SIZE = BUFFER_SIZE = 1024
        
        print('TCP Client:',host,port)

        self.tcpClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        self.tcpClient.connect((host, port))
        self.Stopper = Event()

        self.socks = [self.tcpClient]        
 
    # Function to listener for new connections and/or data from clients
    def Listener(self): 
        print('Listener Client ...')

        # Run until stopper is set
        while not self.Stopper.isSet():
            time.sleep(1)

            # Get list of sockets 
            #print('Getting list')
            #readable,writeable,inerror = select.select(self.socks,self.socks,self.socks,0)
            readable,writeable,inerror = select.select(self.socks,[],[],0)
            #print('readable=',readable,'\twriteable=',writeable,'\tinerror=',inerror)
            
            # iterate through readable sockets
            #i=0
            for sock in readable:
                # read from server
                data = sock.recv(self.BUFFER_SIZE)
                if not data:
                    print('\r{}:'.format(sock.getpeername()),'disconnected')
                    readable.remove(sock)
                    self.socks.remove(sock)
                    sock.close()
                else:
                    print('\r{}:'.format(sock.getpeername()),data)
                        
            # a simple spinner to show activity
            #i += 1
            #print('/-\|'[i%4]+'\r',end='',flush=True)

        # Close socket
        self.tcpClient.close()
        print('Listerner: Bye bye!')

    def Send(self,msg):

        sock = self.tcpClient
        addr = sock.getsockname()
        print('Sending',msg,'to',addr,'...')
        try:
            sock.send(msg.encode())
        except:
            print('Send: Problem with socket')
            print(sock)
            

if __name__ == '__main__':
    TCP_IP = '127.0.0.1' 
    TCP_PORT = 2004 

    client = TCP_Client(TCP_IP,TCP_PORT)
    worker = Thread(target=client.Listener, args=(), name='TCP Client' )
    worker.setDaemon(True)
    worker.start()

    while True:
        #print('zzzzzzzzzzzzzzzzz....')
        MESSAGE = input("Enter Response or exit:")
        if MESSAGE == 'exit':
            client.Stopper.set()
            print('Main exiting')
            break
        else:
            client.Send(MESSAGE)
        time.sleep(1)

    print('Joining ...')
    worker.join()
    print('Done.')

    sys.exit(0)

"""

# This is some code to explore address resolution
hostname = socket.gethostname()
dns_resolved_addr = socket.gethostbyname(hostname)
port = 2004
print('hostname=',hostname)
print('dns_resolved_addr',dns_resolved_addr)
if dns_resolved_addr=='127.0.1.1':                        # Not sure why it gets resolved this way!
    #host='127.0.0.1'
    host='localhost'
else:
    host=dns_resolved_addr
print('host=',host)
 
"""
