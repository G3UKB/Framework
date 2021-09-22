#
# gen_server.jl
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

#=
    This module is loosly based on the erlang gen-server in that it emulates a
    process oriented message passing concurrency model.
    Depending on the instantiation of the servers cooperative and parallel servers
    can be mixed.

    PUBLIC INTERFACE:

        Create a new gen-server with the task name 'name'. As everything is performed using the task name you should
        never need to keep the reference. The dispatcher is a callable that will process the messages. One special message is
        "INIT" which is sent once the gen-server is running. This is to allow any initialisation processing to be done. It also
        passes additional parameters to the server as it is only started with the channel reference (limitation of Task). The
        type is the task type COOP (cooperative) or PAR (parallel).

            gen_server_new( name, dispatcher, type )

        Ask the gen-server with task name 'name' or all servers to terminate. Termination must be performed this way as the
        server is blocked waiting for a message.

            gen_server_term( name )
            gen_server_term_all()

        Send a message to the gen-server with task name 'name', calling dispatcher with the opaque data *. The opaque data can be
        any as it is passed directly to the dispatcher. However, if a response is required the convention is [sender, *] where *
        is the opaque data and the sender is the task name to send the response to.

            gen_server_msg( name, [*] | [sender, *] )

        Retrieve message for tasks that are not gen-servers. Returns the full content. Such tasks could be the main thread or threads that
        want to communicate in other ways but also use the message infrastructure (see registration). As these tasks are not gen-servers no
        message loop is executing so messages are not automatically dispatched. Calling gen_server_msg_get() on a periodic basis will cause
        any queued messages (or responses which are just messages with a response type) to be dispatched to the calling task. In the case
        of responses there would never be a sender as reponding to a response makes no sense.

            [*] | [sender, *] = gen_server_msg_get()

        When the dispatcher receives a message from gen_server_msg() by whatever route it must be aware of the structure of the opaque data
        and if a response is required the array must include the sender name. In order to respond it should call gen_server_response()
        with the sender name 'name', and * the opaque response data.

            gen_server_response(name, *)

        If a task which is not a gen-server wishes to participate in the messaging framework it must be registered in the task registry
        with 'task' the task reference and 'name' the task name. The dispatcher is the callable to dispatch messages to and it must also
        create its own channel and pass the reference.

            gen_server_reg( name, task, dispatcher, channel )

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
            messages and responses are dispatched automatically. Note that both sending and receiving are dispatched via the channel
            so always arrive on the thread of the receiving task, not of the sending task.

        2. Sender : gen-server, receiver : normal user task.
            In this case the normal user task must be registered using gen_server_reg() so its task object can be retrieved by task name.
            Sending is the same as before using gen_server_msg(). However, the receiver will not get that message automatically because
            there is no gen-server to take it from the channel.

        3. Sender : normal user task, receiver gen-server.
            This is similar to [2]. The sender uses gen_server_msg() The receiver will automatically get the message. If a response is
            required then sender must call gen_server_msg_get() as it will not automatically get the response.

        4.  Sender : gen-server, receiver : MAIN-TASK
            This is similar to [2] above except the main task is the recipient. The message is dispatched as normal to the task channel and
            must be retrieved manually.

        5. Sender : MAIN-TASK, receiver : gen-server.
            Again similar to [2] above. The task uses gen_server_msg() to send and if it wants to receive a reply it can use
            gen_server_msg_get() to pick up the reply.

=#

module GenServer

import Base.Threads.@spawn

# External visible functions
export THRD_T, COOP, PAR, gs_new, gs_term, gs_term_all, gs_msg, gs_msg_get, gs_response, gs_response_get, gs_reg, gs_unreg

# Thread type
@enum THRD_T COOP = 0 PAR = 1

# ====================================================================
# PRIVATE
# Global to this module
#
# Task dictionary
# This will be accessed from multiple threads
#
# Holds refs in the form {name: [dispatcher, queue]}
gs_d = Dict{String, Array}()
# Lock for gs_d
lk = ReentrantLock()

# =================================
# The Task container
mutable struct CGenServer
  # Fields
  # Channel to be used by this instance of gen-server
  ch::Channel
  # Function to dispatch messages to by this instance of gen-server
  dispatcher

  # Inner constructor
  CGenServer() = new(Channel(10))
end
# =================================

# =================================
# Member functions
function gs_acquire()
  lock(lk)
end

function gs_release()
  unlock(lk)
end

function gs_store_desc(name, desc)
  gs_acquire()
  gs_d[name] = desc
  gs_release()
end

function gs_rm_desc(name)
  gs_acquire()
  delete!(gs_d, name)
  gs_release()
end

function gs_get_desc(name)
  gs_acquire()
  if haskey(gs_d, name)
      desc = gs_d[name]
  else
      desc = nothing
  end
  gs_release()
  return desc
end

function gs_get_all_desc()
  gs_acquire()
  descs = collect(values(gs_d))
  gs_release()
  return descs
end

# ====================================================================
# PUBLIC
# API

function gs_new(name, dispatcher, thrd_type)
  # Create a new server instance
  server = CGenServer()
  # Set the dispatcher
  server.dispatcher = dispatcher

  # Create a task to run the server and bind to a channel
  # We can choose what kind of threads e want or mix them at
  # This runs cooperative threads
  if thrd_type == 0
    begin
      task = Task(() -> gen_server(server.ch))
      schedule(task)
    end
  else
    begin
      # This runs OS threads, one per
      task = @spawn gen_server(server.ch)
    end
  end

  # Store server descriptor
  gs_store_desc(name, [server.dispatcher, server.ch])
  # Initialise server
  put!(server.ch, ["INIT", [name, dispatcher]])
  return server
end

function gs_term(name)

  d = gs_get_desc(name)
  if d != nothing
    _, ch = d
    put!(ch, ["QUIT", []])
  end
end

function gs_term_all()
    ds = gs_get_all_desc()
    for d in ds
      _, ch = d
      put!(ch, ["QUIT", []])
    end
end

function gs_msg(name, msg)
  d = gs_get_desc(name)
  if d != nothing
    _, ch = d
    put!(ch, ["MSG", msg])
  end
end

function gs_response(name, response)
  d = gs_get_desc(name)
  if d != nothing
    _, ch = d
    put!(ch, ["RESP", response])
  end
end

function gs_msg_get(name)
  d = gs_get_desc(name)
  msg = nothing
  if d != nothing
    _, ch = d
    if isready(ch)
      msg = take!(ch)
    end
  end
  return msg
end

function gs_reg(name, dispatcher, ch)
  gs_store_desc(name, [dispatcher, ch])
end

function gs_unreg(name)
  gs_rm_desc(name)
end

  # ====================================================================
  # PRIVATE
  # The gen-server task

function gen_server(ch)
  name = nothing
  dispatcher = nothing
  while true
    msg = take!(ch)
    cmd, args = msg
    if cmd == "INIT"
      # Might want to do something different here
      name, dispatcher = args
      println(name, " Gen Server running")
      dispatcher(msg)
    elseif cmd == "MSG" || cmd == "RESP"
      # Message for dispatcher
      dispatcher(msg)
    elseif cmd == "QUIT"
      break
    else
      println("Unknown message ", msg)
    end
  end
  println(name, " Gen Server terminating...")
end

end # Module
