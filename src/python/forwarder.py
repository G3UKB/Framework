#!/usr/bin/env python
#
# forwarder.py
#
# Process message forwarder
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
import threading
import queue
from time import sleep

# Application imports
import td_manager

# ====================================================================
# PUBLIC
# API

# The forwarding task
class FwdServer(threading.Thread):
    
    def __init__(self, td_man):
        super(FwdServer, self).__init__()
        self.__td_man = td_man
        self.__term = False
        
    def terminate(self):
        self.__term = True
        
    def run(self):
        while not self.__term:
            for q in qs:
                try:
                    item = self.__q.get(block=False)
                    # Process message
                    self.__process(item)
                except Queue.Empty:
                    continue
            sleep(0.05)
        print("FwdServer terminating...")
            
    def __process(self, msg):
        # A message is of this form but data is opaque to us
        # [name, [*] | [sender, [*]]]
        name, data = msg
        # Lookup the destination
        item = self.__td_man.get_task_ref(name)
        if item == None:
            # No destination 
            print("FwdServer - destination %s not found!" % (name))
        else:
            # Dispatch
            _, d, q = item
            d(data)
            
