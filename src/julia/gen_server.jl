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

function gs_store_ref(name, desc)
  gs_acquire()
  gs_d[name] = desc
  gs_release()
end

function gs_get_ref( name )
    gs_acquire()
    if haskey(gs_d, name)
        r = gs_d[name]
    else
        r = nothing
    end
    gs_release()
    return r
end

gs_store_ref("A", [1,2,3])
print(gs_get_ref("A"))
