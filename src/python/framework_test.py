#!/usr/bin/env python
#
# framework_test.py
#
# Framework test and example code
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
import multiprocessing as mp
import threading
import queue
from time import sleep
from enum import Enum

# Application imports
from defs import *
import gen_server as gs
import pub_sub as ps
import td_manager
import routing
import forwarder
import imc_server

# ====================================================================
# Test code
# NOTE: This code uses the match keyword as we are trying to emulate a
# receive loop and pattern matching is by far the most elegant way.
# However, this needs Python 3.10 which as of writing is pre-release.
# You don't need pattern matching, it's just tidier.

class FrTest:

    def __init__(self, ar_task_ids, ar_imc_ids, qs, mp_dict, mp_event):
        
        # Save params
        self.__tid = ar_task_ids
        self.__imc = ar_imc_ids
        self.__qs = qs
        self.__mp_dict = mp_dict
        self.__mp_event = mp_event
        
    # Entry point for process
    def run(self):
        
        self.GS1 = self.__tid[0]
        self.GS2 = self.__tid[1]

        # We need to create local queues for the IMC messages
        # as we cannot pass these across a process boundary
        self.__imc_qs = {}
        for desc in self.__imc[1]:
            self.__imc_qs[desc[0]] = queue.Queue()     
        
        # ======================================================
        # General setup that will always be required
        # Make a task data manager
        td_man = td_manager.TdManager()
    
        # Make and run a forward server
        fwds = forwarder.FwdServer(td_man, self.__qs)
        fwds.start()
    
        # Make a router
        router = routing.Routing(self.__mp_dict, self.__qs)
        # Add routes for this process
        for desc in self.__tid[1]:
            router.add_route(self.__tid[0], desc)

        # Make an IMC server
        imc_inst = imc_server.ImcServer(td_man, self.__imc, self.__imc_qs)
        imc_inst.start()
        # Add IMC routes
        for desc in self.__imc[1]:
            router.add_route(self.__imc[0], desc)
        
        # Make a GenServer instance to manage gen servers in this process
        self.__gs_inst = gs.GenServer(td_man, router)
        
        # End general setup
        # ======================================================
        
        # Print context
        #print("Context: ", os.getpid(), self.__name, router.get_routes(), self.__qs, sep=' ')
        
        # Following is test code as an example of usage
        # Make 2 gen-servers
        self.__gs_inst.server_new(self.GS1, self.gs1_dispatch)
        self.__gs_inst.server_new(self.GS2, self.gs2_dispatch)
        
        # Regiater our thread for our process
        q = queue.Queue()
        self.__gs_inst.server_reg(self.__name, None, self.main_dispatch, q)
        
        # Wait for ready
        self.__mp_event.wait()
        
        # Send message to A and B from main thread
        self.__gs_inst.server_msg(self.GS1, ["Message 1 to %s" % self.GS1])
        self.__gs_inst.server_msg(self.GS2, ["Message 1 to %s" % self.GS2])
        self.__gs_inst.server_msg(self.GS1, ["Message 2 to %s" % self.GS1])
        self.__gs_inst.server_msg(self.GS2, ["Message 2 to %s" % self.GS2])
        
        # Try message to C
        if self.__name == "PARENT":
            # This is A and B servers so try a send to C
            self.__gs_inst.server_msg("C", ["Interprocess to C from %s" % self.__name])
        else:
            # This is B and C severs so try a send to A
            self.__gs_inst.server_msg("A", ["Interprocess to A from %s" % self.__name])
        
        # Retrieve messages for us
        msg = self.__gs_inst.server_msg_get(self.__name)
        while msg != None:
            print(msg)
            msg = self.__gs_inst.server_msg_get(self.__name)
        
        # Send message to A and B from main thread that require a response
        self.__gs_inst.server_msg(self.GS1, [self.__name, "Message to %s expects response" % self.GS1])
        self.__gs_inst.server_msg(self.GS2, [self.__name, "Message to %s expects response" % self.GS2])
        
        # Retrieve responses for us
        resp = self.__gs_inst.server_response_get(self.__name)
        while resp != None:
            print(resp)
            resp = self.__gs_inst.server_response_get(self.__name)
        
        # Subscribe A & B to a topic
        #ps.ps_subscribe( "GS1", "TOPIC-1")
        #ps.ps_subscribe( "GS2", "TOPIC-1")
        
        # Publish TOPIC-1
        #ps.ps_publish( "TOPIC-1", "Publish to TOPIC-1" )
        
        # Get topic list
        #print("Subscribers: ", ps.ps_list("TOPIC-1"))
        
        # Terminate servers
        sleep(1)
        fwds.terminate()
        fwds.join()
        self.__gs_inst.server_term_all()
        
    def main_dispatch(self, msg):
        class MSGS(Enum):
            MSG1 = "Message 1 to %s" % (self.__name)
            MSG2 = "Message 2 to %s" % (self.__name)
        match msg:
            case [data]:
                match data:
                    case MSGS.MSG1.value:
                        print("%s Message 1 ", (self.__name, data))
                    case MSGS.MSG2.value:
                        print("%s Message 2 ", (self.__name, data))
            # Does message need a response
            case [sender, data]:
                print("%s [%s, %s] " % (self.__name, sender, data))
                self.__gs_inst.server_response( sender, "Response to %s from %s" % (sender, self.__name) )
            case _:
                print("%s [unknown message %s]" % (self.__name, msg)) 
    
    def gs1_dispatch(self, msg):
        class MSGS(Enum):
            MSG1 = "Message 1 to %s" % (self.GS1)
            MSG2 = "Message 2 to %s" % (self.GS1)
            MSG3 = "Message to %s from %s[1]" % (self.GS1, self.GS2)
            MSG4 = "Message to %s from %s[2]" % (self.GS1, self.GS2)
        
        match msg:
            case "INIT":
                print("INIT %s" % self.GS1)
            case [data]:
                match data:
                    case MSGS.MSG1.value:
                        print("%s - Message 1 [%s]" % (self.GS1, str(data)))
                        self.__gs_inst.server_msg( self.__name, ["Message to %s from %s[1]" % (self.__name, self.GS1)] )
                        self.__gs_inst.server_msg( self.GS2, ["Message to %s from %s[1]" % (self.GS2, self.GS1)] )
                    case MSGS.MSG2.value:
                        print("%s - Message 2 [%s]" % (self.GS1, str(data)))
                        self.__gs_inst.server_msg( self.__name, ["Message to %s from %s[2]" % (self.__name, self.GS1)] )
                        self.__gs_inst.server_msg( self.GS2, ["Message to %s from %s[2]" % (self.GS2, self.GS1)] )
                    case MSGS.MSG3.value:
                        print("%s-%s [1]" % (self.GS2, self.GS1))
                    case "Interprocess to A from CHILD":
                        print("Got - Interprocess to A from CHILD")
                    case "Interprocess to C from PARENT":
                        print("Got - Interprocess to C from PARENT")
                    case MSGS.MSG4.value:
                        print("%s-%s [2]" % (self.GS2, self.GS1))
                    case "Publish to TOPIC-1":
                        print("%s - Got TOPIC-1" % self.GS1)
                    case _:
                        print("%s [unknown message %s]" % (self.GS1, msg))
            # Does message need a response
            case [sender, data]:
                print("%s [%s, %s] " % (self.GS1, sender, data))
                self.__gs_inst.server_response( sender, ["Response to %s from %s" % (sender, self.GS1)] )
            case _:
                print("%s [unknown message %s]" % (self.GS1, msg)) 
    
    def gs2_dispatch(self, msg):
        class MSGS(Enum):
            MSG1 = "Message 1 to %s" % (self.GS2)
            MSG2 = "Message 2 to %s" % (self.GS2)
            MSG3 = "Message to %s from %s[1]" % (self.GS2, self.GS1)
            MSG4 = "Message to %s from %s[2]" % (self.GS2, self.GS1)
            
        match msg:
            case "INIT":
                print("INIT %s" % self.GS2)
            case [data]:
                match data:
                    case MSGS.MSG1.value:
                        print("%s Message 1 [%s]" % (self.GS2, str(data)))
                        self.__gs_inst.server_msg( self.__name, ["Message to %s from %s[1]" % (self.__name, self.GS2)] )
                        self.__gs_inst.server_msg( self.GS1, ["Message to %s from %s[1]" % (self.GS1, self.GS2)] )
                    case MSGS.MSG2.value:
                        print("%s Message 2 [%s]" % (self.GS2, str(data)))
                        self.__gs_inst.server_msg( self.__name, ["Message to %s from %s[2]" % (self.__name, self.GS2)] )
                        self.__gs_inst.server_msg( self.GS1, ["Message to %s from %s[2]" % (self.GS1, self.GS2)] )
                    case MSGS.MSG3.value:
                        print("%s-%s [1]" % (self.GS1, self.GS2))
                    case MSGS.MSG4.value:
                        print("%s-%s [2]" % (self.GS1, self.GS2))
                    case "Publish to TOPIC-1":
                        print("%s - Got TOPIC-1" % self.GS2)
                    case _:
                        print("%s [unknown message %s]" % (self.GS2, msg))
            # Does message need a response
            case [sender, data]:
                print("%s [%s, %s] " % (self.GS2, sender, data))
                self.__gs_inst.server_response( sender, ["Response to %s from %s" % (sender, self.GS2)] )
            case _:
                print("%s [unknown message %s]" % (self.GS2, msg))
    
# Run parent instance tests
def run_parent_process(ar_task_ids, ar_imc_ids, d_process_qs, mp_dict, mp_event):
    # Kick off a test 
    FrTest(ar_task_ids, ar_imc_ids, d_process_qs, mp_dict, mp_event).run()

# Run child instance tests
def run_child_process(ar_task_ids, ar_imc_ids, d_process_qs, mp_dict, mp_event):
    # Kick off a test
    p = mp.Process(target=FrTest(ar_task_ids, ar_imc_ids, d_process_qs, mp_dict, mp_event).run)
    p.start()
    
# Test entry point  
if __name__ == '__main__':
    
    # Make the one and only shared dictionary
    mp_manager = mp.Manager()
    mp_dict = mp_manager.dict()
    mp_event = mp_manager.Event()
    
    # Make multiprocessor.Queues between each process
    # There is a pair of queues for each communication channel
    # The first in the pair the listens for messages from 'name'.
    # The second sends messages to 'name'.
    q1 = mp.Queue()
    q2 = mp.Queue()
    
    # These should be in a config file and not hard coded!
    # Define the local processes
    # Tag LOCAL defines a list of process name against task names.
    # In general there is only one entry but for consistency with IMC its a list
    local_procs_1 = [LOCAL, [["PARENT", ["A", "B"]],]]
    local_procs_2 = [LOCAL, [["CHILD", ["C", "D"]],]]
    # Define the remote processes
    # Tag REMOTE defines a list of process/device name against task names + connectivity information.
    remote_procs = [REMOTE, [["DEVICE-A", ["E", "F"],"192,168.1.200", 10000, 10001]], ["DEVICE-B", ["G", "H"],"192,168.1.201", 10002, 10003]]
    # These are multiprocessing queues and need to be created here to pass to each process
    # as they need to know the respective send and receive q's
    parent_qs = {"CHILD": (q1, q2),}
    child_qs = {"PARENT": (q2, q1),}
    
    # Run processes, starting on their own thread
    # main process
    t1 = threading.Thread(target=run_parent_process, args=(local_procs_1, remote_procs, parent_qs, mp_dict, mp_event))
    t1.start()
    sleep(2)
    # and a child process
    t2 = threading.Thread(target=run_child_process, args=(local_procs_2, remote_procs, child_qs, mp_dict, mp_event))
    t2.start()
    sleep(1)
    
    # Ready to go
    mp_event.set()
    
    # Wait for completion
    t1.join()
    t2.join()

