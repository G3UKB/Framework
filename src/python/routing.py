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
    
    def __init__(self, router, qs):
        
        # Router is the single instance of the shared router dictionary
        # Queues are defined as follows:
        # {process-name: (q1,q2), process_name: (...), ..., "IMC": (q3,)}
        # Such that the process is the target and the queues are q1 = input, q2 = output
        # For remote targets there is only one q which is the local q to send to the imc_server
        
        self.__routes = router
        self.__lk = Lock()
        self.__qs = qs
    
    # Add a new route    
    def add_route(self, target, desc):
        # target can be LOCAL or REMOTE
        # The descriptor can contain
        #   [proc_name, [[task_name, task_name, ...]]
        #   for processes residing on this machine
        # or for processes residing on another machine
        #   [proc_name (aka device), [[task_name, task_name, ...], IP-Addr (or DNS name), in-port, out-port]]
        self.__lk.acquire()
        self.__routes[target] = desc
        self.__lk.release()
    
    #  Get desc and Q for process   
    def get_route(self, process):
        r = None
        self.__lk.acquire()
        if process in self.__routes[LOCAL]:
            r = self.__routes[LOCAL][process]
        elif process in self.__routes[REMOTE]:
            r = self.__routes[REMOTE][process]
        self.__lk.release()
        if process in self.__qs:
            return r, self.__qs[process]
        else:
            return r, None
    
    # Return all routes and associated Q's
    def get_routes(self):
        r = None
        self.__lk.acquire()
        r = self.__routes
        self.__lk.release()
        return r, self.__qs
    
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
            print(routes[LOCAL])
            if task in routes[LOCAL][1]:
                r = process
                found = True
                break
        if not found:
            for process in routes[REMOTE]:
                if task in routes[REMOTE][1]:
                    r = process
                    break
        self.__lk.release()
        if r in self.__qs:
            return r, self.__qs[process]
        else:
            return r, None
    
    