# A gen-server try

# ====================================================================
# PRIVATE
# Task dictionary
# This will be accessed from multiple threads
#
# Holds refs in the form {name: [gen-server, dispatcher, queue]}
gs_d = Dict{String, Array}()

# Locks are required for any data with multiple thread readers/writers
lk = ReentrantLock()
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

function gs_rm_desc( name )
    gs_acquire()
    delete!(gs_d, name)
    gs_release()
end

function gs_get_desc( name )
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

function gs_new( name )

  # Assign a channel for messages
  ch = Channel{T=Any}(size=10)
  # Create a new gen server
  # No way to pass arguments to a task!!! What!!!
  # At this point give up for now
  t = Task(gen_server)


# ====================================================================
# TEST
gs_store_desc("A", [1,2,3])
println(gs_get_desc("A"))
println(gs_get_all_desc())
gs_rm_desc( "A" )
println(gs_get_all_desc())
