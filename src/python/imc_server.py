#!/usr/bin/env python
#
# imc_server.py
#
# Inter-Machine-Communications server
# 
# Copyright (C) 2021 by G3UKB Bob Cowdery
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#    
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#    
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#    
#  The author can be reached by email at:   
#     bob@bobcowdery.plus.com
#

# System imports
import socket
import select
import pickle
import threading
from time import sleep

# Application imports
from defs import *
import td_manager

# ====================================================================
# PUBLIC
# API

# The imc task
class ImcServer():
    
    def __init__(self, ports, queues):
        super(ImcServer, self).__init__()
        
        # ports - are a list of ports on which to listen
        # queues - is a dictionary {proc_name: (in_q, out_q), ...}
        #
        # Process:
        #   is to listen on the given ports. If data is received it is sent on the output q
        #       to the destination process. Message is [dest_proc, data].
        #   is the monitor the input q where data will be of the form:
        #       ["192,168.1.200", 10000, [data to be dispatched]]
        #   we send the data message to the given end point.
        
        self.__qs = queues
        self.__ports = ports
        self.__term = False
        
        # Open and bind sockets
        self.__rlist = []
        for port in self.__ports:
            self.__rlist.append(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
            sock.bind(('', port)
        
    def terminate(self):
        self.__term = True
        
    def run(self):
        while not self.__term:
            # Wait for remote data with zero timeout
            r, w, x = select.select(self.__rlist,[], [], 0.0)
            if len(r) > 0:
                # Data available
                for s in r:
                    data, _ = s.recvfrom(512)
                    data = pickle.loads(data)
                    [proc, data] = data
                    # Dispatch on the output q
                    self.__qs[proc][1].put(data)
            else:
                for q in self.__qs.value():
                    try:
                        data = q[0].get(block=False)
                    except queue.Empty:
                        continue
                    data = pickle.dumps(data)
                    [ip, port, [data]] = data
                    # Send message
                    s.sendto(data, (ip, port))
            sleep(0.05)
        print("ImcServer terminating...")

            
