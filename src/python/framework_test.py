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
import queue
from time import sleep

# Application imports
from fr_common import *
import gen_server as gs
import pub_sub as ps

# ====================================================================
# Test code
# NOTE: This code uses the match keyword as we are trying to emulate a
# receive loop and pattern matching is by far the most elegant way.
# However, this needs Python 3.10 which as of writing is pre-release.
# You don't need pattern matching, it's just tidier.

def main_dispatch(msg):
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
            gen_server_response( sender, "Response to %s from MAIN" % (sender) )
        case _:
            print("MAIN [unknown message %s]" % (msg)) 

def gs1_dispatch(msg):
    match msg:
        case "INIT":
            print("INIT GS1")
        case [data]:
            match data:
                case "Message 1 to GS1":
                    print("GS1 - Message 1 ", data)
                    gs.gen_server_msg( "MAIN", ["Message to MAIN from GS1[1]"] )
                    gs.gen_server_msg( "GS2", ["Message to GS2 from GS1[1]"] )
                case "Message 2 to GS1":
                    print("GS1 - Message 2 ", data)
                    gs.gen_server_msg( "MAIN", ["Message to MAIN from GS1[2]"] )
                    gs.gen_server_msg( "GS2", ["Message to GS2 from GS1[2]"] )
                case "Message to GS1 from GS2[1]":
                    print("GS2-GS1 [1]")
                case "Message to GS1 from GS2[2]":
                    print("GS2-GS1 [2]")
                case "Publish to TOPIC-1":
                    print("GS1 - Got TOPIC-1")
                case _:
                    print("GS1 [unknown message %s]" % (msg))
        # Does message need a response
        case [sender, data]:
            print("GS1 [%s, %s] " % (sender, data))
            gs.gen_server_response( sender, ["Response to %s from GS1" % (sender)] )
        case _:
            print("GS1 [unknown message %s]" % (msg)) 

def gs2_dispatch(msg):
    match msg:
        case "INIT":
            print("INIT GS2")
        case [data]:
            match data:
                case "Message 1 to GS2":
                    print("GS2 Message 1 ", data)
                    gs.gen_server_msg( "MAIN", ["Message to MAIN from GS2[1]"] )
                    gs.gen_server_msg( "GS1", ["Message to GS1 from GS2[1]"] )
                case "Message 2 to GS2":
                    print("GS2 Message 2 ", data)
                    gs.gen_server_msg( "MAIN", ["Message to MAIN from GS2[2]"] )
                    gs.gen_server_msg( "GS1", ["Message to GS1 from GS2[2]"] )
                case "Message to GS2 from GS1[1]":
                    print("GS1-GS2 [1]")
                case "Message to GS2 from GS1[2]":
                    print("GS1-GS2 [2]")
                case "Publish to TOPIC-1":
                    print("GS2 - Got TOPIC-1")
                case _:
                    print("GS1 [unknown message %s]" % (msg))
        # Does message need a response
        case [sender, data]:
            print("GS2 [%s, %s] " % (sender, data))
            gs.gen_server_response( sender, ["Response to %s from GS2" % (sender)] )
        case _:
            print("GS2 [unknown message %s]" % (msg))
    
def main():
    # Make 2 gen-servers
    gs.gen_server_new("GS1", gs1_dispatch, MPTYPE.THREAD)
    gs.gen_server_new("GS2", gs2_dispatch, MPTYPE.PROCESS)
    
    # Regiater main thread
    q = queue.Queue()
    gs.gen_server_reg( "MAIN", None, main_dispatch, q )
    
    # Send message to A and B from main thread
    gs.gen_server_msg( "GS1", ["Message 1 to GS1"] )
    gs.gen_server_msg( "GS2", ["Message 1 to GS2"] )
    gs.gen_server_msg( "GS1", ["Message 2 to GS1"] )
    gs.gen_server_msg( "GS2", ["Message 2 to GS2"] )
    
    # Retrieve messages for us
    msg = gs.gen_server_msg_get("MAIN")
    while msg != None:
        print(msg)
        msg = gs.gen_server_msg_get("MAIN")
    
    # Send message to A and B from main thread that require a response
    gs.gen_server_msg( "GS1", ["MAIN", "Message to GS1 expects response"] )
    gs.gen_server_msg( "GS2", ["MAIN", "Message to GS2 expects response"] )
    
    # Retrieve responses for us
    resp = gs.gen_server_response_get("MAIN")
    while resp != None:
        print(resp)
        resp = gs.gen_server_response_get("MAIN")
    
    # Subscribe A & B to a topic
    ps.ps_subscribe( "GS1", "TOPIC-1")
    ps.ps_subscribe( "GS2", "TOPIC-1")
    
    # Publish TOPIC-1
    ps.ps_publish( "TOPIC-1", "Publish to TOPIC-1" )
    
    # Get topic list
    print("Subscribers: ", ps.ps_list("TOPIC-1"))
    
    # Terminate servers
    sleep(1)
    gs.gen_server_term_all()
  
# Test entry point  
if __name__ == '__main__':
    main()

