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
  
        Create a new gen-server with the task name 'name'. As everything is performed using the task name you should
        never need to keep the reference.
  
            gen_server_new( name )

        Ask the gen-server with task name 'name' or all servers to terminate. The server is designed to always allow proper termination.
  
            gen_server_term( name )
            gen_server_term_all()

        Send a message to the gen-server with task name 'name', calling callable 'callable' with the opaque data *. The opaque data can be
        any as it is passed directly to 'callable'. However, if a response is required the convention is [*, sender, callable] where *
        is the opaque data and the sender is the task name to send the response to and 'callable' is the callable to call.
  
            gen_server_msg( name, callable, [*, optional sender, option callable] )
        
        Retrieve message for tasks that are not gen-servers. Returns the full content. Such tasks could be the main thread or threads that
        want to communicate in other ways but also use the message infrastructure (see registration). As these tasks are not gen-servers no
        message loop is executing so messages are not automatically dispatched. Calling gen_server_msg_get() on a periodic basis will cause
        any queued messages to be dispatched to the 'callable' for the calling task (as registered).
        
            [*, optional sender, option callable] = gen_server_msg_get()

        When the callable receives a message from gen_server_msg() by whatever route it must be aware of the structure of the opaque data
        and if a response is required the array must include the sender name and word to call. In order to respond it should call
        gen_server_response() with the sender name 'name', the callable 'callable' to call and * the opaque response data.
  
            gen_server_response(name, callable, *)
  
        Retrieves responses for tasks that are not gen-servers. For the same reason as messages these are not dispatched automatically.
        
            * = gen_server_response_get()
        
        If a task which is not a gen-server wishes to participate in the messaging framework it must be registered in the task registry
        with 'task' the task reference and 'name' the task name.
  
            gen_server_reg( task, name )
  
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

# Application imports
import threading
import queue

# ====================================================================
# PRIVATE
# Task dictionary
# This will be accessed from multiple threads
#
# Holds refs in the form name: [gen-server, queue]
__gen_server_td = {}

# Task dict lock
task_lock = threading.Lock()

def __gen_server_lock():
    task_lock.acquire()
    
def __gen_server_release():
    task_lock.release()
    
def __gen_server_store_task_ref( name, ref ):
    __gen_server_lock()
    __gen_server_td[name] = ref
    __gen_server_release()

def __gen_server_get_task_ref( name ):
    __gen_server_lock()
    if name in  __gen_server_td:
        return __gen_server_td[name]
    else:
        return None
    __gen_server_release()

def __gen_server_get_all_ref():
    __gen_server_lock()
    refs = []
    for ref in  __gen_server_td:
        refs.append(ref)
    __gen_server_release()
    return refs
    
def __gen_server_rm_task_ref( name ):
    __gen_server_lock()
    if name in  __gen_server_td:
        del __gen_server_td[name]
    __gen_server_release()

# ====================================================================
# PUBLIC
# API

def gen_server_new( name, dispatcher ):
    
    # Assign a queue
    q = queue.Queue()
    # Create a new gen-server
    g_s = GenServer(name, dispatcher, q)
    # Add to the task registry
    __gen_server_store_task_ref(name, [g_s, dispatcher, q])
    # Start the gen-server loop
    g_s.start()
    
def gen_server_term( name ):
     item = __gen_server_get_task_ref(name)
     if item != None:
        ref, d, q = item
        ref.terminate()
        ref,join()
        
def gen_server_term_all( ):
    items = __gen_server_get_all_ref()
    for item in items:
        ref, d, q = item
        ref.terminate()
        ref,join()

def gen_server_msg( name, message ):
    item = __gen_server_get_task_ref(name)
    if item != None:
        msg = [name, message]
        gen_server, d, q = item
        q.put(msg)

def gen_server_msg_get(name):
    item = __gen_server_get_task_ref(name)
    if item != None:
        gen_server, d, q = item
        try:
            msg = q.get(block=True, timeout=0.1)
            return msg
        except queue.Empty:
            return None
        
def gen_server_response(name, resp_callback, response):
    item = __gen_server_get_task_ref(name)
    if item != None:
        msg = [name, resp_callback, response]
        gen_server, d, q = item
        q.put(msg)

def gen_server_response_get(name):
    item = __gen_server_get_task_ref(name)
    if item != None:
        gen_server, d, q = item
        try:
            msg = q.get(block=True, timeout=0.1)
            return msg
        except queue.Empty:
            return None

def gen_server_reg( name, task, dispatcher, q ):
    # Add to the task registry
    __gen_server_store_task_ref(name, [task, dispatcher, q])

def gen_server_reg_rm( name ):
    # Remove from task registry
    __gen_server_rm_task_ref( name )

# ====================================================================
# PRIVATE
# The gen-server task

class GenServer(threading.Thread):
    
    def __init__(self, name, dispatcher, q):
        super(GenServer, self).__init__()
        self.__name = name
        self.__dispatcher = dispatcher
        self.__q = q
        self.__term = False
        
    def term(self):
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
        # A message is of this form
        # [name, callable, [*, optional sender, option callable]]
        name, data = msg
        # Lookup the destination
        item = __gen_server_get_task_ref(name)
        if item == None:
            # Oops, no destination
            print("GenServer - destination %s not found!" % (name))
        else:
            # Dispatch
            gen_server, d, q = item
            d(data)
            
                
    
# ====================================================================
# PUBLIC
# Test code

def a_dispatch(msg):
    print("Message to A ", msg)

def b_dispatch(msg):
    print("Message to B ", msg)

def main():
    # Make 2 gen-servers
    gen_server_new("A", a_dispatch)
    gen_server_new("B", b_dispatch)
    # Send message to A and B
    gen_server_msg( "A", "Message to A" )
    gen_server_msg( "B", "Message to B" )
    # Terminate servers
    gen_server_term_all()
    
if __name__ == '__main__':
    main()