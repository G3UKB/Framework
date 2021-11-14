#!/usr/bin/env python
#
# framework_mgr.py
#
# Framework initialisation and closedown routines
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
import gen_server as gs

"""
There are two startup routines which offload boilerplate stuff from the user.

The first is called at start-of-day to read the topology configuration and put
together the global parts of the environment

The second is called from each process loop whether that is within the main
process of other Python processes on the same machine.

These calls are made on each machine in the topology although the configuration
file for each will be different.

"""

#==================================================
# Global startup
class GlobalInit:
    
    #==============================================================================================  
    def __init__(self, cfg):
        self.__cfg = cfg
        
        self.__local = None
        self.__remote = None
        self.__is_local = False
        self.__is_remote = False
     
    #==============================================================================================   
    # Call this after any startup local initialisation
    def start_of_day(self):
        # Where cfg is the fully qualified path to a configuration file
        
        #===================================================================
        # Read the configuration
        try:
            topology = self.__get_config(self.__cfg)
        except Exception as e:
            print('Problem reading configuratioon! [%s]' % str(e))
            return False, {}
        sections = topology.sections()
        if len(sections) == 0 or LOCAL not in sections:
            print('The configuration file appears to be empty or has no LOCAL section!')
            return False, {}
        try:
            if LOCAL in sections:
                self.__is_local = True
                print('Found LOCAL section, parsing processes...')
                self.__local = ['LOCAL', []]
                for key in topology['LOCAL']:
                    # Retrieve and split value
                    val = topology['LOCAL'][key]
                    tasks = val.strip().split(',')
                    self.__local[1].append([key, tasks])
                    print('Found process %s with tasks %s' % ( key, tasks))
            if REMOTE in sections:
                self.__is_remote = True
                print('Found REMOTE section, parsing processes...')
                self.__remote = ['REMOTE', []]
                for key in topology['REMOTE']:
                    # Retrieve and split value
                    val = topology['REMOTE'][key]
                    tasks, params = val.split(':')
                    tasks = tasks.strip().split(',')
                    ip, inport, outport = params.strip().split(',')
                    self.__remote[1].append([key, tasks, ip, int(inport), int(outport)])
                    print('Found process %s with tasks %s and parameters %s, %s, %s' % ( key, tasks, ip, inport, outport))
        except Exception as e:
            print('There was a problem with the configuration [%s]' % str(e))
            return False, {}

        #===================================================================
        # Setup global Manager
        # The one and only multiprocessing.Manager
        self.__mp_manager = mp.Manager()
        # Make the shared dictionary
        self.__mp_dict = self.__mp_manager.dict()
        # Make a shared startup event
        self.__mp_event = self.__mp_manager.Event()
        
        #===================================================================
        # Create local q's
        if self.__is_local:
            #===================================================================
            # We need a pair of multiprocessor.Queue between each communicating instance
            # The first in the pair listens for messages from 'name'.
            # The second sends messages to 'name'.
            # q_local will be of the form {name: {name: [task_name, task_name, ...]}, name: ...}
            # The parent process wants all of the child q's for receive and send
            # Each child wants the parent q's
            self.__q_local_children = {}
            first = True
            parent_name = ''
            for proc in self.__local[1]:
                q1 = mp.Queue()
                q2 = mp.Queue()
                if first:
                    # Main process
                    # Note name
                    parent_name = proc[0]
                    first = False
                else:
                    # Child process
                    self.__q_local_children[proc[0]] = {parent_name: [q1, q2]}
        
            # We now have all the child procs with q's that point to the parent
            # Add all q's to the parent but reverse the receive/send q's
            self.__q_local_parent = {}
            for proc in self.__q_local_children.keys():
                self.__q_local_parent[proc] = [self.__q_local_children[proc][parent_name][1], self.__q_local_children[proc][parent_name][0]]
    
        #===================================================================
        # Make an IMC server which runs as a remote service
        if self.__is_remote:
            # Create ports list
            # This is the ports to listen on
            # Ports can be repeated if there are multiple processes on a node
            # We only want to have each listen port once
            ports = []
            for desc in self.__remote[1]:
                if desc[3] not in ports:
                    ports.append(desc[3])
            # Create queues
            # there is an in and out q for each process on this machine
            # to talk to the IMC server
            # {proc_name: (q, q), ...}
            queues = {}
            for proc in self.__local[1]:   
                q1 = mp.Queue()
                q2 = mp.Queue()
                queues[proc[0]] = (q1, q2)
            # Special control q to send control messages
            self.__imc_ctl_q = mp.Queue()
            # Create and start the IMC process            
            #self.__imc = mp.Process(target=imc_server.ImcServer(ports, queues, self.__imc_ctl_q).run)
            #self.__imc.start()
    
        #===================================================================
        # Return the startup objects
        return True, {LOCAL: self.__local,
                      REMOTE: self.__remote,
                      'PARENT': self.__q_local_parent,
                      'CHILDREN': self.__q_local_children,
                      'DICT': self.__mp_dict,
                      'EVENT': self.__mp_event}

    #==============================================================================================   
    # Call this at end of day
    def end_of_day(self):
        #if self.__is_remote: 
            # Send QUIT to imc control q
        #    self.__imc_ctl_q.put("QUIT")
        #    self.__imc.join()
        pass
    
    #==============================================================================================      
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


#==================================================
# Process startup
class ProcessInit:
    
    #==============================================================================================   
    def __init__(self, local_procs, remote_procs, local_queues, mp_dict):
        self.__local_procs = local_procs
        self.__remote_procs = remote_procs
        self.__local_queues = local_queues
        self.__mp_dict = mp_dict
        
    #==============================================================================================   
    # Call for each process startup
    def start_of_day(self):
        # ======================================================
        # General setup for each process
        # Make a task data manager
        self.__td_man = td_manager.TdManager()
    
        # Make and run a forward server
        self.__fwds = forwarder.FwdServer(self.__td_man, self.__local_queues)
        self.__fwds.start()
    
        # Make a router
        self.__router = routing.Routing(self.__mp_dict, self.__local_queues)
        # Add routes for this process
        self.__router.add_route(self.__local_procs[0], self.__local_procs[1])

        # Add IMC routes
        for desc in self.__remote_procs[1]:
            self.__router.add_route(self.__remote_procs[0], desc)
        
        # Make a GenServer instance to manage gen servers in this process
        self.__gs_inst = gs.GenServer(self.__td_man, self.__router)
        
        # Return the process specific objects
        return {'TD': self.__td_man, 'ROUTER': self.__router, 'GS': self.__gs_inst}
    
    #==============================================================================================   
    # Call this at end of process
    def end_of_day(self):
        self.__fwds.terminate()
        self.__fwds.join()
    