#
# pub_sub.jl
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

#=
The publish/subscribe system is a layer on top of gen_server. It's a very thin layer
    but provides a level of abstraction so senders and receivers are decoupled.

    Pub/sub should be used primarily for send and forget operatiosn that happen multiple
    times or are sent to a number of variable receivers. There can be 0-n receivers for
    a message. Senders are not aware during a send how many receivers there are and will not receive
    any notifications even if there are no receivers currently. If a message is sent once
    only and is important then, especially during startup do a direct send or ensure proper
    sequencing of tasks. A sender can get a subscriber list if required such that they can
    delay startup until the required tasks are running.

    The public interface can be called from any task (thread).
    Subscribers subscribe to a topic and provide a task name.
    Publishers publish to a topic with data to send via a gen_server_msg().

    PUBLIC INTERFACE:

    Subscribe to a topic where 'name' is the task name of the target task and 'topic' is the topic
    to subscribe to. Topic names and task names are strings. If a topic does not exist it will be created.

        ps_subscribe( name, topic )

    Unsubscribe name from topic.

        ps_unsubscribe( name, topic )

    Publish to a topic where * is the opaque data to send and s'topic' is the topic name.
    If a topic does not exist a message will be logged but it won't fail.
    Subscribers should therefore subscribe before publishing starts. Note that this
    is asynchronous as publish will return once messages have been sent to all subscribers.

        ps_publish( topic, * )

    Get a subscriber list for topic 'topic'.

        subscribers = ps_list( topic )

=#

module PubSub

# Modules
using GenServer

# External visible functions
export ps_subscribe, ps_unsubscribe, ps_publish, ps_list


# ====================================================================
# PRIVATE
# Global to this module
#
# Subscriber dictionary
# This will be accessed from multiple threads
#
# Holds refs in the form topic: task-name
ps_d = Dict{String, Array}()
# Lock for ps_d
lk = ReentrantLock()

function ps_acquire()
  lock(lk)
end

function ps_release()
  unlock(lk)
end

# ====================================================================
# PUBLIC
# API
function ps_subscribe(name, topic)
  ps_acquire()
  if haskey(ps_d, topic)
    append!(ps_d[topic], [name])
  else
    ps_d[topic] = [name]
  end
  ps_release()
end

function ps_unsubscribe(name, topic)
  ps_acquire()
  if haskey(ps_d, topic)
    if name in ps_d[topic]
      ps_d[topic] = setdiff(ps_d[topic], name)
    end
  end
  ps_release()
end

function ps_publish(topic, data)
  ps_acquire()
  if haskey(ps_d, topic)
    subscribers = ps_d[topic]
    for subscriber in subscribers
      desc = GenServer.gs_get_desc(subscriber)
      if desc != nothing
        GenServer.gs_msg(subscriber, data)
      end
    end
  end
  ps_release()
end

function ps_list(topic)
  ps_acquire()
  copyof = []
    if haskey(ps_d, topic)
      copyof = deepcopy(ps_d[topic])
    end
  ps_release()
  return copyof
end

end # module
