#!/usr/bin/env python
#
# gen_server.py
#
# Generic Server implementation
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

"""
    This module is loosly based on the erlang gen-server in that it emulates a 
    process oriented message passing concurrency model.
    Note, concurrent, not parallel due to the global lock.

    PUBLIC INTERFACE:
        Main words for gen-server and message management:
        
        NOTE: As this is intended to use the pattern matching introduced in 3.10 the messages must be sequences in order to
        bind directly to variables in the match statements.
  
        Create a new gen-server with the task name 'name'. As everything is performed using the task name you should
        never need to keep the reference. The dispatcher is a callable that will process the messages. One special message is
        "INIT" which is sent once the gen-server is running. This is effectively an extension of __init__() to allow any
        initialisation processing to be done.
  
            gen_server_new( name, dispatcher )

        Ask the gen-server with task name 'name' or all servers to terminate. The server is designed to always allow proper termination.
  
            gen_server_term( name )
            gen_server_term_all()

        Send a message to the gen-server with task name 'name', calling dispatcher with the opaque data *. The opaque data can be
        any as it is passed directly to the dispatcher. However, if a response is required the convention is [sender, *] where *
        is the opaque data and the sender is the task name to send the response to.
  
            gen_server_msg( name, [*] | [sender, *] )
        
        Retrieve message for tasks that are not gen-servers. Returns the full content. Such tasks could be the main thread or threads that
        want to communicate in other ways but also use the message infrastructure (see registration). As these tasks are not gen-servers no
        message loop is executing so messages are not automatically dispatched. Calling gen_server_msg_get() on a periodic basis will cause
        any queued messages to be dispatched to the calling task.
        
            [*] | [sender, *] = gen_server_msg_get()

        When the dispatcher receives a message from gen_server_msg() by whatever route it must be aware of the structure of the opaque data
        and if a response is required the array must include the sender name. In order to respond it should call gen_server_response()
        with the sender name 'name', and * the opaque response data.
  
            gen_server_response(name, *)
  
        Retrieves responses for tasks that are not gen-servers. For the same reason as messages these are not dispatched automatically.
        
            [*] = gen_server_response_get()
        
        If a task which is not a gen-server wishes to participate in the messaging framework it must be registered in the task registry
        with 'task' the task reference and 'name' the task name. The dispatcher is the callable to dispatch messages to and it must also
        create its own queue and pass the reference.
  
            gen_server_reg( name, task, dispatcher, q )
  
        Remove a registration of a non-gen-server task.
  
            gen_server_reg_rm( name )
        
        When it is required to terminate one or all tasks gen_server_term[_all]() is used to terminate tasks. However it is good practice 
        to wait for the task to exit.
  
            gen_server_wait_single_task( name )
            gen_server_wait_all()
 
    Messaging scenarios
    ===================
    There are quite a number of sender/receiver combinations that require specific protocols. These are pretty much the same
    whether messaging is direct through the gen-server or through the pub/sub system which dispatches through gen-server.
 
    Interactions are gen-server to gen-server, gen-server to non gen-server and the special case of to the main thread which
    is important for a GUI application where interaction with the GUI must be from the main thread.
    
        1. Sender : gen-server, receiver : gen-server. 
            This is the simplest scenario as everything is managed by the gen-server. Messages are sent using gen_server_msg(). Both
            messages and responses are dispatched automatically. Note that both sending and receiving are dispatched via the task-q
            so always arrive on the thread of the receiving task, not of the sending task.
            
        2. Sender : gen-server, receiver : normal user task.
            In this case the normal user task must be registered using gen_server_reg() so its task object can be retrieved by task name.
            Sending is the same as before using gen_server_msg(). However, the receiver will not get that message automatically because
            there is no gen-server to take it from the q.
                
        3. Sender : normal user task, receiver gen-server.
            This is similar to [2]. The sender uses gen_server_msg() The receiver will automatically get the message. If a response is
            required then sender must call gen_server_response_get() as it will not automatically get the response. 
                
        4.  Sender : gen-server, receiver : MAIN-TASK
            This is similar to [2] above except the main task is the recipient. The message is dispatched as normal to the task q and
            must be retrieved manually. As it's retrieved on the main thread it is GUI safe.
                
        5. Sender : MAIN-TASK, receiver : gen-server.
            Again similar to [2] above. The task uses gen_server_msg() to send and if it wants to receive a reply it can use
            gen_server_response_get() to pick up the reply.
                
"""

# System imports
import threading
import queue
from time import sleep

# Application imports

# ====================================================================
# PUBLIC
# API

class GenServer:
   
    def __init__(self, td_man, router):
        self.__router = router
        self.__td_man = td_man

    def server_new(self, name, dispatcher):
        
        # Assign a queue
        q = queue.Queue()
        # Create a new thrd-server task
        thrd_server = ThrdServer(name, self.__td_man, q)
            
        # Add to the task registry
        self.__td_man.store_task_ref(name, [thrd_server, dispatcher, q])
        # Start the gen-server loop
        thrd_server.start()
        # Initialise task
        dispatcher("INIT")
        
    def server_term(self, name):
         item = self.__td_man.get_task_ref(name)
         if item != None:
            t, d, q = item
            t.terminate()
            t.join()
            
    def server_term_all(self):
        items = self.__td_man.get_all_ref()
        for item in items:
            t, d, q = item
            if t != None:
                t.terminate()
                t.join()
    
    def server_msg(self, name, message):
        item = self.__td_man.get_task_ref(name)
        if item == None:
            # Which process is the message destination
            q = self.get_target(name)
            if q != None:
                # Forward the message to the process q
                msg = [name, message]
                q.put(msg)
        else:
            # For this process
            msg = [name, message]
            _, d, q = item
            q.put(msg)
    
    def server_msg_get(self, name):
        item = self.__td_man.get_task_ref(name)
        if item != None:
            _, d, q = item
            try:
                msg = q.get(block=True, timeout=0.1)
                return msg
            except queue.Empty:
                return None
            
    def server_response(self, name, response):
        item = self.__td_man.get_task_ref(name)
        if item == None:
            # Which process is the message destination
            q = self.get_target(name)
            if q != None:
                # Forward the message to the process q
                msg = [name, message]
                q.put(msg)
        else:
            # Local dispatch
            msg = [name, response]
            _, d, q = item
            q.put(msg)
    
    def server_response_get(self, name):
        item = self.__td_man.get_task_ref(name)
        if item != None:
            _, d, q = item
            try:
                msg = q.get(block=True, timeout=0.1)
                return msg
            except queue.Empty:
                return None
    
    def server_reg(self, name, t, dispatcher, q):
        # Add to the task registry
        self.__td_man.store_task_ref(name, [t, dispatcher, q])
    
    def server_reg_rm(self, name):
        # Remove from task registry
       self.__td_man.rm_task_ref( name )

    def get_target(self, name):
        # Which process is the message destination
        process, (_, q) = self.__router.process_for_task(name)
        if process == None:
            # Not known
            print("GenServer - destination %s not found in router table!" % (name))
            return None
        elif q == None:
            print("GenServer - destination %s found but no associated queue!" % (name))
            return None
        else:
            return q
        
# ====================================================================
# PRIVATE

# The gen-server thread task
class ThrdServer(threading.Thread):
    
    def __init__(self, name, td_man, q):
        super(ThrdServer, self).__init__()
        self.__name = name
        self.__td_man = td_man
        self.__q = q
        self.__term = False
        
    def terminate(self):
        self.__term = True
        
    def run(self):
        while not self.__term:
            try:
                item = self.__q.get(block=True, timeout=1)
                # Process message
                self.__process(item)
            except queue.Empty:
                continue
        print("GenServer %s terminating..." % (self.__name))
            
    def __process(self, msg):
        # A message is of this form but data is opaque to us
        # [name, [*] | [sender, [*]]]
        name, data = msg
        # Lookup the destination
        item = self.__td_man.get_task_ref(name)
        if item == None:
            # No destination  
            print("GenServer - destination %s not found!" % (name))
        else:
            # Dispatch
            _, d, q = item
            d(data)  
