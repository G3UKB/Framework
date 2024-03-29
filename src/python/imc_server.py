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
import multiprocessing as mp
from time import sleep

# Application imports
from defs import *
import td_manager

# ====================================================================
# PUBLIC
# API

# The imc task
class ImcServer():
    
    def __init__(self, ports, queues, ctl_q):
        super(ImcServer, self).__init__()
        
        # ports - are a list of ports on which to listen
        # queues - is a dictionary {proc_name: (in_q, out_q), ...}
        #
        # Process:
        #   is to listen on the given ports. If data is received it is sent on the output q
        #       to the destination process. Message is [dest_proc, data].
        #   is to monitor the input q where data will be of the form:
        #       ["192,168.1.200", 10000, [data to be dispatched]]
        #   we send the data message to the given end point.
        
        self.__qs = queues
        self.__ports = ports
        self.__ctl_q = ctl_q
        self.__term = False
        
        # Open and bind sockets
        self.__rlist = []
        for port in self.__ports:
            self.__s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.__rlist.append(self.__s)
            self.__s.bind(('', port))
        
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
                    # data is of the form [task, message]
                    data = pickle.loads(data)
                    #print('Got data from socket ', data)
                    # Dispatch on the output q on all channels we have (there should only be one at present)
                    # Someone needs to be listening on this q to dispatch the message to the correct task
                    # TBD this should be in framework manager to listen and dispatch on a separate thread.
                    for q in self.__qs.values():
                        q[0].put(data)
                        #print('Dispatched on q ', q[0])
            else:
                for q in self.__qs.values():
                    try:
                        data = q[1].get(block=False)
                    except Exception as err:
                        continue
                    # Data is of the form [task-name, [message, ip, port]]
                    #print('Got data from q ', data)
                    task_name, [message, ip, port] = data
                    message = pickle.dumps([task_name, message])
                    # Send message
                    self.__s.sendto(message, (ip, port))
                    #print('Sent data to ', ip, port)
            try:
                data = self.__ctl_q.get(block=False)
                if data =="QUIT":
                    break
            except Exception as err:
                continue
            sleep(0.05)
        print("ImcServer terminating...")

            
