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

class Routing:
    
    def __init__(self, router):
        self.__routes = router
        self.__lk = Lock()
        
    def add_route(self, process, tasks):
        self.__lk.acquire()
        self.__routes[process] = tasks
        self.__lk.release()
        
    def get_route(self, process):
        r = None
        self.__lk.acquire()
        if process in self.__routes:
            r = self.__routes[name]
        self.__lk.release()
        return r
    
    def get_routes(self):
        r = None
        self.__lk.acquire()
        r = self.__routes
        self.__lk.release()
        return r
    
    def process_for_task(self, task):
        r = None
        self.__lk.acquire()
        for process in self.__routes:
            if task in self.__routes[process]:
                r = process
                break
        self.__lk.release()
        return r
                
            
    