# Copyright (C) 1994-2018 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# For a copy of the commercial license terms and conditions,
# go to: (http://www.pbspro.com/UserArea/agreement.html)
# or contact the Altair Legal Department.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

#	When an MPI job executes within the PBS environment, MPI resource
#	specification and PBS resource selections may conflict (for example,
#	on choice of execution host).  This script works in conjunction with
#	the PBS mpiexec script to transform those MPI resource specifications
#	to instead use the resources provided by PBS.
#
#	It does this by consulting the PBS nodes file (whose name appears in
#	the "PBS_NODEFILE" environment variable) to determine the host names
#	and available number of CPUs per host (the latter by counting the
#	number of times a given host name appears in the nodes file), then
#	assigning hosts and CPUs to MPI resource specifications in a round-
#	robin fashion.
#
#	We expect to be passed values for these variables by the PBS mpiexec
#	that invokes us,
#
#		configfile	is a file either supplied as an argument to
#				mpiexec, or constructed by the PBS mpiexec
#				script to represent the concatenation of rank
#				specifications on the mpiexec command line,
#
#		runfile		is the output file into which this program
#				should put the vendor-specific invocations
#				that implement the various mpiexec directives
#
#		pbs_exec	is the value of $PBS_EXEC from the pbs.conf file
#
#		debug		may be set to enable this program to report
#				some of its internal workings
#
#	To customize this program for a different vendor, change the functions
#
#		vendor_init	which does one-time per-vendor initializations,
#				and
#
#		vendor_dorank	which formats and returns a rank specification
#				for output to the supplied runfile

function init()
{
	if ((jobid = ENVIRON["PBS_JOBID"]) == "") {
		printf("cannot find \"PBS_JOBID\" in environment\n");
		exit 1;
	}

	if (configfile == "") {
		printf("no mpiexec configfile specified\n");
		exit 1;
	}

	if (runfile == "") {
		printf("no output run file specified\n");
		exit 1;
	}

	vendor_init();
}

function vendor_init()
{
	SGIMPI_init();
}

function vendor_dorank()
{
	return SGIMPI_dorank();
}

function SGIMPI_init()
{
	SGIMPI_cmdfmt = sprintf("%%s%%s -np %%d %%s -j %s  %%s %%s",
	    jobid);
}

function SGIMPI_dorank(ret)
{
	ret = sprintf(SGIMPI_cmdfmt, ranksep, rank[HOST], rank[NCPUS],
	    pbs_exec "/bin/pbs_attach", prog, args);
	ranksep = ": ";		# for all but the first line of the config file

	return (ret);
}

#	Break a line from the supplied configuration file into ranks, validate
#	the syntax, assign nodes to the ranks, and emit the vendor-specific
#	invocations for later use by the calling PBS mpiexec script.
function doline(i, type, val)
{
	linenum++;
	ranknum = 0;
	reset_rank();
	for (i = 1; i <= NF; i++) {
		type = $i;
		if (type ~ argpat) {
			# mpiexec directive
			in_rankdef = 1;
			sub(/^-/, "", type);
			if (i == NF) {
				printf(missingvalfmt,
				       configfile, linenum, type);
				return;
				exit 1;
			} else {
				i++;
				val = $i;
			}
			rank[type] = val;
		} else if (type == ":") {
			# rank separator
			in_rankdef = 0;
			break;
		} else {
			# program and its arguments
			prog = $i;
			i++;
			for (; i <= NF; i++) {
				if ($i == ":")
					break;
				else
					args = args " " $i;
			}
			assign_nodes();
			ranknum++;
			reset_rank();
			in_rankdef = 0;
		}
	}

	if ((in_rankdef == 1) && (prog == "")) {
		printf(missingcmdfmt, configfile, linenum, ranknum);
		return;
		exit 1;
	}

}

#	(re)initializations to be done when beginning a new rank
function reset_rank(r)
{
	for (r in rank)
		delete rank[r];

	prog = "";
	args = "";

	rank[NCPUS] = num_nodes;	# default is implementation-dependent
}

#	Emit a rank specification into the runfile.
function dorank(r)
{
	if (debug) {
		for (r in rank)
			printf("line %d, rank #%d:  %s=%s\n",
			    linenum, ranknum, r, rank[r]);
		printf("line %d, rank #%d:  prog:  %s, args %s\n",
		    linenum, ranknum, prog, args);
	}

	printf("%s\n", vendor_dorank()) >> runfile;
}

#	Read the PBS nodes file, remembering the node names and CPUs per node.
function read_nodefile(nf, pbs_nodefile)
{
	pbs_nodefile = "PBS_NODEFILE";

	if ((nf = ENVIRON[pbs_nodefile]) == "") {
		printf("cannot find \"%s\" in environment\n", pbs_nodefile);
		exit 1;
	}

	nodeindex = 0;
	while ((getline < nf) > 0) {
		if ($0 in cpus_per_node)
			cpus_per_node[$0]++;
		else {
			nodelist[nodeindex] = $0;
			cpus_per_node[$0] = 1;
			nodeindex++;
		}
	}
	close(nf);

	if (nodeindex == 0) {
		if ((getline < nf) == -1)
			printf(badnodefilefmt, nf);
		else
			printf(nonodesfmt, nf);
		exit 1;
	}
	num_nodes = nodeindex;
	reinit_avail();
}

#	for debugging
function report_nodefile(node)
{
	print "report_nodefile:  num_nodes " num_nodes;
	for (node = 0; node < num_nodes; node++)
		printf("\tnode %s:  CPUs available:  %d\n", nodelist[node],
		    cpus_per_node[nodelist[node]]);
}

#	This does a virtual rewind of the PBS nodes list, resetting the
#	number of CPUs available to that determined in read_nodefile().
function reinit_avail(node)
{
	for (node = 0; node < num_nodes; node++)
		cur_avail[node] = cpus_per_node[nodelist[node]];
	nodeindex = 0;
}

#	Step through the nodelist[] array, consuming CPU resources.  When doing
#	so, either we satisfy a rank specification or must go on to the next
#	host;  in either case we emit the current rank spec before proceeding.
function assign_nodes(cpus_needed, node)
{
	cpus_needed = rank[NCPUS];

	while (cpus_needed > 0) {
		for (node = nodeindex; node < num_nodes; node++) {
			rank[HOST] = nodelist[node];
			if (cur_avail[node] >= cpus_needed) {
				cur_avail[node] -= cpus_needed;
				rank[NCPUS] = cpus_needed;
				dorank();
				if (cur_avail[node] == 0)
					nodeindex++;
				return;
			} else {
				rank[NCPUS] = cur_avail[node];
				cpus_needed -= cur_avail[node];
				cur_avail[node] = 0;
				dorank();
				nodeindex++;
				continue;
			}
		}
		reinit_avail();
	}
}

BEGIN	{
		linenum = 0;
		argpat = "^-(arch|host|file|n|path|soft|wdir)$";
		badnodefilefmt = "could not read PBS_NODEFILE \"%s\"\n";
			nonodesfmt = "no nodes found in PBS_NODEFILE \"%s\"\n";
		missingcmdfmt = "%s line %d rank %d has no executable\n";
		missingvalfmt = "%s line %d:  argument \"-%s\":  missing val\n";
		# symbolic name for readability
		HOST = "host"
		NCPUS = "n";

		init();

		read_nodefile();
		if (debug)
			report_nodefile();

		while ((getline < configfile) > 0)
			doline();
		close(configfile);
	}
