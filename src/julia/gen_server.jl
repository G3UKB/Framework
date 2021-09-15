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
# External API
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

# =================================
# The Task container
mutable struct CGenServer
  # Fields
  # Locks are required for any data with multiple thread readers/writers
  lk::ReentrantLock
  ch::Channel
  dispatcher

  # Inner constructor
  CGenServer() = new(ReentrantLock(), Channel(10))
end
# =================================

# =================================
# Member functions
function gs_acquire(x::CGenServer)
  lock(x.lk)
end

function gs_release(x::CGenServer)
    unlock(x.lk)
end

function gs_store_desc(x::CGenServer, name, desc)
  gs_acquire(x)
  gs_d[name] = desc
  gs_release(x)
end

function gs_rm_desc(x::CGenServer, name)
    gs_acquire(x)
    delete!(gs_d, name)
    gs_release(x)
end

function gs_get_desc(x::CGenServer, name)
    gs_acquire(x)
    if haskey(gs_d, name)
        desc = gs_d[name]
    else
        desc = nothing
    end
    gs_release(x)
    return desc
end

function gs_get_all_desc(x::CGenServer)
    gs_acquire(x)
    descs = collect(values(gs_d))
    gs_release(x)
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
  gs_store_desc(server, name, [server.dispatcher, server.ch])
  # and schedule...
  schedule(task)
  # Initialise server
  put!(server.ch, "INIT")
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
    if msg == "QUIT"
      break
    end
  end
  println("Gen Server terminating...")
end

# ====================================================================
# TEST
function dispatch()
  println("Dispatcher")
end

function test()
  # Make a new server
  server = gs_new("T1", dispatch)
  # Get its descriptor
  d = gs_get_desc(server, "T1")
  # Send quit
  put!(d[2], "QUIT")
end

test()
readline()
println("Test complete")

# end Module
end
