#!/usr/bin/env python
#
# framework_init.py
#
# Framework initialisation routines
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
import os
import configparser as cp
import multiprocessing as mp
import queue
from time import sleep

# Application imports
from defs import *
import td_manager
import routing
import forwarder
import imc_server

"""
There are two startup routines which offload boilerplate stuff from the user.

The first is called at start-of-day to read the topology configuration and put
together the global parts of the environment

The second is called from each process loop whether that is within the main
process of other Python processes on the same machine.

These calls are made on each machine in the topology although the configuration
file for each will be different.

"""

# Single class contains all startup routines
class FrameworkInit:
    
    def __init__(self, cfg):
        self.__cfg = cfg
        
    # Call this after any startup local initialisation
    def start_of_day(self):
        # Where cfg is the fully qualified path to a configuration file
        
        # Read the configuration
        topology = self.__get_config(self.__cfg)
        sections = topology.sections()
        if LOCAL in sections:
            print('Found LOCAL section, parsing processes...')
            local = ['LOCAL', []]
            for key in topology['LOCAL']:
                # Retrieve and split value
                val = topology['LOCAL'][key]
                tasks = val.strip().split(',')
                local[1].append([key, tasks])
                print('Found process %s with tasks %s' % ( key, tasks))
        if REMOTE in sections:
            print('Found REMOTE section, parsing processes...')
            remote = ['REMOTE', []]
            for key in topology['REMOTE']:
                # Retrieve and split value
                val = topology['REMOTE'][key]
                tasks, params = val.split(':')
                tasks = tasks.strip().split(',')
                ip, inport, outport = params.strip().split(',')
                remote[1].append([key, tasks, ip, int(inport), int(outport)])
                print('Found process %s with tasks %s and parameters %s, %s, %s' % ( key, tasks, ip, inport, outport))

    # This reader ensures we retain the case of the options
    # otherwise they are all converted to lower case
    def __get_config(self, cfg):
        config = cp.ConfigParser()
        config.optionxform=str
        try:
            config.read(cfg)
            return config
        except Exception as e:
            log.error(e)
        