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

# Using
using Match

# External visible functions
export gs_new

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

function gs_new(name, dispatcher)

  # Create a new server instance
  server = CGenServer()
  # Set the dispatcher
  server.dispatcher = dispatcher
  # Create a task to run the server and bind to a channel
  task = Task(() -> gen_server(server.ch))
  # Store server descriptor
  gs_store_desc(name, [server.dispatcher, server.ch])
  # and schedule...
  schedule(task)
  # Initialise server
  put!(server.ch, ["INIT", [name, dispatcher]])
  return server
end

  # ====================================================================
  # PRIVATE
  # The gen-server task

function gen_server(ch)

  println("Gen Server starting...")
  while true
    msg = take!(ch)
    println(msg)
    cmd, args = msg
    if cmd == "INIT"
      name, dispatcher = args
      dispatcher(msg)
    end
    if cmd == "QUIT"
      break
    end
  end
  println("Gen Server terminating...")
end

# ====================================================================
# TEST
function dispatch(msg)
  println("Dispatcher ", msg)
end

function test()
  # Make a new server
  server = gs_new("T1", dispatch)
  # Get its descriptor
  d = gs_get_desc("T1")
  _, ch = d
  # Send quit
  put!(ch, ["QUIT", []])
end

test()
readline()
println("Test complete")

# end Module
end
