# Copyright (C) 1994-2021 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of both the OpenPBS software ("OpenPBS")
# and the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# OpenPBS is free software. You can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# OpenPBS is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# PBS Pro is commercially licensed software that shares a common core with
# the OpenPBS software.  For a copy of the commercial license terms and
# conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
# Altair Legal Department.
#
# Altair's dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of OpenPBS and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair's trademarks, including but not limited to "PBS™",
# "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
# subject to Altair's trademark licensing policies.
#
#	Usage:
#
#		awk -f ThisScript [ -v type=m ] [ inputfile ]
#		awk -f ThisScript [ -v type=q ] [ inputfile ]
#
#	If no input file is given, the value of topology_file (below) is used.
#
#	This script is designed to consume the Altix ProPack 4+ system topology
#	file and emit placement set information in one of two forms, one for
#	consumption by pbs_mom and the other in qmgr form.  The form of output
#	is controlled by the command-line variable "type", whose value should
#	be either 'm' (for the pbs_mom form) or 'q' (for the qmgr form).
#
#	For the pbs_mom form, we first emit a prologue describing the types of
#	placement sets and any global options.  This prologue uses the special
#	vnode ID of NODE and the special attribute name "pnames":
#
#		NODE:	pnames = TYPE1 [, TYPE2 ...]
#
#	then a list of the various placement sets by node
#
#		NODE[N]:	NAME = ps1 [ , ps2 ... ]
#
#	where NODE is derived from the host's FQDN by dropping the domain
#	qualifier(s), N is a node number, NAME is the name of a resource
#	(e.g. "cbrick" or "router"), and ps1, ... is a list of placement
#	set names.
#
#	This script currently computes only one type of placement set
#	("router").  It does this by associating with each router that
#	is directly connected to a node the list of node IDs.  Then, for
#	each router that is two hops removed from a node, we associate
#	the union of the lists of nodes of each directly-connected router.
#	The expanding ring computation goes on until we either run out of
#	routers or have failed to make progress.
#
#	The qmgr form of output is a series of lines like this:
#
#		set NAME[N] resources_available.TYPE = "ps1 [ , ps2 ... ]"
#
#	where NAME is the host's name, N is a node number, TYPE is the name
#	of the resource type (e.g. "cbrick" or "router", as above), and ps1,
#	... is a list of placement set names.
#
#	Additionally the script emits generic vnode information (vnode ID,
#	number of CPUs, amount of memory) for consumption by pbs_mom in this
#	form
#
#		NODE[ID]:	cpus = <CPUlist>
#		NODE[ID]:	resources_available.ncpus = X
#		NODE[ID]:	resources_available.mem = Y
#
#	where NODE is derived from the host's FQDN by dropping the domain
#	qualifier(s), ID is a vnode ID, X is the number of CPUs belonging
#	to the vnode with this ID, and Y is the amount of memory (in KB).
#	<CPUlist> is a list of CPUs in the given NODE[ID].
#
#	Note:  the list of vnodes is culled to ensure that it excludes CPUs
#	that belong to CPU sets not claimed by PBS.

BEGIN {
	# Sort cpus, mems, and vnodes numerically
	PROCINFO["sorted_in"] = "@ind_num_asc";

	deftype = "m";			#	by default, output for pbs_mom
	exitval = 0;			#	used to elide END actions
	listsep = ", "
	ncpus = 0;
	nnodes = 0;
	npnames = 0;
	nnumalinks = 0;
	nrouters = 0;

	ptype = "router";		#	placement set type
	pshort = "R";			#	shorthand used in resource value
					#	(later modified by prepending
					#	nodename to uniquify values

	#	command to find "cpus" and "mems" files that do not belong to
	#	PBS (CPU sets that are not the root, and not under /PBSPro)
	#	in the "cpuset" file system
	findcmd = "find /dev/cpuset -name cpus -o -name cpuset.cpus \
		-o -name mems -o -name cpuset.mems | \
		egrep -v -e '/dev/cpuset/cpus$' -e '/dev/cpuset/cpuset.cpus$' \
		-e '/dev/cpuset/mems$' -e '/dev/cpuset/cpuset.mems$' \
		-e '/PBSPro/'";

	topology_version_min = 1;	#	the versions we understand
	topology_version_max = 2;	#	the versions we understand
	UVtopology_version_min = 1;	#	the versions we understand
	UVtopology_version_max = 1;	#	the versions we understand
	topology_file = "/proc/sgi_sn/sn_topology"
	UVtopology_file = "/proc/sgi_uv/topology"

	#	override standard input default if no input file is given
	if (ARGC == 1) {
		if ((getline < topology_file) > 0) {
			ARGV[ARGC++] = topology_file;
			close(topology_file);
		} else if ((getline < UVtopology_file) > 0) {
			ARGV[ARGC++] = UVtopology_file;
			close(UVtopology_file);
		}
		if (ARGC == 1) {
			printf("no input files given, no known topology files found\n");
			exitval = 1;
			exit(1);
		}
	}

	"uname -n | sed -e 's/\\..*//'" | getline nodename
	close("uname -n | sed -e 's/\\..*//'");
	pshort = nodename "-" pshort;	#	shorthand is now "H-RN" where
					#	H is the unFQDNed host name and
					#	N is a nonnegative integer

	#	make two lists, excludedCPUs[] and excludedmems[],
	#	of all CPUs and memory boards found in CPU sets
	#	that do not belong to PBS
	while ((findcmd | getline cpumemfile) > 0)
		read_excludelist(cpumemfile);
	close(findcmd);

	if (type == "")
		type = deftype;
	else if ((type != "m") && (type != "q")) {
		printf("type should be one of 'm' or 'q'\n");
		exitval = 1;
		exit(1);
	}
}

#	check for supported version(s)
$2 == "sn_topology" && $3 == "version" {
	is_UV = 0
	topology_version = $4;
	verscheck($4, topology_version_min, topology_version_max)
	if (debug)
		printf("SN topology file (version %d)\n", topology_version);
}

#	check for supported version(s) for UV
$2 == "uv_topology" && $3 == "version" {
	is_UV = 1
	topology_version = $4;
	verscheck($4, UVtopology_version_min, UVtopology_version_max)
	if (debug)
		printf("UV topology file (version %d)\n", topology_version);
}

#	cpu 0 001c05#0a local freq 1500MHz, arch ia64, dist 10:10:45:...
#	cpu 000 r001i01b00#00_00-000 local freq 2666MHz, arch UV , dist 10:10:10:...
/^cpu[[:space:]]+[[:digit:]]+/ {
	cpuid[int($2)] = $3;
	if (debug)
		printf("cpu[%d]:  id %s\n", ncpus, $3);

	if (is_UV == 0) {
		#	Even though the sn_topology version stays the same, the
		#	distance vector may appear in multiple places within the
		#	line.
		if ($9 == "dist") {
			split($10, tmp, ":");
			do_cpudist = 1;
		} else if ($13 == "dist") {
			split($14, tmp, ":");
			do_cpudist = 1;
		} else
			do_cpudist = 0;
	} else {
		if ($10 == "dist") {
			split($11, tmp, ":");
			do_cpudist = 1;
		} else
			do_cpudist = 0;
	}

	if (do_cpudist)
		for (tmpindex in tmp)
			cpudist[int($2), tmpindex - 1] = tmp[tmpindex];
	ncpus++;
}

#	node 0 001c05#0 local asic SHub_1.2, nasid 0x0, dist 10:45:...
/^node[[:space:]]+[[:digit:]]+/ {
	nodeid[$2] = $3;
	nodenums[$3] = $2;
	if (debug)
		printf("node[%d]:  id %s\n", nnodes, $3);

	#	Even though the sn_topology version stays the same, the
	#	distance vector may appear in multiple places within the
	#	line.
	if ($9 == "dist") {
		split($10, tmp, ":");
		do_nodedist = 1;
	} else if ($13 == "dist") {
		split($14, tmp, ":");
		do_nodedist = 1;
	} else
		do_nodedist = 0;

	if (do_nodedist)
		for (tmpindex in tmp) {
			#	Does the distance list terminate the line, or
			#	is it followed by ", near_mem_nodeid ..."?  In
			#	the latter case, remove any possible trailing
			#	',' from the distance number.
			if (topology_version == 2)
				sub(",$", "", tmp[tmpindex]);
			nodedist[$2, tmpindex - 1] = tmp[tmpindex];
		}
	nnodes++;
}

#	Info from SGI:
#	A "local" NUMAlink connection connects to another device that resides
#	in the same partition as the source.
#	A "foreign" NUMAlink connection terminates to another device that is
#	in a non-local partition.
#	A "shared" connection terminates on a device that is shared between
#	several partitions (always routers presently.)
#
#	numalink 1 001c05#0-1 local endpoint 001c05#5-1, protocol LLP4
#			^			    ^
#			|			    |
#			-- stored in		    -- stored in
#			   numalinkremoteid[]  	       numalinklocalid[]
#
/^numalink[[:space:]]+[[:digit:]]+/ {
	if ($6 == "disconnected,")
		next;
	if (($4 == "foreign") || ($4 == "local") || ($4 == "shared")) {
		sub(",$", "", $6);
		numalinklocalid[$2] = $3;
		numalinkremoteid[$2] = $6;
		ridtmp = NUMAlink2router($3);

		#	nrouterconnections[] is an array (indexed by router ID,
		#	ridtmp) that records the number of routers connected to
		#	the router with ID ridtmp.  routerconnections[] holds
		#	the names of those routers.
		if (!(ridtmp in nrouterconnections))
			nrouterconnections[ridtmp] = 0;
		routerconnections[ridtmp, nrouterconnections[ridtmp]] = NUMAlink2router($6);
		nrouterconnections[ridtmp]++;
		if (debug)
			printf("NUMAlink %d:  %s -> %s\n", nnumalinks,
			       numalinklocalid[$2], numalinkremoteid[$2]);
	}
	nnumalinks++;
}

#	router 0 001c05#4 local asic NL4Router
#	router 1 001c21#5 shared asic NL4Router
/^router[[:space:]]+[[:digit:]]+/ {
	routernum[$3] = $2;
	routerid[$2] = $3;
	if (debug)
		printf("router[%d]:  id %s\n", nrouters, $3);
	nrouters++;
}

#	read a list of "cpus" and "mems" files from the "cpuset" file system
#	and remember those CPUs and memory board numbers found there.  Later
#	(in printmompsdefs() and printqmgrpsdefs()) any vnode containing an
#	excluded CPU or memory board will not appear in the resulting placement
#	definitions.
function read_excludelist(listfile)
{
	if (debug)
		printf("read_excludelist:  listfile %s\n", listfile);
	if (listfile ~ "/cpus$" || listfile ~ "/cpuset.cpus$") {
		while ((getline cpumemlist < listfile) > 0)
			parse_CPUs(cpumemlist);
		close(listfile);
	} else if (listfile ~ "/mems$" || listfile ~ "/cpuset.mems$") {
		while ((getline cpumemlist < listfile) > 0)
			parse_mems(cpumemlist);
		close(listfile);
	} else {
		printf("read_excludelist:  not reading from cpus or mems\n");
		exit (1);
	}
}

#	break list at ',' characters, if any, then handle lists of
#	the form M or "M-N"
function parse_CPUs(cpulist,		cpusublist, rangenum)
{
	split(cpulist, cpusublist, ",");
	for (rangenum in cpusublist)
		exclude_range(cpusublist[rangenum], "cpus");
}


#	break list at ',' characters, if any, then handle lists of
#	the form M or "M-N"
function parse_mems(memlist,		memsublist, rangenum)
{
	#	break list at ',' characters, if any, then handle lists of
	#	the form M or "M-N"

	split(memlist, memsublist, ",");
	for (rangenum in memsublist)
		exclude_range(memsublist[rangenum], "mems");
}

function exclude_range(range, excltype,	nexcludedcpus, nexlcudedmems,
					nnums, nums)
{
	nnums = split(range, nums, "-");

	if (nnums == 1) {
		if (debug)
			printf("exclude %s %d\n", excltype, nums[1]);
		nums[2] = nums[1];
	} else if (nnums == 2) {
		if (debug)
			printf("exclude %s %d - %d\n", excltype,
			    nums[1], nums[2]);
	} else {
		printf("exclude_cpus:  internal error - nnums (%d) > 2\n",
		    nnums);
		exit (1);
	}

	if (excltype == "cpus")
		for (exclindex = nums[1]; exclindex <= nums[2]; exclindex++)
			excludedCPUs[nexcludedcpus++] = exclindex;
	else
		for (exclindex = nums[1]; exclindex <= nums[2]; exclindex++)
			excludedmems[nexcludedmems++] = exclindex;
}

function report_memory(nodenum,		meminfofile)
{
	# use "-v sysdir=/..." to direct this script to an alternate /sys
	meminfofile = sysdir "/sys/devices/system/node/node" nodenum "/meminfo";

	if (debug)
		printf("report_memory(node %d, meminfofile %s)\n", nodenum,
		    meminfofile);
	while ((getline meminfo < meminfofile) > 0)
		if (meminfo ~ /MemTotal/) {
			sub(".*MemTotal:[[:space:]]*", "", meminfo);
			sub("[[:space:]]*[kK][bB]$", "", meminfo);
			close(meminfofile);
			return (meminfo);
		}
	close(meminfofile);

	printf("No memory information for node %d\n", nodenum) | "cat 1>&2";
	return (-1);
}

#	emit the virtual partition list prologue, if any
function momprologue(			firsttime, momfmt,
					nocpusfmt, nomemfmt, novmemfmt,
					pnamefmt, sharedfmt, t, versionfmt)
{
	versionfmt = "$configversion 2\n";	# same as CONFIG_VNODEVERS
	pnamefmt = "%s:  pnames = %s";
	sharedfmt = "%s:  sharing = ignore_excl\n";
	nocpusfmt = "%s:  resources_available.ncpus = 0\n";
	nomemfmt = "%s:  resources_available.mem = 0\n";
	novmemfmt = "%s:  resources_available.vmem = 0\n";

	printf(versionfmt);

	firsttime = 1;
	for (t in pnames) {
		if (firsttime == 1) {
			firsttime = 0;
			printf(pnamefmt, nodename, pnames[t]);
		} else {
			printf(",%s", pnames[t]);
		}
	}
	if (npnames > 0)
		printf("\n");

	printf(sharedfmt, nodename);
	printf(nocpusfmt, nodename);
	printf(nomemfmt, nodename);
	printf(novmemfmt, nodename);
}

#	emit the virtual partition list prologue, if any
function qprologue(			firsttime,
					nocpusfmt, nomemfmt, novmemfmt,
					pnamefmt, sharedfmt, t)
{
	pnamefmt = "set node %s pnames = \"%s"
	sharedfmt = "set node %s sharing = ignore_excl\n";
	nocpusfmt = "set node %s resources_available.ncpus = 0\n";
	nomemfmt = "set node %s resources_available.mem = 0\n";
	novmemfmt = "set node %s resources_available.vmem = 0\n";

	firsttime = 1;
	for (t in pnames) {
		if (firsttime == 1) {
			firsttime = 0;
			printf(pnamefmt, nodename, pnames[t]);
		} else {
			printf(",%s", pnames[t]);
		}
	}
	if (npnames > 0)
		printf("\"\n");

	printf(sharedfmt, nodename);
	printf(nocpusfmt, nodename);
	printf(nomemfmt, nodename);
	printf(novmemfmt, nodename);
}

#	for debugging
#	consistency checks:  distance should be symmetric
function doconsistencychecks(		i, j)
{
	for (i in cpuid)
		for (j = 0; j < ncpus; j++)
			if (cpudist[i, j] != cpudist[j, i]) {
				printf("cpudist[%d, %d] (%s) != ", i, j,
				    cpudist[i, j]);
				printf("cpudist[%d, %d] (%s)\n", j, i,
				    cpudist[j, i]);
			}
	if (is_UV == 0)
		for (i in nodeid) {
			for (j = 0; j < nnodes; j++) {
				if (nodedist[i, j] != nodedist[j, i]) {
					printf("nodedist[%s, %d] (%s) != ", i, j,
					    nodedist[i, j]);
					printf("nodedist[%d, %s] (%s)\n", j, i,
					    nodedist[j, i]);
				}
			}
		}
}

#	for debugging
function dumpnodeinfo(			cid, i, ix, j, UVnode)
{
	for (i in nodeid) {
		for (j in cpuid) {
			if (is_UV) {
				split(cpuid[j], UVnode, "_");
				cid = UVnode[1];
			} else {
				cid = cpuid[j];
			}
				
			if ((nodeid[i] != "") && (cid != "")) {
				if ((ix = index(cid, nodeid[i])) == 1) {
					printf("dumpnodeinfo:  cpuid[%s] = \"%s\", nodeid[%s] = \"%s\", index(cid, nodeid[i]) = %d\n", j, cpuid[j], i, nodeid[i], ix);
					printf("node %s contains CPU[%s]\n", nodeid[i], j);
				}
			}
		}
	}
}

#	for debugging
function dumprouterinfo(		i, j, k, rconn, rid)
{
	for (i in routerid) {
		for (j in numalinklocalid) {
			if (index(numalinklocalid[j], routerid[i]) == 1) {
				rid = numalinkremoteid[j];
				for (k in nodeid) {
					if (index(rid, nodeid[k]) == 1) {
						printf("router[%s] -> node %s\n",
						    i, nodeid[k]);
					}
				}
			}
		}
	}

	for (i = 0; i < nrouters; i++) {
		rid = routerid[i];
		for (j = 0; j < nrouterconnections[rid]; j++) {
			rconn = routerconnections[rid, j];
			printf("router %s connected to %s %s\n", rid,
			    (rconn in nodenums) ? "node" : "router", rconn);
		}
	}

}

#	Add a new placement set type, t, to the list of known types.
function newpstype(t)
{
	if (!(t in pnames)) {
		if (debug)
			printf("newpstype:  \"%s\"\n", t);
		pnames[npnames++] = t "";
	}
}

#	Emit vnode definitions for consumption by pbs_mom.
#	In constructing vnode names, we are careful to ensure that the index
#	(in name[index]) is the same as the node number that appears in the
#	sn_topology file.
#
#	In constructing the values for the placement sets, we are also careful
#	to ensure that the index (in R[index]) is the same as the router number
#	in the sn_topology file.  We must also be sure when concatenating names
#	to form the a placement set value that we always concatenate in the same
#	order (that is, even though a human can tell that placement set "ABC" is
#	the same as placement set "BCA", PBS regards them as different);  we
#	achieve this by always traversing the router list the same way.
function printmompsdefs(			cpusfmt, cpuspernode, i, j, id,
						exclCPUfmt, exclmemfmt, extmp,
						firsttime, 
						memfmt, ncpusfmt, psfmt,
						ptmp, rid, vnodename)
{
	psfmt = "%s:  resources_available.%s = %s\n";
	cpusfmt = "%s:  cpus = %s\n";
	memnodefmt = "%s:  mems = %d\n";
	ncpusfmt = "%s:  resources_available.ncpus = %d\n";
	memfmt = "%s:  resources_available.mem = %dkb\n";
	exclCPUfmt = "deleting node[%d] (ID %s) - contains excluded CPU %d\n";
	exclmemfmt = "deleting node[%d] (ID %s) - contains excluded memory %d\n";

	#	Refrain from reporting any vnode which contains an excluded CPU.
	for (i in excludedCPUs) {
		extmp = excludedCPUs[i];
		for (j in nodeid)
			if (index(cpuid[extmp], nodeid[j]) == 1) {
				if (debug)
					printf(exclCPUfmt, j, nodeid[j], extmp);
				delete nodeid[j];
				nnodes--;
			}
	}

	#	Refrain from reporting any vnode which contains an excluded
	#	memory board.  This relies on the fact that there is exactly
	#	one memory board per topology file node.
	for (i in excludedmems) {
		extmp = excludedmems[i];
		if (nodeid[extmp] != "") {
			if (debug)
				printf(exclmemfmt, extmp, nodeid[extmp], extmp);
			delete nodeid[extmp];
			nnodes--;
		}
	}

	for (i in nodeid) {
		if ((id = nodeid[i]) == "")
			continue;

		#	Make sure that the vnode name we construct maps directly
		#	to the node number in the sn_topology file.
		vnodename = nodename "[" nodenums[id] "]";

		printf("%s:  sharing = default_excl\n", vnodename);

		cpuspernode = 0;
		vnodeCPUs = "";
		for (j in cpuid)
			if (index(cpuid[j], id) == 1) {
				if (cpuspernode == 0)
					vnodeCPUs = j;
				else
					vnodeCPUs = vnodeCPUs "," j;
				cpuspernode++;
			}

		if (cpuspernode > 0) {
			printf(ncpusfmt, vnodename, cpuspernode);
			printf(cpusfmt, vnodename, vnodeCPUs);
		} else
			printf(ncpusfmt, vnodename, 0);

		meminfo = report_memory(i);
		if (meminfo >= 0) {
			printf(memfmt, vnodename, meminfo);
			printf(memnodefmt, vnodename, i)
		} else
			printf(memfmt, vnodename, 0);

		if ((cpuspernode > 0) || (meminfo > 0)) {
			firsttime = 1;
			ptmp = "";
			#	Make sure that the router names in the placement
			#	set values map directly to the router numbers in
			#	the sn_topology file.
			for (j = 0; j < nrouters; j++) {
				rid = routerid[j];
				if (index(nodesof[rid], id))
					if (firsttime) {
						firsttime = 0;
						ptmp = pshort routernum[rid];
					} else
						ptmp = ptmp "," pshort routernum[rid];
			}
			if (ptmp != "") {
				#	add a value for the whole machine
				ptmp = ptmp "," nodename;
				printf(psfmt, vnodename, ptype, ptmp);
			}
		}
	}
}

#	Emit vnode definitions for consumption by qmgr.
#	In constructing vnode names, we are careful to ensure that the index
#	(in name[index]) is the same as the node number that appears in the
#	sn_topology file.
#
#	In constructing the values for the placement sets, we are also careful
#	to ensure that the index (in R[index]) is the same as the router number
#	in the sn_topology file.  We must also be sure when concatenating names
#	to form the a placement set value that we always concatenate in the same
#	order (that is, even though a human can tell that placement set "ABC" is
#	the same as placement set "BCA", PBS regards them as different);  we
#	achieve this by always traversing the router list the same way.
function printqmgrpsdefs(		i, j, id, cpuspernode,
					exclCPUfmt, exclmemfmt, extmp,
					firsttime,
					memfmt, ncpusfmt, psfmt,
					ptmp, rid, vnodename)
{
	ncpusfmt = "set node %s resources_available.ncpus = %d\n";
	memfmt = "set node %s resources_available.mem = %dkb\n";
	psfmt = "set node %s resources_available.%s = %s\n";
	exclCPUfmt = "deleting node[%d] (ID %s) - contains excluded CPU %d\n";
	exclmemfmt = "deleting node[%d] (ID %s) - contains excluded memory %d\n";

	#	Refrain from reporting any vnode which contains an excluded CPU.
	for (i in excludedCPUs) {
		extmp = excludedCPUs[i];
		for (j in nodeid)
			if (index(cpuid[extmp], nodeid[j]) == 1) {
				if (debug)
					printf(exclCPUfmt, j, nodeid[j], extmp);
				delete nodeid[j];
				nnodes--;
			}
	}

	#	Refrain from reporting any vnode which contains an excluded
	#	memory board.
	for (i in excludedmems) {
		extmp = excludedmems[i];
		if (nodeid[extmp] != "") {
			if (debug)
				printf(exclmemfmt, extmp, nodeid[extmp], extmp);
			delete nodeid[extmp];
			nnodes--;
		}
	}

	for (i in nodeid) {
		if ((id = nodeid[i]) == "")
			continue;

		#	Make sure that the vnode name we construct maps directly
		#	to the node number in the sn_topology file.
		vnodename = nodename "[" nodenums[id] "]";

		printf("set node %s sharing = default_excl\n",
		    vnodename);

		cpuspernode = 0;
		vnodeCPUs = "";
		for (j in cpuid)
			if (index(cpuid[j], id) == 1) {
				if (cpuspernode == 0)
					vnodeCPUs = j;
				else
					vnodeCPUs = vnodeCPUs "," j;
				cpuspernode++;
			}

		if (cpuspernode > 0) {
			printf(ncpusfmt, vnodename, cpuspernode);

			meminfo = report_memory(i);
			if (meminfo >= 0)
				printf(memfmt, vnodename, meminfo);
			firsttime = 1;
			ptmp = "";
			#	Make sure that the router names in the placement
			#	set values map directly to the router numbers in
			#	the sn_topology file.
			for (j = 0; j < nrouters; j++) {
				rid = routerid[j];
				if (index(nodesof[rid], id))
					if (firsttime) {
						firsttime = 0;
						ptmp = pshort routernum[rid];
					} else
						ptmp = ptmp "," pshort routernum[rid];
			}
			if (ptmp != "") {
				#	add a value for the whole machine
				ptmp = ptmp "," nodename;
				printf(psfmt, vnodename, ptype, ptmp);
			}
		}
	}
}

#	These are functions to convert between various IDs (CPU, node, NUMAlink,
#	router).  The IDs follow a pattern illustrated by this excerpt
#
#		cpu 1 001c01^3#0a local freq 1596MHz, arch ia64, ...
#		node 1 001c01^3#0 local asic SHub_2.0, nasid 0x2, ...
#		numalink 4 001.01^10#0-2 local endpoint 001c01^3#0-0, ...
#		router 0 001.01^10#0 local asic NL4Router
#		numalink 14 001.01^11#1-4 local endpoint 001c01^3#0-1, ...
#		router 1 001.01^11#1 local asic NL4Router
#
#	from an sn_topology file.
#	A node ID is derived from a CPU ID by dropping the last character:
function CPU2node(id,				tmpid)
{
	tmpid = id;
	sub(/.$/, "", tmpid)

	return (tmpid);
}

#	A router ID is derived from a NUMAlink ID by dropping the trailing
#	"-[[:digit:]]":
function NUMAlink2router(id,			tmpid)
{
	tmpid = id;
	sub(/-[[:digit:]]$/, "", tmpid)

	return (tmpid);
}

#	Find routers h hops removed from a node.  We depend on having already
#	computed the list of routers that are less than h hops removed, in
#	which case any router whose hop count is still not known and which is
#	one hop removed from a router with hop count h-1 must have hop count h.
#	The function returns the number of new assignements done.
function nexthop(h,				i, j, ndone, rid, rtmp)
{
	ndone = 0;
	for (i = 0; i < nrouters; i++) {
		rid = routerid[i];
		if (hops[rid] != -1)
			continue;
		for (j = 0; j < nrouterconnections[rid]; j++) {
			rtmp = routerconnections[rid, j];
			if ((rtmp in hops) && (hops[rtmp] == (h - 1))) {
				hops[rid] = h;
				ndone++;
				break;
			}
		}
	}

	return (ndone);
}

#	Use an expanding ring to assign hop counts (number of hops removed from
#	a node) to routers, and returns the maximum possible hop count.
function genhops(				curhop, i, j, nroutersleft,
						progress, rid)
{
	curhop = 1;
	nroutersleft = nrouters;

	#	The first pass is special since we care only about routers that
	#	are directly connected to nodes.
	for (i = 0; i < nrouters; i++) {
		rid = routerid[i];
		progress = 0;
		for (j = 0; j < nrouterconnections[rid]; j++)
			if (routerconnections[rid, j] in nodenums) {
				hops[rid] = curhop;
				nroutersleft--;
				progress = 1;
				break;
			}
		if (progress == 0)
			hops[rid] = -1;
	}

	#	Now derive the count for the rest of the routers, one hop at a
	#	time.  As a safety measure, we terminate the loop if we have
	#	made no progress (found no routers with a given hop count).
	do {
		curhop++;
		progress = nexthop(curhop);
		nroutersleft -= progress;
	} while ((progress > 0) && (nroutersleft > 0));

	if (debug == 1)
		for (i = 0; i < nrouters; i++) {
			rid = routerid[i];
			printf("router %s:  hop %d\n", rid, hops[rid]);
		}

	return (curhop);
}

#	This function generates placement sets for each router based on
#	the nodes to which the router is connected (through one or more
#	hops).  For each router, we build a list (nodesof[router ID]),
#	which is a concatenation of the node IDs for each node (if any)
#	to which the router is directly connected.  For subsequent hops
#	H (2 through nhops), the list of nodes for each new router, R,
#	is formed by concatenating the lists for every router directly
#	connected to R whose hop count is less than H.
function genps(nhops,				curhop, i, j, nid, rconn, rid)
{
	curhop = 1;

	#	The first pass is special since we care only about routers that
	#	are directly connected to nodes.
	newpstype(ptype);
	for (i = 0; i < nrouters; i++) {
		rid = routerid[i];
		if (hops[rid] == curhop) {
			nodesof[rid] = "";
			for (j = 0; j < nrouterconnections[rid]; j++) {
				rconn = routerconnections[rid, j];
				if (is_UV) {
					#	nid[1] will be the router ID
					#	(currently dysfunctional)
					split(j, nid, "#");
					if (rid == nid[1])
						nodesof[rid] = nodesof[rid] "" rconn;
				} else {
					if (rconn in nodenums)
						nodesof[rid] = nodesof[rid] "" rconn;
				}
			}
		}
	}

	#	For
	do {
		curhop++;
		for (i = 0; i < nrouters; i++) {
			rid = routerid[i];
			if (hops[rid] == curhop) {
				#	This should not happen ...
				if ((debug == 1) && (rid in nodesof))
					printf("router %s in nodesof[]\n", rid);
				nodesof[rid] = "";
				for (j = 0; j < nrouterconnections[rid]; j++) {
					rconn = routerconnections[rid, j];
					if (hops[rconn] < curhop)
						nodesof[rid] = nodesof[rid] "" nodesof[rconn];
				}
			}
		}
	} while (curhop <= nhops);

	if (debug == 1)
		for (i = 0; i < nrouters; i++) {
			rid = routerid[i];
			printf("router %s:  hop %d, nodesof %s\n",
			    rid, hops[rid], nodesof[rid]);
		}
}

function verscheck(vers, version_min, version_max)
{
	if ((vers < version_min) || (vers > version_max)) {
		printf("unsupported version (%d) - not between %d and %d\n",
		    vers, version_min, version_max);
		exitval = 1;
		exit(1);
	}
}

#	This function infers the existence of nodes and routers in order to
#	allow this script to work for both UV and non-UV systems with minimal
#	changes.  It does this by assuming that the blade IDs (a.k.a. nodes)
#	are derived from CPU IDs by truncating the ID string at an '_' character
#	and that routers are derived from blade IDs by truncating at a '#'
#	character.
function UV_infer_nodes_and_routers(		i, n, nid, UVnodeID, UVnode, nlid)
{
	if (nnodes == 0) {
		n = asort(cpuid, temp)
		for (i = 0; i < n; i++) {
			split(cpuid[i], UVnode, "_");
			UVnodeID = UVnode[1];

			if (UVnodeID in nodenums)
				continue;
			else {
				#	nid is currently unused;
				#	nid[1] would be a router ID
				split(UVnodeID, nid, "#");
				nodenums[UVnodeID] = nnodes;
				nodeid[nnodes] = UVnodeID "";
				if (debug) {
					printf("nodenums[%s]:  %d\n", UVnodeID, nnodes);
					printf("nodeid[%d]:  %s\n", nnodes, nodeid[nnodes]);
				}
				nnodes++;
			}
		}
	}
	if (nrouters == 0) {
		for (i in numalinklocalid) {
			nlid = NUMAlink2router(numalinklocalid[i]);
			if (nlid in routernum) {
				if (debug)
					printf("router %s already in routernum\n", nlid);
				continue;
			}
			routernum[nlid] = nrouters;
			routerid[nrouters] = nlid;
			if (debug) {
				printf("routernum[%s]:  %d\n", nlid, nrouters);
				printf("routerid[%d]:  %s\n", nrouters, nlid);
			}
			nrouters++;
		}
	}
}

END {
	#	Even though BEGIN may have called exit(), the END rule will
	#	still be executed.  Avoid any actions that shouldn't occur
	#	in that case.
	if (exitval)
		exit(exitval);

	if (is_UV)
		UV_infer_nodes_and_routers();
	if (debug) {
		doconsistencychecks();
		dumpnodeinfo();
		dumprouterinfo();
	}

	numhops = genhops();
	genps(numhops);

	if (type == "m") {
		momprologue();
		printmompsdefs();
	} else if (type == "q") {
		qprologue();
		printqmgrpsdefs();
	}
}
