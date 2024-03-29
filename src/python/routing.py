#!/usr/bin/env python
#
# routing.py
#
# Manages shared routing data
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
from multiprocessing import Manager, Lock
from time import sleep
import pprint

# Application imports
from defs import *

"""
    Shared multiprocessing.Manager to store shared routing state. This is a dictionary of the form:
        {process-name: [task-name, task-name, ...], process-name [...], ...}
    It provides a lookup to find usually the Process within which a Task is implemented. Both names
    are strings set when routes are added. It would be nice to be able to store an associated Queue
    with the Process as this is the means to dispatch a message to another Process where it can be
    forwarded to the appropriate Task. Unfortunately a Queue is not pickleable and can only be passed
    directly to child processes so a dictionary of process name(s) to Queue is passed to all Processes.
    This means that the hierarchy must be known in advance on program initialisation.
    
    The router passed in is an instance of multiprocessing.Manager. This is passed as an argument to each
    process and then each Process can create an instance of Routing to provide the convienience access methods.
"""

# System imports
import copy

# Application imports
from defs import *

class Routing:
    
    def __init__(self, router, local_qs, imc_qs):
        
        # Router is the single instance of the shared router dictionary
        # Queues are defined as follows:
        # {process-name: (q1,q2), process_name: (...), ..., "IMC": (q3,)}
        # Such that the process is the target and the queues are q1 = input, q2 = output
        # For remote targets there is only one q which is the local q to send to the imc_server
        self.__routes = router
        self.__lk = Lock()
        self.__local_qs = local_qs
        self.__imc_qs = imc_qs
    
    # Add a new route    
    def add_route(self, target, desc):
        #print('add_route ', target, desc)
        
        # target can be LOCAL or REMOTE
        # The descriptor can contain
        #   [proc_name, [[task_name, task_name, ...]]
        #   for processes residing on this machine
        # or for processes residing on another machine
        #   [proc_name (aka device), [[task_name, task_name, ...], IP-Addr (or DNS name), in-port, out-port]]
        self.__lk.acquire()
        # Dict is a proxy, can't just append to elements
        if target in self.__routes:
            current = copy.deepcopy(self.__routes[target])
            if desc not in current:
                current.append(desc)
                self.__routes[target] = current
        else:
            self.__routes[target] = [desc]
        self.__lk.release()
    
    #  Get desc and Q for process   
    def get_route(self, process):
        r = None
        self.__lk.acquire()
        d = find_process(LOCAL, process)
        if d != None:
            r = d
        else:
            d = find_process(REMOTE, process)
            if d != None:
                r = d
        self.__lk.release()
        if process in self.__local_qs:
            return r, self.__local_qs[process]
        elif process in self.__imc_qs:
                return r, self.__imc_qs[process]
        else:
            return r, None
    
    # Return all routes and associated Q's
    def get_routes(self):
        r = None
        self.__lk.acquire()
        r = self.__routes
        self.__lk.release()
        return r, self.__local_qs, self.__imc_qs
    
    # Return process and Q for given task
    # The process could be this process, another on this machine or a remote machine
    def process_for_task(self, task):
        r = None
        self.__lk.acquire()
        # Can't directly iterate a proxy
        # This is a simple work round as the dict is small
        routes = copy.deepcopy(self.__routes)
        found = False
        for process in routes[LOCAL]:
            if task in process[1]:
                r = process[0]
                found = True
                break
        if not found:
            for process in routes[REMOTE]:
                if task in process[1]:
                    r = process[0]
                    break
        self.__lk.release()
        if r in self.__local_qs:
            return r, self.__local_qs[r]
        elif r in self.__imc_qs:
            return r, self.__imc_qs[r]
        else:
            return r, None
 
    # Is this task remote
    def is_remote(self, task):
        self.__lk.acquire()
        r = False
        routes = copy.deepcopy(self.__routes)
        for process in routes[REMOTE]:
            if task in process[1]:
                r = True
        self.__lk.release()
        return r
        
    # Return network address for given task
    def address_for_task(self, task):
        r = []
        self.__lk.acquire()
        routes = copy.deepcopy(self.__routes)
        # Can't directly iterate a proxy
        # This is a simple work round as the dict is small
        routes = copy.deepcopy(self.__routes)
        for process in routes[REMOTE]:
            # Process of the form [process-name, [tasks], IP, port-in, port-out]
            if task in process[1]:
                r = [process[2], process[3]]
        self.__lk.release()
        return r
        
    # Return the descriptor for process or None
    def find_process(self, target, process):
        
        l = self.__routes[target]
        for d in l:
            if d[0] == process:
                return d
        return None
    
