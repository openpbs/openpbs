'''
$Rev$

This hook is intended to set default resources to support the InfiniBand 
integration on IBM AIX.

Notes:
   - Standard indentation in this script is 3 spaces.
   - To enable debugging 
      - Verify resourcedef contains
      debug_hooks type=string_array
      - set server resources_available.debug_hooks+=<name for this hook>
   - To set default networks amount
      - Verify resourcedef contains
      PBS_ibm_ib_default_networks    type=long  flag=r
      PBS_ibm_ib_max_instances   type=long   flag=r

'''

import pbs
import re
import os
import sys

my_name = pbs.event().hook_name
myjob = pbs.event().job
if myjob == None:
   pbs.logmsg(pbs.LOG_WARNING, "Event Job parameter is not set")
   sys.exit()


### We only want to continue if they requested that we obtain the netwins 
### resource.
if ( 'PBS_GET_IBWINS' in myjob.Variable_List ):
   pbs.logmsg(pbs.LOG_WARNING, "User requested that netwins be calculated")
else:
   sys.exit()

### script Defaults area
### Reasonable internal defaults for networks, instances, and max instances
default_networks = 2
max_instances = 4
instances = 1
msg_api = ""
mpiprocs=1

# Put this closer to actual reference for efficiency.
mysrv = pbs.server()

debug_me = False

# If resources_available.debug_hooks contains the name of this hook, then we
# turn on the debug flag.
if ( "debug_hooks" in mysrv.resources_available and 
      my_name in str(
         mysrv.resources_available['debug_hooks']).split(',')
      ):
   debug_me=True

def dbg_svr_log(string):
   '''quick function to wrap debug logging to the server'''
   # Abort if the hook_debug value is not set
   if(debug_me):
      header = "DEBUG"
      footer = "".join(["%s" % "*" for s in range(80)])
      pbs.logmsg(pbs.LOG_ERROR, "%s\n%s\n%s" % ( header, string, footer ))

# If select is totally empty, set up reasonable defaults
if( myjob.Resource_List["select"] == None ):
   dbg_svr_log('myjob select is: %s' % myjob.Resource_List['select'])
   myjob.Resource_List["select"] = pbs.select(
      "1:ncpus=%d" % mysrv.default_chunk['ncpus'])

### obtain qmgr defaults/maximums
# Default value of networks.  This can be overridden by admin by changing
# value of PBS_ibm_ib_default_networks.
if ( 'PBS_ibm_ib_default_networks' in mysrv.resources_available and 
      mysrv.resources_available['PBS_ibm_ib_default_networks'] >= 0 ):
   default_networks = mysrv.resources_available['PBS_ibm_ib_default_networks']

# Maximum value of instances.  If not specified it will default to the value
# above in the defaults area.
if ( 'PBS_ibm_ib_max_instances' in mysrv.resources_available and 
   mysrv.resources_available['PBS_ibm_ib_max_instances'] != None):
   max_instances = mysrv.resources_available['PBS_ibm_ib_max_instances']

### Obtain user entered values
# Get the user entered value for MP_INSTANCES if it is defined in the variable
# list.
if ( 'MP_INSTANCES' in myjob.Variable_List ):
   instances = myjob.Variable_List['MP_INSTANCES']
   # We try to 'cast' the instances value as an int, which will throw ValueError
   # if it is a string.  The only valid string we allow for MP_INSTANCES is 
   # 'max'.  So if ValueError is thrown and MP_INSTANCES != 'max', reject
   # the submission.  We do the check this way because the instances value
   # always comes out of Variable_List as a string, even if it is really a 
   # number.  Because of this, a type check will always fail.
   try:
      instances = int(instances)
   except ValueError:
      if ( myjob.Variable_List['MP_INSTANCES'] != 'max' ):
         pbs.event().reject('Invalid value entered for MP_INSTANCES: %s' % 
            myjob.Variable_List['MP_INSTANCES'])

# If the person specified max, or an instances value that is too high, just set
# instances to max_instances
if ( instances == 'max' or instances > max_instances ):
   instances = max_instances

# There is no default for MP_MSG_API but we need to know the value
if ( 'MP_MSG_API' in myjob.Variable_List ):
   msg_api = myjob.Variable_List['MP_MSG_API']

### All inputs should be gathered at this point, begin parsing and setting up
### the values for netwins.
# Set up regex's for parsing the select statement
select=str(myjob.Resource_List["select"])

# The following regular expressions attempt to match the select syntax:
#    [ chunk | N:chunk ][+[chunk | N:chunk] ...]
#  where: 
#	N is a decimal digit,
#	chunk has syntax: resource=value[:resource=value ...]
#		with resource name starting with an alphabetic character
#		followed by a alphanumeric characters, _, or  -,
#		and value being a string with alphanumeric characters,
#               _, -, #, [, ], or . 
s_re = re.compile(r'\+?(?:(?P<qty>\d+))?:?(?P<res>(?:[a-zA-Z][\w_-]*?=[\w\.,\-_#\[\]]+:?)*)')
res_re=re.compile(r'([a-zA-Z][\w_-]*)=([\w\.,\-_#\[\]]+)')
new_chunksets=[]

# Parse out the elements of the select statment.
for chunkset in s_re.findall(select):

   # If both quantity and chunk resource are missing, we need to just skip
   # this iteration.  If one or the other are missing, fill them in with a 
   # reasonable default.  This should handle 'edge cases' like 
   # -l select=1
   # -l select=ncpus=1
   # It is not meant to handle a completely null select string, because that
   # won't even register in s_re.findall.

   if ( chunkset[0] == '' and chunkset[1] == '' ):
      continue
   elif ( chunkset[0] == '' ):
      qty = 1
      res_string = chunkset[1]
   elif ( chunkset[1] == '' ):
      qty = int(chunkset[0])
      if mysrv.default_chunk['ncpus'] != None:
         res_string = 'ncpus=%s' % mysrv.default_chunk['ncpus']
      else:
         res_string = 'ncpus=1'
   else:
      qty = int(chunkset[0])
      res_string = chunkset[1]

   # Loop through the pieces of the chunk to find mpiprocs
   for resource in res_re.findall(res_string):
      if ( resource[0] == 'mpiprocs' ):
         mpiprocs = resource[1]

   ### Perform our netwins calculation for this chunk(set).
   # Ibwins on a chunk = 
   # mpiprocs x (Num of networks x $INSTANCES)x(2 iff $MP_MSG_API = "mpi,lapi")
   ###
   dbg_svr_log("Calculating netwins based on:\n"+
      "mpiprocs: %s\ndefault_networks: %s\ninstances: %s\nmsg_api: %s" % ( 
         mpiprocs,default_networks,instances,msg_api
         )
      )
   netwins = int(mpiprocs) * int(default_networks) * int(instances) 
   # IFF MPI,LAPI is specified, double the netwins value
   if(msg_api.upper() == 'MPI\,LAPI'):
      netwins = netwins * 2 

   new_chunksets.append('%d:%s:netwins=%d' % ( qty, res_string, netwins ))

# Assemble the actual select string
new_select_string="+".join(new_chunksets)
dbg_svr_log('New select strings: %s' % new_select_string)
# Set select to be the new string
myjob.Resource_List['select'] = pbs.select(new_select_string)

# Do we want to output this information?
dbg_svr_log('The new select statement is going to be: %s' % 
   myjob.Resource_List['select'] )
