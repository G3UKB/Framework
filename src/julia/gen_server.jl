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
export gs_new, gs_term, gs_term_all, gs_msg, gs_msg_get, gs_response, gs_response_get, gs_reg, gs_unreg

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

# ====================================================================
# ====================================================================
# TEST
function main_dispatch(msg)
  @match msg begin
    # Message without response or response
    [c, [m]] =>
      @match c begin
        "MSG" =>
          # Message type
          @match m begin
            "Message 1: GS1 -> MAIN" => println("MAIN: Msg 1 from GS1 ")
            "Message 1: GS2 -> MAIN" => println("MAIN: Msg 1 from GS2 ")
          end
        "RESP" =>
          # Response type
          @match m begin
            "Message 1 response : GS1 -> MAIN" => println("MAIN: Resp 1 from GS1 ")
            "Message 1 response : GS2 -> MAIN" => println("MAIN: Resp 1 from GS2 ")
          end
      end
    # Message requires response
    [c, [n, m]] =>
      # Message type
      @match m begin
        "Message with response 1: GS1 -> MAIN" =>
          begin
            println("MAIN: Msg with resp 1 from GS1 ")
            gs_response(n, ["Message 1 response : MAIN -> GS1"])
          end
        "Message with response 1: GS2 -> MAIN" =>
          begin
            println("MAIN: Msg with resp 1 from GS2 ")
            gs_response(n, ["Message 1 response : MAIN -> GS2"])
          end
      end
  end
end

function gs1_dispatch(msg)
  @match msg begin
    # Message without response or response
    [c, [m]] =>
      @match c begin
        "MSG" =>
          # Message type
          @match m begin
            "Message 1: MAIN -> GS1" =>
              begin
                println("GS1: Msg 1 from MAIN ")
                # Send a message to GS2
                gs_msg("GS2", ["Message 1: GS1 -> GS2"])
              end
            "Message 2: MAIN -> GS1" => println("GS1: Msg 2 from MAIN ")
            "Message 1: GS2 -> GS1" => println("GS1: Msg 1 from GS2")
          end
        "RESP" =>
          # Response type
          @match m begin
            "Response 1: MAIN -> GS1" => println("GS1: Resp 1 from MAIN ")
            "Response 2: MAIN -> GS1" => println("GS1: Resp 1 from MAIN ")
          end
      end
    # Message requires response
    [c, [n, m]] =>
      # Message type
      @match m begin
        "Message with response 1: MAIN -> GS1" =>
          begin
            println("GS1: Msg with resp 1 from MAIN ")
            gs_response(n, ["Message 1 response : GS1 -> MAIN"])
          end
        "Message with response 2: MAIN -> GS1" =>
          begin
            println("MAIN: Msg with resp 1 from MAIN ")
            gs_response(n, ["Message 2 response : GS1 -> MAIN"])
          end
      end
  end
end

function gs2_dispatch(msg)
  @match msg begin
    # Message without response or response
    [c, [m]] =>
      @match c begin
        "MSG" =>
          # Message type
          @match m begin
            "Message 1: MAIN -> GS2" =>
            begin
              println("GS2: Msg 1 from MAIN ")
              # Send a message to GS1
              gs_msg("GS1", ["Message 1: GS2 -> GS1"])
            end
            "Message 2: MAIN -> GS2" => println("GS2: Msg 2 from MAIN")
            "Message 1: GS1 -> GS2" => println("GS2: Msg 1 from GS1")
          end
        "RESP" =>
          # Response type
          @match m begin
            "Response 1: MAIN -> GS2" => println("GS2: Resp 1 from MAIN")
            "Response 2: MAIN -> GS2" => println("GS2: Resp 1 from MAIN")
          end
      end
    # Message requires response
    [c, [n, m]] =>
      # Message type
      @match m begin
        "Message with response 1: MAIN -> GS2" =>
          begin
            println("GS2: Msg with resp 1 from MAIN ")
            gs_response(n, ["Message 1 response : GS2 -> MAIN"])
          end
        "Message with response 2: MAIN -> GS2" =>
          begin
            println("GS2: Msg with resp 2 from MAIN ")
            gs_response(n, ["Message 2 response : GS2 -> MAIN"])
          end
      end
  end
end

function test()
  # Make two servers
  gs1 = gs_new("GS1", gs1_dispatch)
  gs2 = gs_new("GS2", gs2_dispatch)

  # Register main thread
  ch = Channel(10)
  gs_reg("MAIN", main_dispatch, ch)

  # Send a message to both servers from main thread
  gs_msg("GS1", ["Message 1: MAIN -> GS1"])
  gs_msg("GS2", ["Message 1: MAIN -> GS2"])
  gs_msg("GS1", ["Message 2: MAIN -> GS1"])
  gs_msg("GS2", ["Message 2: MAIN -> GS2"])

  # Send message to GS1 and GS2 from MAIN thread that requires a response
  gs_msg("GS1", ["MAIN", "Message with response 1: MAIN -> GS1"])
  gs_msg("GS2", ["MAIN", "Message with response 1: MAIN -> GS2"])

  # Retrieve messages and any responses for us
  for i in 1:10
    msg = gs_msg_get("MAIN")
    while msg != nothing
      main_dispatch(msg)
      msg = gs_msg_get("MAIN")
    end
    sleep(0.1)
  end

  # Term all servers
  gs_term_all()

end # test

# ====================================================================
# Run tests
for i in 1:10
  test()
end
println("Test complete")

end # Module
