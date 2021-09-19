#!/usr/bin/env python
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
