#!/usr/bin/env python
#
# framework_test.py
#
# Publish/Subscribe implementation
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
import multiprocessing as mp
import threading
import queue
from time import sleep
from enum import Enum

# Application imports
import gen_server as gs
import pub_sub as ps
import routing

# ====================================================================
# Test code
# NOTE: This code uses the match keyword as we are trying to emulate a
# receive loop and pattern matching is by far the most elegant way.
# However, this needs Python 3.10 which as of writing is pre-release.
# You don't need pattern matching, it's just tidier.

class FrTest:

    def __init__(self, name, gs_inst, GS1, GS2, route_manager, q={}):
        
        self.__gs_inst = gs_inst
        self.GS1 = GS1
        self.GS2 = GS2
        print(q)
        router = routing.Routing(route_manager)
        print("Name:", name, router.get_routes(), sep=' ')
    
    def run(self):
        
        # Make 2 gen-servers
        self.__gs_inst.server_new(self.GS1, self.gs1_dispatch)
        self.__gs_inst.server_new(self.GS2, self.gs2_dispatch)
        
        # Regiater main thread
        q = queue.Queue()
        self.__gs_inst.server_reg("MAIN", None, self.main_dispatch, q)
        
        # Send message to A and B from main thread
        self.__gs_inst.server_msg(self.GS1, ["Message 1 to %s" % self.GS1])
        self.__gs_inst.server_msg(self.GS2, ["Message 1 to %s" % self.GS2])
        self.__gs_inst.server_msg(self.GS1, ["Message 2 to %s" % self.GS1])
        self.__gs_inst.server_msg(self.GS2, ["Message 2 to %s" % self.GS2])
        
        # Retrieve messages for us
        msg = self.__gs_inst.server_msg_get("MAIN")
        while msg != None:
            print(msg)
            msg = self.__gs_inst.server_msg_get("MAIN")
        
        # Send message to A and B from main thread that require a response
        self.__gs_inst.server_msg(self.GS1, ["MAIN", "Message to %s expects response" % self.GS1])
        self.__gs_inst.server_msg(self.GS2, ["MAIN", "Message to %s expects response" % self.GS2])
        
        # Retrieve responses for us
        resp = self.__gs_inst.server_response_get("MAIN")
        while resp != None:
            print(resp)
            resp = self.__gs_inst.server_response_get("MAIN")
        
        # Subscribe A & B to a topic
        #ps.ps_subscribe( "GS1", "TOPIC-1")
        #ps.ps_subscribe( "GS2", "TOPIC-1")
        
        # Publish TOPIC-1
        #ps.ps_publish( "TOPIC-1", "Publish to TOPIC-1" )
        
        # Get topic list
        #print("Subscribers: ", ps.ps_list("TOPIC-1"))
        
        # Terminate servers
        sleep(1)
        self.__gs_inst.server_term_all()
        
    def main_dispatch(self, msg):
        match msg:
            case [data]:
                match data:
                    case "Message 1 to MAIN":
                        print("MAIN Message 1 ", data)
                    case "Message 2 to MAIN":
                        print("MAIN Message 2 ", data)
            # Does message need a response
            case [sender, data]:
                print("MAIN [%s, %s] " % (sender, data))
                self.__gs_inst.server_response( sender, "Response to %s from MAIN" % (sender) )
            case _:
                print("MAIN [unknown message %s]" % (msg)) 
    
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
                        self.__gs_inst.server_msg( "MAIN", ["Message to MAIN from %s[1]" % self.GS1] )
                        self.__gs_inst.server_msg( self.GS2, ["Message to %s from %s[1]" % (self.GS2, self.GS1)] )
                    case MSGS.MSG2.value:
                        print("%s - Message 2 [%s]" % (self.GS1, str(data)))
                        self.__gs_inst.server_msg( "MAIN", ["Message to MAIN from %s[2]" % self.GS1] )
                        self.__gs_inst.server_msg( self.GS2, ["Message to %s from %s[2]" % (self.GS2, self.GS1)] )
                    case MSGS.MSG3.value:
                        print("%s-%s [1]" % (self.GS2, self.GS1))
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
                        self.__gs_inst.server_msg( "MAIN", ["Message to MAIN from %s[1]" % self.GS2] )
                        self.__gs_inst.server_msg( self.GS1, ["Message to %s from %s[1]" % (self.GS1, self.GS2)] )
                    case MSGS.MSG2.value:
                        print("%s Message 2 [%s]" % (self.GS2, str(data)))
                        self.__gs_inst.server_msg( "MAIN", ["Message to MAIN from %s[2]" % self.GS2] )
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
def run_parent_process(route_manager):
    router = routing.Routing(route_manager)
    router.add_route("MAIN", ["A", "B"])
    gs_inst = gs.GenServer()
    FrTest("PARENT", gs_inst, "A", "B", route_manager).run()

# Run child instance tests
def run_child_process(route_manager):
    router = routing.Routing(route_manager)
    router.add_route("CHILD", ["C", "D"])
    gs_inst = gs.GenServer()
    q1 = mp.Queue()
    q2 = mp.Queue()
    p = mp.Process(target=FrTest("CHILD", gs_inst, "C", "D", route_manager, {"PARENT": q1, "CHILD": q2}).run)
    p.start()
    
# Test entry point  
if __name__ == '__main__':
    # Make the one and only shared routing manager to store routes in a dict
    route_manager = mp.Manager().dict()
    # Kick off a parent and child process
    t1 = threading.Thread(target=run_parent_process, args=(route_manager,))
    t1.start()
    t2 = threading.Thread(target=run_child_process, args=(route_manager,))
    # Wait for completion
    t2.start()
    t1.join()
    t2.join()

