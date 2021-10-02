#!/usr/bin/env python
#
# td_manager.py
#
# Manages task data
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
from time import sleep

# Application imports
    
# ====================================================================
# Manager for task dictionary

class TdManager:
    
    def __init__(self):
        # Task dictionary
        self.__td = {}

        # Task dictionary lock
        self.__lock = threading.Lock()
    
    def lock(self):
        self.__lock.acquire()
        
    def release(self):
        self.__lock.release()
        
    def store_task_ref(self, name, ref):
        self.lock()
        self.__td[name] = ref
        self.release()
    
    def get_task_ref(self, name):
        self.lock()
        if name in  self.__td:
            r = self.__td[name]
        else:
            r = None
        self.release()
        return r
    
    def get_all_ref(self):
        self.lock()
        refs = self.__td.values()
        self.release()
        return refs
    
    def get_raw(self):
        return self.__td
    
    def rm_task_ref(self, name):
        self.lock()
        if name in  self.__td:
            del self.__td[name]
        self.release()
        