"""
This hook will translate old mpp* language into the select/place language.
The hook reads in mpp* values from Resource_List.
If no mpp* values are set, then the hook exits without doing anything.
Otherwise, the mpp values are acted upon.
A combination of mpp* and -lselect is not allowed, and will cause
the hook to reject the job and give an error.
The select line to be output from the hook will be formed by:
1) Placing any -lvnode and/or -lhost requests at the beginning
   of the select this is so the job will be launched from the
   requested vnode/host
2) set nchunk=(mppwidth+(mppnppn-1))/mppnppn
3) set ncpus=mppdepth*mppnppn
4) set mpiprocs=mppnppn
5) set arch=mpparch
6) set PBScrayhost=mpphost
7) set mem=mppmem
8) set PBScraylabel_<label>=true where <label> is any mpplabels requested
9) set vntype=cray_compute
10) if mppnppn was requested set place=scatter 
Set node_set to the vnode names corresponding to the requested mppnodes.

More information can be found in the external design for SPID16543 
"""

import sys
import pbs

jobexists = -1

e = pbs.event()

if (e.type is pbs.QUEUEJOB):
	j = e.job
	jobexists = j.id

elif e.type is pbs.RESVSUB:
	j = e.resv
	jobexists = j.qmove

if j == None:
    e.reject("Event Job or Resv parameter is not set")


# Assign the Resource_List values to local variables
# These Resource_List values are built-in, so they are
# guaranteed to be defined.
mppwidth = j.Resource_List["mppwidth"]
mppdepth = j.Resource_List["mppdepth"]
mppnppn = j.Resource_List["mppnppn"]
mpparch = j.Resource_List["mpparch"]
mpphost = j.Resource_List["mpphost"]
mppnodes = j.Resource_List["mppnodes"]
mppmem = j.Resource_List["mppmem"]
mpplabels = j.Resource_List["mpplabels"]
reqvnode = j.Resource_List["vnode"]
reqhost = j.Resource_List["host"]

#If none of the mpp* values are set, then just exit.
if (((mppwidth is None) or (mppwidth == '')) and \
    ((mppdepth is None) or (mppdepth == '')) and \
    ((mppnppn is None) or (mppnppn == '')) and \
    ((mpparch is None) or (mpparch == '')) and \
    ((mpphost is None) or (mpphost == '')) and \
    ((mppmem is None) or (mppmem == '')) and \
    ((mpplabels is None) or (mpplabels == '')) and \
    ((mppnodes is None) or (mppnodes == ''))):
    pbs.event().accept()

# Do not allow both mpp* and -lselect or -lplace to be given
# If we got here, at least one mpp resource is set.
reqsel = j.Resource_List["select"]
reqplace = j.Resource_List["place"]

# If a Resource_List.select or a Resource_List.place is set 
# then check if this is an existing job.  If it is an existing job,
# then it's possible this hook has run before and created the 
# situation with mpp* and select/place are both set, so don't error out
# ignore the select line and re-translate the mpp* resources.
# If this is a new resv/job then reject any requests that have mpp*
# resources and select or place set.
if ((reqsel != None) or (reqplace != None)):
    if ((jobexists is None) or (jobexists == '')):
    	errstr="mpp resources cannot be used with \"select\" or \"place\""
    	pbs.event().reject("The following error was encountered: \n"+errstr)

# build the select line
select=""

# Set the vnode and/or the host first, if it was requested
# We need this request to be first in the select line
if ((reqvnode != None) or (reqhost != None)):
    select=select + "1:ncpus=1"

    if (reqvnode != None):
        select=select + ":vnode=%s" %reqvnode
        j.Resource_List["vnode"]=None

    if (reqhost != None):
        select=select + ":host=%s" %reqhost
        j.Resource_List["host"]=None
    select = select + "+"

# If the values of mppnppn and mppdepth are not already set,
# then set them equal to 1 so we can do math with them later
hooksetnppn=0
hooksetdepth=0
if ((mppnppn is None) or (mppnppn == '')):
    mppnppn = 1
    hooksetnppn = 1

if ((mppdepth is None) or (mppdepth == '')):
    mppdepth = 1
    hooksetdepth = 1

if ((mppwidth != None) and (mppwidth != '')):
    nchunk=str((int(mppwidth)+(int(mppnppn)-1))/int(mppnppn))
    select=select + "%s:" %nchunk
    
# If the hook didn't set nppn or depth, then 
# use what the user input to determine the number of ncpus
# If the hook did set nppn or depth to a default value of 1,
# then don't calculate ncpus, because maybe the admin has
# a default value of ncpus for the queue or server and we want the job
# to be able to use the defaults.
# In other words, we only set resource values like ncpus or mpiprocs
# if the user provided corresponding mpp* values.
if ((hooksetnppn == 0) or (hooksetdepth == 0)):
    ncpus=int(mppdepth)*int(mppnppn)
    select=select + "ncpus=%s:" %(str(ncpus))

# Only set mpiprocs when the user gave us a corresponding mppnppn value.
# Otherwise don't set mpiprocs.  

if ((hooksetnppn == 0) and (mppnppn >= 1)):
    select=select + "mpiprocs=%d:" %mppnppn

# Pass along the arch value if it is set
if (mpparch != None) and (mpparch != ''):
    select=select + "arch=%s:" %mpparch

if (mpphost != None):
    select=select + "PBScrayhost=%s:" %mpphost

if (mppmem != None):
    select=select + "mem=%s:" %mppmem

# Set any mpplabels
if (mpplabels != None):
    labellist = mpplabels.split(',')
    for label in labellist:
        newlabel="PBScraylabel_" + label
        select=select + "%s=True:" %newlabel 

# The user requested mpp* resources, which means they want to use Cray 
# compute nodes. So we set vntype=cray_compute automatically in the hook.
select=select + "vntype=cray_compute"

j.Resource_List["select"]=pbs.select(select)

# Set place=scatter if mppnppn was requested
if (hooksetnppn == 0):
  j.Resource_List["place"]=pbs.place("scatter")

# If mppnodes is given:
#         Expand the nodelist keeping the given order of nodes.
#         Find the matching vnode name.
#         Build a list of matching vnode names.
def pbs_expandrange(seq):
    # Deal with the ranges first
    range = list(seq.partition('-'))

    lower = int(range[0])
    upper = int(range[2])

    if (upper <= lower ):
        pbs.logmsg(pbs.LOG_ERROR, "translate mpp: ERROR: bad range '%s', " \
                  "the first number (%d) must be less than the " \
                  "second number (%d)" %(seq, lower, upper))
        errstr="Bad range '%s', the first number (%d) must be less than " \
               "second number (%d)" %(seq, lower, upper)
        pbs.event().reject("The following error was encountered: \n"+errstr)
    expandedlist=list()
    while (lower <= upper):
        expandedlist.append(str(lower))
        lower=lower+1

    return expandedlist 

if (mppnodes != None):
    pbs.logmsg(pbs.LOG_DEBUG, "translate mpp:  requested mppnodes are " \
              "= '%s'" %mppnodes)
    nodelist = []
    firstpass = mppnodes.split(',')
    #search the list for '-'
    for item in firstpass:
        if(item.find("-") != -1):
            rangelist = pbs_expandrange(item)
            nodelist = nodelist + rangelist
        else:
            nodelist.append(item)

    # From the nodelist, create a comma separated list of vnode names
    # Set node_set to the list of vnode names, to pass to the scheduler
    # walk the list of given mppnodes looking for a matching vnode 
    # An mppnode num may be found more than once in vnode list,
    # so we have to keep walking the vnode list even after finding a match.
    # We need to keep the same order for the found vnode names as the
    # given order of the mppnodes.  Cray cares about the ordering.
    vnl = []                        #Entire list of vnodes
    nsl = []                        #List of vnodes that match mppnodes
    nomatch = []

    #Save the equivalent of pbsnodes -av to vnl
    #This uses less memory than getting the list each time
    vni = pbs.server().vnodes()
    for vn in vni:
        vnl.append(vn)

    for num in nodelist:
        matched = 0
        for vnode in vnl:
            if ((hasattr(vnode.resources_available, "PBScraynid")) and \
                (num == vnode.resources_available["PBScraynid"])):
                if (mpphost != None):
                    if ((hasattr(vnode.resources_available, "PBScrayhost")) and \
                        (mpphost == vnode.resources_available["PBScrayhost"])):
                            # the mpphost and the vnode's PBScrayhost match
                            matched = 1
                            nsl.append(vnode.name)
                else:
                    # the user did not specify a mpphost, we match
                    # so just add the vnode name to the node set list
                    matched = 1
                    nsl.append(vnode.name)
            # num doesn't match this vnode, check the next vnode in the list
        # We have gone through all of the vnodes on the system
        # if we didn't find a match for this mppnode, add it to the
        # list of mppnodes not matched
        if (matched == 0):
            nomatch.append(num)
    
    t=","
    j.node_set=t.join(nsl)

    # The hook should reject the job if no matches could be found for the 
    # given mppnodes (i.e. the node_set list is empty).
    if (j.node_set == ''):
        pbs.logmsg(pbs.LOG_ERROR, "translate mpp: ERROR: could not find matching vnodes for the given mppnodes %s" %(mppnodes))
        errstr="No matching vnodes for the given mppnodes %s" %(mppnodes)
        pbs.event().reject("The following error was encountered: \n"+errstr)

    # Some, but not all mppnodes could be matched to vnodes.  Print the list
    # of unmatched mppnodes to the server log.  And then continue on with 
    # j.node_set set to the vnode names that matched the requested mppnode.  
    # Print j.node_set to the server log too.  This way there will be a record
    # of what did and didn't match.
    if (len(nomatch) > 0):
        pbs.logmsg(pbs.LOG_DEBUG, "translate mpp: could not find matching " \
                  "vnodes for these given mppnodes %s" %(nomatch))

    # This is the node_set list being passed to the scheduler
    pbs.logmsg(pbs.LOG_DEBUG, "translate mpp:  vnode name list= '%s'" %j.node_set)

