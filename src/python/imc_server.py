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
class ImcServer(threading.Thread):
    
    def __init__(self, td_man, desc, qs):
        super(ImcServer, self).__init__()
        self.__td_man = td_man
        # desc is of the form
        # [[["E", "F"],"192,168.1.200", 10000, 10001], [["G", "H"],"192,168.1.201", 10000, 10001]]
        # We listen for remote data on the first port and dispatch it locally
        # We listen for local requests on q to be sent to a remote destination and dispatch to the second port
        self.__qs = qs
        self.__desc = desc
        self.__term = False
        
        # Open sockets
        self.__rlist = []
        
        for dest in desc[1]:
            device, task_id, ip_addr, out_port, in_port = dest
            self.__rlist.append(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
            #wlist.append(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
        index = 0
        # Bind to all adapters on the receiving ports
        for sock in self.__rlist:
            sock.bind(('', desc[1][index][3]))
            index += 1
        
    def terminate(self):
        self.__term = True
        
    def run(self):
        while not self.__term:
            # Wait for remote data
            r, w, x = select.select(self.__rlist,[], [], 0.0)
            if len(r) > 0:
                # Data available
                for s in r:
                    data, _ = s.recvfrom(512)
                    data = pickle.loads(data)
                    # Dispatch locally
                    self.__process(data)
            #else:
                #try:
                #    data = self.__q.get(block=False)
                #    data = pickle.dumps(data)
                #    # Send message
                #    s.sendto(data, (dest[0], dest[2]))
                #except queue.Empty:
                #    continue
            sleep(0.05)
        print("ImcServer terminating...")
            
    def __process(self, msg):
        # A message is of this form but data is opaque to us
        # [name, [*] | [sender, [*]]]
        name, data = msg
        # Lookup the destination
        item = self.__td_man.get_task_ref(name)
        if item == None:
            # No destination 
            print("ImcServer - destination %s not found!" % (name))
        else:
            # Dispatch
            _, d, q = item
            d(data)
            
