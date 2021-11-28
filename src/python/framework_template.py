#!/usr/bin/env python
#
# framework_template.py
#
# Framework starter code
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
import os, sys
import multiprocessing as mp
import threading
import queue
from time import sleep
from enum import Enum
import pprint

# Application imports
from defs import *
import framework_mgr
import gen_server as gs
import pub_sub as ps
import td_manager
import routing
import forwarder
import imc_server

# ====================================================================
# Starter code
# This code is the simplest possible working framework which can be expanded
# to the actual topology required for the application.

class AppMain:

    def __init__(self, local, remote, imc_queues, local_queues, multiproc_dict, multiproc_event):
        
        # Save params
        self.__local = local
        self.__remote = remote
        self.__imc_queues = imc_queues
        self.__local_queues = local_queues
        self.__multiproc_dict = multiproc_dict
        self.__multiproc_event = multiproc_event
        
    # Entry point for process
    def run(self):
        
        # ======================================================
        # For each process we perform a process initialisation which does the boiler plate stuff
        fm = framework_mgr.ProcessInit(self.__local, self.__remote, self.__imc_queues, self.__local_queues, self.__multiproc_dict)
        # Call start_of_day() to get the task data instance that tracks the tasks this instance creates and the
        # router instance that merges together the data about which process containes which tasks and the
        # associated queues for processes to communicate.
        params = fm.start_of_day()
        td_man = params['TD']           # The task data manager
        router = params['ROUTER']       # The router reference
        self.__gs_inst = params['GS']   # Instance of the gen server class to manage gen server instances
        
        # ======================================================
        # Get the local proc in a more usable state
        # The local proc is of this form:
        # If this is the parent process
        #   ['LOCAL', ['PARENT', ['A', 'B']]]
        # If this is a child process
        #   ['LOCAL', ['CHILD', ['C', 'D']]]
        # Extract our process name
        self.__name = self.__local[1][0]
        # Extract the task names for this process
        # We will call the task names GS1 and GS2 for gen server 1 & 2
        # Not every task has to be a gen server but it does make messaging somewhat easier
        # We need to know what is in our task list as its application dependent.
        self.GS1 = self.__local[1][1][0]
        self.GS2 = self.__local[1][1][1]
      
        # Useful debug context
        #print("Context: ", os.getpid(), self.__name, router.get_routes(), self.__qs, sep=' ')
        
        # Each gen server needs to know its task name and it needs a dispatcher to process
        # and dispatch messages.
        # We use the gs_inst to create new servers. We don't need a refernece as they are self
        # managing.
        self.__gs_inst.server_new(self.GS1, self.gs1_dispatch)
        self.__gs_inst.server_new(self.GS2, self.gs2_dispatch)
        
        # The gen servers start on their own thread. However we might want to send messages to this
        # thread which is not a gen server and could be the main GUI thread.
        # In order to do that we must register the thread with its name and dispatcher in much the same
        # way as the gen servers. The difference is messages have to be pulled rather than being automatic.
        # Register our thread for our process
        # It also needs a q on which to receive messages
        q = queue.Queue()
        # We register the main thread (task) as its own process name for messaging
        self.__gs_inst.server_reg(self.__name, None, self.main_dispatch, q)
        
        # Now all the initialisation is done we wait for the start signal
        self.__multiproc_event.wait()
        
        # ======================================================
        # The rest is application specific so ...
        # Just send and receive a few messages to prove operation and to provide sample exchanges.
        
        # Send one way message to our gen servers from main thread (A&B or C&D)
        self.__gs_inst.server_msg(self.GS1, ["Message to %s from %s main thread" % (self.GS1, self.__name)])
        self.__gs_inst.server_msg(self.GS2, ["Message to %s from %s main thread" % (self.GS2, self.__name)])
        
        # Now send one way message from main thread, parent -> child or child -> parent to first gen server
        if self.__name == "PARENT":
            # This is parent so A and B gen servers, so send to C
            self.__gs_inst.server_msg("C", ["Interprocess to C from %s main thread" % self.__name])
        else:
            # This is child so B and C gen servers, so send to A
            self.__gs_inst.server_msg("A", ["Interprocess to A from %s main thread" % self.__name])
        
        # In this template example the gen servers send a one way message back to this thread
        # As we are not a gen server we have to manually retrieve messages using our task name
        msg = self.__gs_inst.server_msg_get(self.__name)
        while msg != None:
            print('Main thread got message: %s' % msg)
            msg = self.__gs_inst.server_msg_get(self.__name)
        
        # Now send message from main thread to our gen servers that require a response
        # For a response we simply add the name of the task to reply to.
        # For the main task the task name is the same as the process name
        self.__gs_inst.server_msg(self.GS1, [self.__name, "Message to %s from %s expects response" % (self.GS1, self.__name)])
        self.__gs_inst.server_msg(self.GS2, [self.__name, "Message to %s from %s expects response" % (self.GS2, self.__name)])
        
        # As we now expect a response retrieve our messages as before
        resp = self.__gs_inst.server_response_get(self.__name)
        while resp != None:
            print('Main thread got response: %s' % resp)
            resp = self.__gs_inst.server_response_get(self.__name)
        
        # ======================================================
        # Finally send message to remote system(s)
        # A remote connection is defined as e.g. PARENT-A = E,F:192.168.1.200,10000,10001
        # The name is the process name and must be the same as the local process name
        # on that machine. There is one descriptor for each remote process
        # When we send a message to a task on a remote process we only need to use the task
        # name so from the application viewpoint there is no difference between local and remote.
        # However, it is a send and forget message unless it needs a reply so if the other end is
        # not listening there will be no error or a timeout on the reply.
        
        # One-way message
        self.__gs_inst.server_msg("E", ["Intermachine to E from %s" % self.__name])
        # Response expected
        #self.__gs_inst.server_msg("G", [self.__name, "Intermachine to G from %s expects response" % self.__name])
        
        # As we now expect a response retrieve our messages as before
        #resp = self.__gs_inst.server_response_get(self.__name)
        #while resp != None:
        #    print(resp)
        #    resp = self.__gs_inst.server_response_get(self.__name)
        
        # ======================================================
        # use the higher level publish/subscribe system
        # This uses the underlying gen server messaging system but decouples the sender and
        # receiver.
        # Subscribe A & B to a topic
        #ps.ps_subscribe( "GS1", "TOPIC-1")
        #ps.ps_subscribe( "GS2", "TOPIC-1")
        
        # Publish TOPIC-1
        #ps.ps_publish( "TOPIC-1", "Publish to TOPIC-1" )
        
        # Get topic list
        #print("Subscribers: ", ps.ps_list("TOPIC-1"))
        
        # ======================================================
        # Clean up
        sleep(1)
        # Do framework manager end of day
        fm.end_of_day()
        # Terminate all our gen servers
        self.__gs_inst.server_term_all()
     
    # ======================================================
    # Start dispatch methods
    # Dispatcher for main thread
    def main_dispatch(self, msg):
        # We expect two message types from each local gen server
        # We need to match on the exact message text but in reality could be
        # on a msg id as the data is opaque to the framework.
        class MSGS(Enum):
            MSG = "Message to %s" % (self.__name)
        match msg:
            case [data]:
                # Local one way message
                match data:
                    case MSGS.MSG.value:
                        print("%s Message ", (self.__name, data))
            case [sender, data]:
                # RPC type message that requires a response
                print("%s RPC [%s, %s] " % (self.__name, sender, data))
                # Send response to sender
                self.__gs_inst.server_response( sender, "Response to %s from %s" % (sender, self.__name) )
            case _:
                # Message not understood
                print("%s [unknown message %s]" % (self.__name, msg)) 
    
    # ======================================================
    # Dispatcher for gen server 1
    def gs1_dispatch(self, msg):
        class MSGS(Enum):
            MSG1 = "Message to %s from PARENT main thread" % (self.GS1)
            MSG2 = "Message to %s from CHILD main thread" % (self.GS1)
            MSG3 = "Message to %s from %s" % (self.GS1, self.GS2)
        
        match msg:
            case "INIT":
                # Each dispatcher receives an INIT message at start of day
                # so it can perform any necessary initialisation
                print("INIT %s" % self.GS1)
            case [data]:
                match data:
                    case MSGS.MSG1.value:
                        print("%s - Message [%s]" % (self.GS1, str(data)))
                        # Send a one way message back to main task
                        self.__gs_inst.server_msg( self.__name, ["Message to %s from %s" % (self.__name, self.GS1)] )
                        # Send a one way message from this gen server to the other gen server
                        self.__gs_inst.server_msg( self.GS2, ["Message to %s from %s" % (self.GS2, self.GS1)] )
                    case MSGS.MSG2.value:
                        print("%s - Message [%s]" % (self.GS1, str(data)))
                    case MSGS.MSG3.value:
                        print("%s - Message [%s]" % (self.GS1, str(data)))
                    # Interprocess on same machine messages to first gen server only
                    case "Interprocess to A from CHILD main thread":
                        print("%s - %s" % (self.GS1, str(data)))
                    case "Interprocess to C from PARENT main thread":
                        print("%s - %s" % (self.GS1, str(data)))
                    # Using pub/sub system
                    #case "Publish to TOPIC-1":
                    #    print("%s - Got TOPIC-1" % self.GS1)
                    case _:
                        print("%s [unknown message %s]" % (self.GS1, msg))
            # Does message need a response
            case [sender, data]:
                print("%s - [%s, %s] " % (self.GS1, sender, data))
                self.__gs_inst.server_response( sender, ["Response to %s from %s" % (sender, self.GS1)] )
            case _:
                print("%s [unknown message %s]" % (self.GS1, msg)) 
    
    # ======================================================
    # Dispatcher for gen server 2
    def gs2_dispatch(self, msg):
        class MSGS(Enum):
            MSG1 = "Message to %s from PARENT main thread" % (self.GS2)
            MSG2 = "Message to %s from CHILD main thread" % (self.GS2)
            MSG3 = "Message to %s from %s" % (self.GS2, self.GS1)
            
        match msg:
            case "INIT":
                print("INIT %s" % self.GS2)
            case [data]:
                match data:
                    case MSGS.MSG1.value:
                        print("%s - Message [%s]" % (self.GS2, str(data)))
                        # Send a one way message back to main task
                        self.__gs_inst.server_msg( self.__name, ["Message to %s from %s" % (self.__name, self.GS2)] )
                        # Send a one way message from this gen server to the other gen server
                        self.__gs_inst.server_msg( self.GS1, ["Message to %s from %s" % (self.GS1, self.GS2)] )
                    case MSGS.MSG2.value:
                        print("%s - Message [%s]" % (self.GS2, str(data)))
                    case MSGS.MSG3.value:
                        print("%s - Message [%s]" % (self.GS2, str(data)))
                    # Pub/sub system
                    #case "Publish to TOPIC-1":
                    #    print("%s - Got TOPIC-1" % self.GS2)
                    case _:
                        print("%s [unknown message %s]" % (self.GS2, msg))
            # Does message need a response
            case [sender, data]:
                print("%s - [%s, %s] " % (self.GS2, sender, data))
                self.__gs_inst.server_response( sender, ["Response to %s from %s" % (sender, self.GS2)] )
            case _:
                print("%s [unknown message %s]" % (self.GS2, msg))

# =======================================================================================================
# Run parent instance
def run_parent_process(ar_task_ids, ar_imc_ids, d_imc_qs, d_process_qs, mp_dict, mp_event):
    # Directly call the main template code
    AppMain(ar_task_ids, ar_imc_ids, d_imc_qs, d_process_qs, mp_dict, mp_event).run()

# Run child instance
def run_child_process(ar_task_ids, ar_imc_ids, d_imc_qs, d_process_qs, mp_dict, mp_event):
    # Run a separate instance of the main template code via multiprocessing
    p = mp.Process(target=AppMain(ar_task_ids, ar_imc_ids, d_imc_qs, d_process_qs, mp_dict, mp_event).run)
    p.start()

# =======================================================================================================
# Main path code to establish system
def main(config_path):
    
    # Do start-of-day processing
    # Create an instance of GlobalInit
    fm = framework_mgr.GlobalInit(config_path)
    # Run start of day code
    r, global_cfg = fm.start_of_day()
    # Extract parameters from the global configuration response
    local_procs = global_cfg[LOCAL]             # All processes on this machine
    remote_procs = global_cfg[REMOTE]           # All processes on other machines
    q_imc = global_cfg['IMC']                   # Q's to talk to IMC server
    q_local_parent = global_cfg['PARENT']       # The children q pairs given to the parent
    q_local_children = global_cfg['CHILDREN']   # The parent q pair given to each child
    mp_dict = global_cfg['DICT']                # The global dictionary for routing info
    mp_event = global_cfg['EVENT']              # The global startup event
    # Split local procs
    # The local procs can contain one or more processes with its task list
    # We need these separated as each will be given to a separate process
    expanded_local_procs = []
    for proc in local_procs[1]:
        expanded_local_procs.append([LOCAL, proc])
        
    # ========================================================
    # Run processes
    # It usually makes sense to run the child processes first and then start the main process loop, especially if its a GUI
    # process. Otherwise it can be simpler to make another thread the main process thread then just wait for things to
    # terminate here.
    
    # *******TODO Give IMC q's and put them to the router
    
    # The first process in the list should probably be the main process otherwise look for a specific name.
    # Start the main process via a thread.
    t1 = threading.Thread(target=run_parent_process, args=(expanded_local_procs[0], remote_procs, q_imc, q_local_parent, mp_dict, mp_event))
    t1.start()
    
    # Start any child processes via another thread.
    t2 = threading.Thread(target=run_child_process, args=(expanded_local_procs[1], remote_procs, q_imc, q_local_children['CHILD'], mp_dict, mp_event))
    t2.start()
    sleep(1)
    
    # We don't want things to start until all processes have done initialisation.
    # At the appropriate point a process should wait on the global event
    mp_event.set()
    
    # Wait for completion of processes
    t1.join()
    t2.join()
    
    # End-of-day processing
    fm.end_of_day()
    sleep(1)
    print("Template run complete")

# =======================================================================================================    
# Entry point   
if __name__ == '__main__':
    # Check parameters
    if len(sys.argv) != 2:
        print("framework_template <full path to configuration file>")
    else:
        if os.path.isfile(sys.argv[1]):
            # Enter main program
            main(sys.argv[1])
        else:
            print("Configuration file at %s does not exist!" % sys.argv[1])
