#!/usr/bin/env python
#
# gen_server_test.jl
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

module GenServerTest

# Modules
include("gen_server.jl")

# Using
using Match

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
            GenServer.gs_response(n, ["Message 1 response : MAIN -> GS1"])
          end
        "Message with response 1: GS2 -> MAIN" =>
          begin
            println("MAIN: Msg with resp 1 from GS2 ")
            GenServer.gs_response(n, ["Message 1 response : MAIN -> GS2"])
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
                GenServer.gs_msg("GS2", ["Message 1: GS1 -> GS2"])
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
            GenServer.gs_response(n, ["Message 1 response : GS1 -> MAIN"])
          end
        "Message with response 2: MAIN -> GS1" =>
          begin
            println("MAIN: Msg with resp 1 from MAIN ")
            GenServer.gs_response(n, ["Message 2 response : GS1 -> MAIN"])
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
              GenServer.gs_msg("GS1", ["Message 1: GS2 -> GS1"])
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
            GenServer.gs_response(n, ["Message 1 response : GS2 -> MAIN"])
          end
        "Message with response 2: MAIN -> GS2" =>
          begin
            println("GS2: Msg with resp 2 from MAIN ")
            GenServer.gs_response(n, ["Message 2 response : GS2 -> MAIN"])
          end
      end
  end
end

function test()
  # Make two servers
  gs1 = GenServer.gs_new("GS1", gs1_dispatch)
  gs2 = GenServer.gs_new("GS2", gs2_dispatch)

  # Register main thread
  ch = Channel(10)
  GenServer.gs_reg("MAIN", main_dispatch, ch)

  # Send a message to both servers from main thread
  GenServer.gs_msg("GS1", ["Message 1: MAIN -> GS1"])
  GenServer.gs_msg("GS2", ["Message 1: MAIN -> GS2"])
  GenServer.gs_msg("GS1", ["Message 2: MAIN -> GS1"])
  GenServer.gs_msg("GS2", ["Message 2: MAIN -> GS2"])

  # Send message to GS1 and GS2 from MAIN thread that requires a response
  GenServer.gs_msg("GS1", ["MAIN", "Message with response 1: MAIN -> GS1"])
  GenServer.gs_msg("GS2", ["MAIN", "Message with response 1: MAIN -> GS2"])

  # Retrieve messages and any responses for us
  for i in 1:10
    msg = GenServer.gs_msg_get("MAIN")
    while msg != nothing
      main_dispatch(msg)
      msg = GenServer.gs_msg_get("MAIN")
    end
    sleep(0.1)
  end

  # Term all servers
  GenServer.gs_term_all()

end # test

# ====================================================================
# Run tests
for i in 1:1
  test()
end
println("Test complete")

end # module
