/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of both the OpenPBS software ("OpenPBS")
 * and the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * OpenPBS is free software. You can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * OpenPBS is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * PBS Pro is commercially licensed software that shares a common core with
 * the OpenPBS software.  For a copy of the commercial license terms and
 * conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
 * Altair Legal Department.
 *
 * Altair's dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of OpenPBS and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair's trademarks, including but not limited to "PBS™",
 * "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
 * subject to Altair's trademark licensing policies.
 */

/**
 * @file
 *		pbs_probe.c
 *
 * @brief
 * 		Much of this program derives from the PBS utility chk_tree
 * 		and the manner in which thing were done in that program.
 *
 * Functions included are:
 * 	main()
 * 	am_i_authorized()
 * 	infrastruct_params()
 * 	print_infrastruct()
 * 	title_string()
 * 	print_problems()
 * 	msg_table_set_defaults()
 * 	get_primary_values()
 * 	pbsdotconf()
 * 	get_realpath_values()
 * 	is_parent_rpathnull()
 * 	inspect_dir_entries()
 * 	which_suffixset()
 * 	is_suffix_ok()
 * 	which_knwn_mpugs()
 * 	chk_entries()
 * 	pbs_dirtype()
 * 	non_db_resident()
 * 	is_a_numericname()
 * 	check_paths()
 * 	check_owner_modes()
 * 	mbits_and_owner()
 * 	perm_owner_msg()
 * 	perm_string()
 * 	owner_string()
 * 	process_ret_code()
 * 	conf4primary()
 * 	env4primary()
 * 	fix()
 * 	fix_perm_owner()
 *
 */
#include <pbs_config.h>

#include <Python.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <fcntl.h>
#include <pwd.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <assert.h>
#include <dirent.h>
#include <grp.h>
#include "cmds.h"
#include "pbs_version.h"
#include "pbs_ifl.h"
#include "glob.h"

// clang-format off

#ifndef	S_ISLNK
#define	S_ISLNK(m)	(((m) & S_IFMT) == S_IFLNK)
#endif

#define	DEMARC	'/'
#define DFLT_MSGTBL_SZ (1024)

/* ---- required and disallowed dir/file modes ----*/

#define DFLT_REQ_DIR_MODES (S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IWOTH)
#define DFLT_DIS_DIR_MODES (S_IWGRP | S_IWOTH)

#define rwxrxrx		(S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH)
#define frwxrxrx	(S_IFREG | S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH)
#define drwxrxrx	(S_IFDIR | S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH)
#define tdrwxrwxrwx	(S_ISVTX | S_IFDIR | S_IRWXU | S_IRWXG | S_IRWXO)
#define tgworwx		(S_ISVTX | S_IWGRP | S_IRWXO)

#define drwxgo		(S_IFDIR | S_IRWXU)
#define drwxrxo		(S_IFDIR | S_IRWXU | S_IRGRP | S_IXGRP)
#define tgrwxorwx	(S_ISVTX | S_IRWXG | S_IRWXO)
#define tgwow		(S_ISVTX | S_IWGRP | S_IWOTH)

#define drwxrxx		(S_IFDIR | S_IRWXU | S_IRGRP | S_IXGRP | S_IXOTH)
#define tgworw		(S_ISVTX | S_IWGRP | S_IROTH | S_IWOTH)
#define dtgwow		(S_IFDIR | S_ISVTX | S_IWGRP | S_IWOTH)

#define frwxrxrx	(S_IFREG | S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH)
#define sgswow		(S_ISUID | S_ISGID | S_IWGRP | S_IWOTH)

#define fsrwxrxrx	(S_IFREG | S_ISUID | S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH)
#define gswow		(S_ISGID | S_IWGRP | S_IWOTH)

#define frwxgo		(S_IFREG | S_IRWXU)
#define sgsrwxorwx	(S_ISUID | S_ISGID | S_IRWXG | S_IRWXO)

#define frwrr		(S_IFREG | S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH)
#define xsgswxowx	(S_IXUSR | S_ISUID | S_ISGID | S_IWGRP | S_IXGRP | S_IWOTH | S_IXOTH)

#define frwgo		(S_IFREG | S_IRUSR | S_IWUSR)
#define xsgsrwxorwx	(S_IXUSR | S_ISUID | S_ISGID | S_IRWXG | S_IRWXO)

#define frgror		(S_IFREG | S_IRUSR | S_IRGRP | S_IROTH)
#define sgswxowx	(S_ISUID | S_ISGID | S_IWGRP | S_IXGRP | S_IWOTH | S_IXOTH)

#define	drwxrr		(S_IFDIR | S_IRWXU | S_IRGRP | S_IROTH)
#define tgwxowx		(S_ISVTX | S_IWGRP | S_IXGRP | S_IWOTH | S_IXOTH)


/* ---- Codes to identify the source of various data items ----*/

#define	SRC_NONE	0	/* no source/can't determine */
#define	SRC_DFLT	1	/* source is default value */
#define	SRC_ENV		2	/* source is environment variable */
#define	SRC_CONF	3	/* source is PBS config file */


/* -----------  error values -------------*/

#define	PBS_CONF_NO_EXIST	1
#define	PBS_CONF_CAN_NOT_OPEN	2

#define LSTAT_PATH_ERR	-1
#define PATH_ERR	 1


typedef struct  statdata {
	int populated;		/* member "sb" populated */
	struct stat	sb;	/* stat  "buffer" */
} STATDATA;

typedef struct  utsdata {
	int	populated;	/* member "ub" populated */
	struct  utsname ub;	/* uname "buffer" */
} UTSDATA;

typedef struct vld_ug {
	/*
	 * each directory/file in the PBS infrastructure should
	 * one of these "valid users, valid groups" structures
	 * associated with it
	 */
	int	*uids;		/* -1 terminated array UID values */
	int	*gids;		/* -1 terminated array GID values */

	char	**unames; 	/* null terminated table user names */
	char	**gnames; 	/* null terminated table group names */
} VLD_UG;


typedef struct modes_path_user_group {
	/*
	 * each directory/file in the PBS infrastructure should have
	 * one of these "modes, path, user, group, type" structures
	 * associated with it
	 */
	int	fc;		/* fix code: 0=no, 1=perm/own, 2=create */

	int	notReq;		/* bit1 (0x1): 0=always required, 1=never required
				   bit2 (0x2): 1=not required for command-only install
				   bit3 (0x4): 1=not required for execution-only install
				   Note: used in conjunction with "notbits"
				 */

	int	chkfull;	/* 1=check each path component */

	int	req_modes;	/* required permissions (modes) */
	int	dis_modes;	/* disallowed permissions (modes) */
	VLD_UG	*vld_ug;	/* tables of valid users and groups */
	char	*path;		/* location of file/directory */
	char	*realpath;	/* canonicalized absolute location */
} MPUG;

typedef struct modeadjustments {
	/*
	 * an instance of this structure will contain modification
	 * data that should be used in conjunction with the mode data
	 * found in a corresponding MPUG data struccture.
	 */
	int	req;	/* required modes   */
	int	dis;	/* disallowed modes */
} ADJ;


typedef struct primary {

	MPUG	*pbs_mpug;	/* MPUGs: PBS primary dirs/files */

	/*
	 * record values and sources for "path" and "started"
	 */

	struct {
		unsigned	server:1, mom:1, sched:1;
	} started;

	struct {
		unsigned	server:2, mom:2, sched:2;
	} src_started;

	struct {
		unsigned	conf:2, home:2, exec:2;
	} src_path;

} PRIMARY;

/*
 * Numeric codes - use in title generation (see function, title_string)
 */
enum code_title { TC_top, TC_sys, TC_ro, TC_fx, TC_pri, TC_ho, TC_ex,
	TC_cnt, TC_tvrb, TC_datpri, TC_datho, TC_datex, TC_noerr,
	TC_use };
/*
 * Numeric codes - for use in function process_ret_code()
 */
enum func_names { GET_PRIMARY_VALUES, END_FUNC_NAMES };

/*
 * Message Header data - use, output of pbs_probe's "Primary" variables
 */
enum	mhp { MHP_cnf, MHP_home, MHP_exec, MHP_svr, MHP_mom, MHP_sched };
static char mhp[][20] = {
	"PBS_CONF_FILE",
	"PBS_HOME",
	"PBS_EXEC",
	"PBS_START_SERVER",
	"PBS_START_MOM",
	"PBS_START_SCHED"
};

/* ---- default values for uid/gid, user names, group names ----*/

static int pbsdata[] = {-1, -1};		  /* PBS datastore */
static int pbsservice[] = {0, -1}; /* PBS daemon service user */
static int pbsu[] = {0, -1};		  /* PBS UID, default */
static int du[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1}; /* non-PBS UIDs, default */

static char *pbs_dataname[] = {"pbsdata", NULL}; /* PBS data name, default */
static char *pbs_servicename[] = {"root", NULL}; /* PBS daemon service name, default */
static char *pbs_unames[] = {"root", NULL}; /* PBS user name, default */
static char *pbs_gnames[] = {NULL}; /* PBS group name, default*/

static	int	dg[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1}; /* non-PBS GIDs, default */


/* ---------- default VLD_UG structures, PBS and non-PBS -----------*/

static VLD_UG dflt_pbs_data = { pbsdata, dg, &pbs_dataname[0], &pbs_gnames[0] };
static VLD_UG dflt_pbs_service = { pbsservice, dg, &pbs_servicename[0], &pbs_gnames[0] };
static VLD_UG dflt_pbs_ug = { pbsu, dg, &pbs_unames[0], &pbs_gnames[0] };
static VLD_UG dflt_ext_ug = { du, dg, &pbs_unames[0], &pbs_gnames[0] };

/* ============  PBS path names ============ */

static  char default_pbsconf[] = "/etc/pbs.conf";

/* ------------ PBS HOME: relative paths -----------*/


static char svrhome[][80] = {
	/* 00 */ "server_logs",
	/* 01 */ "spool",
	/* 02 */ "server_priv",
	/* 03 */ "server_priv/resourcedef",
	/* 04 */ "server_priv/server.lock",
	/* 05 */ "server_priv/tracking",
	/* 06 */ "server_priv/accounting",
	/* 07 */ "server_priv/jobs",
	/* 08 */ "server_priv/users",
	/* 09 */ "server_priv/hooks",
	/* 10 */ "server_priv/hooks/tmp",
	/* 11 */ "server_priv/prov_tracking",
	/* 12 */ "server_priv/db_password",
	/* 13 */ "server_priv/db_svrhost",
	/* 14 */ "server_priv/db_svrhost.new",
	/* 15 */ "server_priv/svrlive",
	/* 16 */ "datastore"
};

static char momhome[][80] = {
	/* 0 */ "aux",
	/* 1 */ "checkpoint",
	/* 2 */ "mom_logs",
	/* 3 */ "mom_priv",
	/* 4 */ "mom_priv/mom.lock",
	/* 5 */ "mom_priv/config",
	/* 6 */ "mom_priv/jobs",
	/* 7 */ "spool",
	/* 8 */ "undelivered",
	/* 9 */ "mom_priv/config.d",
	/* 10 */ "mom_priv/hooks",
	/* 11 */ "mom_priv/hooks/tmp"
};

static char schedhome[][80] = {
	/* 0 */ "sched_logs",
	/* 1 */ "sched_priv",
	/* 2 */ "sched_priv/dedicated_time",
	/* 3 */ "sched_priv/holidays",
	/* 4 */ "sched_priv/sched_config",
	/* 5 */ "sched_priv/resource_group",
	/* 6 */ "sched_priv/sched.lock",
	/* 7 */ "sched_priv/sched_out"
};

static char exec[][80] = {
	/* 0 */ "bin",
	/* 1 */ "etc",
	/* 2 */ "include",
	/* 3 */ "lib",
	/* 4 */ "man",
	/* 5 */ "sbin",
	/* 6 */ "tcltk",
	/* 7 */ "python",
	/* 8 */ "pgsql"
};



/* ------------ PBS EXEC: relative paths ----------*/

static char exbin[][80] = {
	/* 00 */ "bin/pbs_topologyinfo",
	/* 01 */ "bin/pbs_hostn",
	/* 02 */ "bin/pbs_rdel",
	/* 03 */ "bin/pbs_rstat",
	/* 04 */ "bin/pbs_rsub",
	/* 05 */ "bin/pbs_tclsh",
	/* 06 */ "bin/pbs_wish",
	/* 07 */ "bin/pbsdsh",
	/* 08 */ "bin/pbsnodes",
	/* 09 */ "bin/printjob",
	/* 10 */ "bin/qalter",
	/* 11 */ "bin/qdel",
	/* 12 */ "bin/qdisable",
	/* 13 */ "bin/qenable",
	/* 14 */ "bin/qhold",
	/* 15 */ "bin/qmgr",
	/* 16 */ "bin/qmove",
	/* 17 */ "bin/qmsg",
	/* 18 */ "bin/qorder",
	/* 19 */ "bin/qrerun",
	/* 20 */ "bin/qrls",
	/* 21 */ "bin/qrun",
	/* 22 */ "bin/qselect",
	/* 23 */ "bin/qsig",
	/* 24 */ "bin/qstart",
	/* 25 */ "bin/qstat",
	/* 26 */ "bin/qstop",
	/* 27 */ "bin/qsub",
	/* 28 */ "bin/qterm",
	/* 29 */ "bin/tracejob",
	/* 30 */ "bin/pbs_lamboot",
	/* 31 */ "bin/pbs_mpilam",
	/* 32 */ "bin/pbs_mpirun",
	/* 33 */ "bin/pbs_mpihp",
	/* 34 */ "bin/pbs_attach",
	/* 35 */ "bin/pbs_remsh",
	/* 36 */ "bin/pbs_tmrsh",
	/* 37 */ "bin/mpiexec",
	/* 38 */ "bin/pbsrun",
	/* 39 */ "bin/pbsrun_wrap",
	/* 40 */ "bin/pbsrun_unwrap",
	/* 41 */ "bin/pbs_python",
	/* 42 */ "bin/pbs_ds_password",
	/* 43 */ "bin/pbs_dataservice"
};

static char exsbin[][80] = {
	/* 00 */ "sbin/pbs-report",
	/* 01 */ "sbin/pbs_demux",
	/* 02 */ "sbin/pbs_idled",
	/* 03 */ "sbin/pbs_iff",
	/* 04 */ "sbin/pbs_mom",
	/* 05 */ "XXX",				/* slot available for use */
	/* 06 */ "XXX",				/* slot available for use */
	/* 07 */ "sbin/pbs_rcp",
	/* 08 */ "sbin/pbs_sched",
	/* 09 */ "sbin/pbs_server",
	/* 10 */ "sbin/pbsfs",
	/* 11 */ "sbin/pbs_probe",
	/* 12 */ "sbin/pbs_upgrade_job"
};

static char exetc[][80] = {
	/* 00 */ "etc/modulefile",
	/* 01 */ "etc/pbs_dedicated",
	/* 02 */ "etc/pbs_habitat",
	/* 03 */ "etc/pbs_holidays",
	/* 04 */ "etc/pbs_init.d",
	/* 05 */ "etc/pbs_postinstall",
	/* 06 */ "etc/pbs_resource_group",
	/* 07 */ "etc/pbs_sched_config",
	/* 08 */ "etc/pbs_db_utility",
	/* 09 */ "etc/pbs_topologyinfo"
};

static char exinc[][80] = {
	/* 00 */ "include/pbs_error.h",
	/* 01 */ "include/pbs_ifl.h",
	/* 02 */ "include/rm.h",
	/* 03 */ "include/tm.h",
	/* 04 */ "include/tm_.h"
};

static char exlib[][80] = {
	/* 00 */ "lib/libattr.a",
	/* 01 */ "SLOT_AVAILABLE",
	/* 02 */ "lib/liblog.a",
	/* 03 */ "lib/libnet.a",
	/* 04 */ "lib/libpbs.a",
	/* 05 */ "lib/libsite.a",
	/* 06 */ "lib/pbs_sched.a",
	/* 07 */ "lib/pm",
	/* 08 */ "lib/pm/PBS.pm",
	/* 09 */ "lib/MPI",
	/* 10 */ "lib/MPI/sgiMPI.awk",
	/* 11 */ "lib/MPI/pbsrun.ch_gm.init.in",
	/* 12 */ "lib/MPI/pbsrun.ch_mx.init.in",
	/* 13 */ "lib/MPI/pbsrun.gm_mpd.init.in",
	/* 14 */ "lib/MPI/pbsrun.mx_mpd.init.in",
	/* 15 */ "lib/MPI/pbsrun.mpich2.init.in",
	/* 16 */ "lib/MPI/pbsrun.intelmpi.init.in",
	/* 17 */ "SLOT_AVAILABLE",
	/* 18 */ "lib/python",
	/* 19 */ "lib/python/altair",
	/* 20 */ "lib/python/altair/pbs",
	/* 21 */ "lib/python/altair/pbs/__pycache__",
	/* 22 */ "lib/python/altair/pbs/__pycache__/__init__.cpython-3?.pyc",
	/* 23 */ "lib/python/altair/pbs/__init__.py",
	/* 24 */ "lib/python/altair/pbs/v1",
	/* 25 */ "lib/python/altair/pbs/v1/__pycache__",
	/* 26 */ "lib/python/altair/pbs/v1/__pycache__/__init__.cpython-3?.pyc",
	/* 27 */ "lib/python/altair/pbs/v1/__init__.py",
	/* 28 */ "lib/python/altair/pbs/v1/_export_types.py",
	/* 29 */ "lib/python/altair/pbs/v1/_attr_types.py",
	/* 30 */ "lib/python/altair/pbs/v1/__pycache__/_attr_types.cpython-3?.pyc",
	/* 31 */ "lib/python/altair/pbs/v1/_base_types.py",
	/* 32 */ "lib/python/altair/pbs/v1/__pycache__/_base_types.cpython-3?.pyc",
	/* 33 */ "lib/python/altair/pbs/v1/_exc_types.py",
	/* 34 */ "lib/python/altair/pbs/v1/__pycache__/_exc_types.cpython-3?.pyc",
	/* 35 */ "lib/python/altair/pbs/v1/__pycache__/_export_types.cpython-3?.pyc",
	/* 36 */ "lib/python/altair/pbs/v1/_svr_types.py",
	/* 37 */ "lib/python/altair/pbs/v1/__pycache__/_svr_types.cpython-3?.pyc",
};

#if 0
static char exec_man1[] = "man/man1";
static char exec_man3[] = "man/man3";
static char exec_man7[] = "man/man7";
static char exec_man8[] = "man/man8";
#endif

static char exman1[][80] = {
	/* 00 */ "man/man1",
	/* 01 */ "man/man1/pbs_python.1B",
	/* 02 */ "man/man1/pbs_rdel.1B",
	/* 03 */ "man/man1/pbs_rstat.1B",
	/* 04 */ "man/man1/pbs_rsub.1B",
	/* 05 */ "man/man1/pbsdsh.1B",
	/* 06 */ "man/man1/qalter.1B",
	/* 07 */ "man/man1/qdel.1B",
	/* 08 */ "man/man1/qhold.1B",
	/* 09 */ "man/man1/qmove.1B",
	/* 10 */ "man/man1/qmsg.1B",
	/* 11 */ "man/man1/qorder.1B",
	/* 12 */ "man/man1/qrerun.1B",
	/* 13 */ "man/man1/qrls.1B",
	/* 14 */ "man/man1/qselect.1B",
	/* 15 */ "man/man1/qsig.1B",
	/* 16 */ "man/man1/qstat.1B",
	/* 17 */ "man/man1/qsub.1B"
};

static char exman3[][80] = {
	/* 00 */ "man/man3",
	/* 01 */ "man/man3/pbs_alterjob.3B",
	/* 02 */ "man/man3/pbs_connect.3B",
	/* 03 */ "man/man3/pbs_default.3B",
	/* 04 */ "man/man3/pbs_deljob.3B",
	/* 05 */ "man/man3/pbs_disconnect.3B",
	/* 06 */ "man/man3/pbs_geterrmsg.3B",
	/* 07 */ "man/man3/pbs_holdjob.3B",
	/* 08 */ "man/man3/pbs_manager.3B",
	/* 09 */ "man/man3/pbs_movejob.3B",
	/* 10 */ "man/man3/pbs_msgjob.3B",
	/* 11 */ "man/man3/pbs_orderjob.3B",
	/* 12 */ "man/man3/pbs_rerunjob.3B",
	/* 13 */ "man/man3/pbs_statsched.3B",
	/* 14 */ "man/man3/pbs_rescreserve.3B",
	/* 15 */ "man/man3/pbs_rlsjob.3B",
	/* 16 */ "man/man3/pbs_runjob.3B",
	/* 17 */ "man/man3/pbs_selectjob.3B",
	/* 18 */ "man/man3/pbs_sigjob.3B",
	/* 19 */ "man/man3/pbs_stagein.3B",
	/* 20 */ "man/man3/pbs_statjob.3B",
	/* 21 */ "man/man3/pbs_statnode.3B",
	/* 22 */ "man/man3/pbs_statque.3B",
	/* 23 */ "man/man3/pbs_statserver.3B",
	/* 24 */ "man/man3/pbs_submit.3B",
	/* 25 */ "man/man3/pbs_terminate.3B",
	/* 26 */ "man/man3/tm.3",
	/* 27 */ "man/man3/pbs_tclapi.3B",
	/* 28 */ "man/man3/pbs_delresv.3B",
	/* 29 */ "man/man3/pbs_locjob.3B",
	/* 30 */ "man/man3/pbs_selstat.3B",
	/* 31 */ "man/man3/pbs_statresv.3B",
	/* 32 */ "man/man3/pbs_statfree.3B"
};

static char exman7[][80] = {
	/* 00 */ "man/man7",
	/* 01 */ "man/man7/pbs_job_attributes.7B",
	/* 02 */ "man/man7/pbs_node_attributes.7B",
	/* 03 */ "man/man7/pbs_queue_attributes.7B",
	/* 04 */ "man/man7/pbs_resources.7B",
	/* 05 */ "man/man7/pbs_resv_attributes.7B",
	/* 06 */ "man/man7/pbs_server_attributes.7B",
	/* 07 */ "man/man7/pbs_sched_attributes.7B",
	/* 08 */ "man/man7/pbs_professional.7B"
};

static char exman8[][80] = {
	/* 00 */ "man/man8",
	/* 01 */ "man/man8/pbs_idled.8B",
	/* 02 */ "man/man8/pbs_mom.8B",
	/* 03 */ "man/man8/pbs_sched.8B",
	/* 04 */ "man/man8/pbs_server.8B",
	/* 05 */ "man/man8/pbsfs.8B",
	/* 06 */ "man/man8/pbsnodes.8B",
	/* 07 */ "man/man8/qdisable.8B",
	/* 08 */ "man/man8/qenable.8B",
	/* 09 */ "man/man8/qmgr.8B",
	/* 10 */ "man/man8/qrun.8B",
	/* 11 */ "man/man8/qstart.8B",
	/* 12 */ "man/man8/qstop.8B",
	/* 13 */ "man/man8/qterm.8B",
	/* 14 */ "man/man8/pbs_lamboot.8B",
	/* 15 */ "man/man8/pbs_mpilam.8B",
	/* 16 */ "man/man8/pbs_mpirun.8B",
	/* 17 */ "man/man8/pbs_attach.8B",
	/* 18 */ "man/man8/pbs_mkdirs.8B",
	/* 19 */ "man/man8/pbs_hostn.8B",
	/* 20 */ "man/man8/pbs_probe.8B",
	/* 21 */ "man/man8/pbs-report.8B",
	/* 22 */ "man/man8/pbs_tclsh.8B",
	/* 23 */ "man/man8/pbs_tmrsh.8B",
	/* 24 */ "man/man8/pbs_wish.8B",
	/* 25 */ "man/man8/printjob.8B",
	/* 26 */ "man/man8/pbs.8B",
	/* 27 */ "man/man8/pbs_interactive.8B"
};

static char extcltk[][80] = {
	/* 0 */ "tcltk/bin",
	/* 1 */ "tcltk/include",
	/* 2 */ "tcltk/lib",
	/* 3 */ "tcltk/license.terms"
};

static char expython[][80] = {
	/* 0 */ "python/bin",
	/* 1 */ "python/include",
	/* 2 */ "python/lib",
	/* 3 */ "python/man",
	/* 4 */ "python/python.changes.txt",
	/* 5 */ "python/bin/python"
};

static char expgsql[][80] = {
	/* 0 */ "pgsql/bin",
	/* 1 */ "pgsql/include",
	/* 2 */ "pgsql/lib",
	/* 3 */ "pgsql/share"
};

/* -------- global static PBS variables -------- */

ADJ dflt_modeadjustments = { S_IFDIR | S_IXUSR | S_IXGRP | S_IXOTH, S_IFREG };

enum fixcodes	{ FIX_none, FIX_po };
enum pbsdirtype { PBS_niltype, PBS_logsdir, PBS_acctdir,
	PBS_spooldir, PBS_jobsdir,
	PBS_usersdir,
	PBS_hooksdir, PBS_hookswdir };


enum pbs_mpugs { PBS_conf, PBS_home, PBS_exec, PBS_last };
char	*origin_names[] = {"PBS CONF FILE", "PBS HOME", "PBS EXEC"};

/*
 * The following definitions simplify setting bit field codes
 */

#define C000	{0, 0, 0}		/* no fix,    Req'd, !ckfull */
#define C010	{0, 1, 0}		/* no fix,    noReq, !ckfull */
#define C100	{1, 0, 0}		/* fix perms, Req'd, !ckfull */
#define C110	{1, 1, 0}		/* fix perms, noReq, !ckfull */
#define C111	{1, 1, 1}		/* fix perms, noReq,  ckfull */
#define C200	{2, 0, 0}		/* fix exist, Req'd, !ckfull */
#define C201	{2, 0, 1}		/* fix exist, Req'd,  ckfull */

/*
 * MPUG arrays and mask to use with MPUG's "notReq" member
 */

/*
 * variable records which bits in an MPUG's "notReq" member need be considered
 *	notbits starts as 0x1
 *	For execution only (Mom) set to 0x5
 *	For commands only	 set to 0x3
 *
 *	"notReq" is set to
 *	0 - required for all
 *	1 - not required ever
 *	2 - not required for commands only install
 *	4 - not required for execuition only (Mom) install
 *
 * The two are "and"ed together.  If the result is 0 the file should be there,
 * if the result is non-zero, the file need not be present.
 */
static int	notbits = 0x1;


static MPUG	pbs_mpugs[] = {
	/*
	 * infrastructure data associated with PBS origins
	 * dir, chkfull, required and disallowed modes, pointer
	 * to "valid users, valid groups", path, realpath
	 */
	{1, 0, 0, frwrr,  xsgswxowx, &dflt_ext_ug, NULL, NULL},
	{1, 0, 1, drwxrxrx,   tgwow, &dflt_ext_ug, NULL, NULL},
	{1, 0, 1, drwxrxrx,   tgwow, &dflt_ext_ug, NULL, NULL} };

enum exec_mpugs { EXEC_exec, EXEC_bin, EXEC_sbin,  EXEC_etc, EXEC_include,
	EXEC_lib, EXEC_man, EXEC_man1, EXEC_man3, EXEC_man7,
	EXEC_man8, EXEC_tcltk, EXEC_python, EXEC_pgsql, EXEC_last };

char *exec_mpug_set[EXEC_last] = {"exec", "bin", "sbin", "etc", "include",
	"lib", "man", "man1", "man3", "man7",
	"man8", "tcltk", "python", "pgsql"};

int  exec_sizes[EXEC_last];

static MPUG	 exec_mpugs[] = {
	/*
	 * infrastructure data associated with PBS execution -
	 * bin, sbin, etc, include, lib, man, tcltk, python, pgsql
	 */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[0], NULL}, /* bin */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[1], NULL}, /* etc */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[2], NULL}, /* include */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[3], NULL}, /* lib */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[4], NULL}, /* man */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[5], NULL}, /* sbin */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[6], NULL}, /* tcltk */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[7], NULL}, /* python */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[8], NULL}  /* pgsql */
};



static MPUG	bin_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/bin
	 */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[0],    NULL},
	{1, 6, 0,   frwxgo,   sgsrwxorwx, &dflt_pbs_ug, exbin[ 0], NULL }, /* pbs_topologyinfo */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 1], NULL }, /* pbs_hostn */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 2], NULL }, /* pbs_rdel */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 3], NULL }, /* pbs_rstat */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 4], NULL }, /* pbs_rsub */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 5], NULL }, /* pbs_tclsh */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 6], NULL }, /* pbs_wish */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 7], NULL }, /* pbsdsh */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 8], NULL }, /* pbsnodes */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[ 9], NULL }, /* printjob */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[10], NULL }, /* qalter */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[11], NULL }, /* qdel */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[12], NULL }, /* qdisable */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[13], NULL }, /* qenable */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[14], NULL }, /* qhold */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[15], NULL }, /* qmgr */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[16], NULL }, /* qmove */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[17], NULL }, /* qmsg */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[18], NULL }, /* qorder */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[19], NULL }, /* qrerun */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[20], NULL }, /* qrls */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[21], NULL }, /* qrun */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[22], NULL }, /* qselect */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[23], NULL }, /* qsig */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[24], NULL }, /* qstart */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[25], NULL }, /* qstat */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[26], NULL }, /* qstop */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[27], NULL }, /* qsub */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[28], NULL }, /* qterm */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[29], NULL }, /* tracejob */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[30], NULL }, /* pbs_lamboot */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[31], NULL }, /* pbs_mpilam */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[32], NULL }, /* pbs_mpirun */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[33], NULL }, /* pbs_mpihp */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[34], NULL }, /* pbs_attach */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[35], NULL }, /* pbs_remsh */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[36], NULL }, /* pbs_tmrsh */
	{1, 2, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[37], NULL }, /* mpiexec */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[38], NULL }, /* pbsrun */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[39], NULL }, /* pbsrun_wrap */
	{1, 1, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[40], NULL }, /* pbsrun_unwrap */
	{1, 2, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exbin[41], NULL },  /* pbs_python */
	{1, 6, 0,   frwxgo,     tgrwxorwx, &dflt_pbs_ug, exbin[42], NULL },  /* pbs_ds_password */
	{1, 6, 0,   frwxgo,     tgrwxorwx, &dflt_pbs_ug, exbin[43], NULL }  /* pbs_dataservice */
};

static MPUG	sbin_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/sbin
	 */
	{1, 0, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, exec[5], NULL},
	{1, 2, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exsbin[ 0], NULL }, /* pbs-report */
	{1, 2, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exsbin[ 1], NULL }, /* pbs_demux */
	{1, 2, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exsbin[ 2], NULL }, /* pbs_idled */
	{1, 0, 0,  fsrwxrxrx,      gswow, &dflt_pbs_ug, exsbin[ 3], NULL }, /* pbs_iff */
	{1, 2, 0,     frwxgo, sgsrwxorwx, &dflt_pbs_ug, exsbin[ 4], NULL }, /* pbs_mom */
	{1, 1, 0,     frwxgo, sgsrwxorwx, &dflt_pbs_ug, exsbin[ 5], NULL }, /* slot available for use */
	{1, 1, 0,     frwxgo, sgsrwxorwx, &dflt_pbs_ug, exsbin[ 6], NULL }, /* slot available for use */
	{1, 2, 0,  fsrwxrxrx,      gswow, &dflt_pbs_ug, exsbin[ 7], NULL }, /* pbs_rcp */
	{1, 6, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exsbin[ 8], NULL }, /* pbs_sched */
	{1, 6, 0,     frwxgo, sgsrwxorwx, &dflt_pbs_ug, exsbin[ 9], NULL }, /* pbs_server */
	{1, 6, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exsbin[10], NULL }, /* pbsfs */
	{1, 0, 0,   frwxrxrx,     sgswow, &dflt_pbs_ug, exsbin[11], NULL }, /* pbs_probe */
	{1, 2, 0,     frwxgo, sgsrwxorwx, &dflt_pbs_ug, exsbin[12], NULL } /* pbs_upgrade_job */
};


static MPUG	etc_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/etc
	 */
	{1, 0, 0, drwxrxrx,      tgwow, &dflt_pbs_ug,  exec[ 1], NULL },
	{1, 0, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exetc[ 0], NULL }, /* modulefile */
	{1, 6, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exetc[ 1], NULL }, /* pbs_dedicated */
	{1, 2, 0,   frwxgo, sgsrwxorwx, &dflt_pbs_ug, exetc[ 2], NULL }, /* pbs_habitat */
	{1, 6, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exetc[ 3], NULL }, /* pbs_holidays */
	{1, 2, 0,   frwxgo, sgsrwxorwx, &dflt_pbs_ug, exetc[ 4], NULL }, /* pbs_init.d */
	{1, 0, 0,   frwxgo, sgsrwxorwx, &dflt_pbs_ug, exetc[ 5], NULL }, /* pbs_postinstall */
	{1, 6, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exetc[ 6], NULL }, /* pbs_resource_group */
	{1, 6, 0,   frgror,   sgswxowx, &dflt_pbs_ug, exetc[ 7], NULL }, /* pbs_sched_config */
	{1, 6, 0,   frwxgo,  tgrwxorwx, &dflt_pbs_ug, exetc[ 8], NULL }, /* pbs_db_utility */
	{1, 6, 0,   frwxgo, sgsrwxorwx, &dflt_pbs_ug, exetc[ 9], NULL }  /* pbs_topologyinfo */
};


static MPUG	include_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/include
	 */
	{1, 1, 0,   drwxrxrx,    tgwow, &dflt_pbs_ug, exec[2], NULL},
	{1, 1, 0,     frgror,   sgswxowx, &dflt_pbs_ug, exinc[0], NULL }, /* pbs_error.h */
	{1, 1, 0,     frgror,   sgswxowx, &dflt_pbs_ug, exinc[1], NULL }, /* pbs_ifl.h */
	{1, 1, 0,     frgror,   sgswxowx, &dflt_pbs_ug, exinc[2], NULL }, /* rm.h */
	{1, 1, 0,     frgror,   sgswxowx, &dflt_pbs_ug, exinc[3], NULL }, /* tm.h */
	{1, 1, 0,     frgror,   sgswxowx, &dflt_pbs_ug, exinc[4], NULL } }; /* tm_.h */


static MPUG	lib_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/lib
	 */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[3],    NULL},
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 0], NULL }, /* libattr.a */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 1], NULL }, /* SLOT_AVAILABLE */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 2], NULL }, /* liblog.a */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 3], NULL }, /* libnet.a */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 4], NULL }, /* libpbs.a */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 5], NULL }, /* libsite.a */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 6], NULL }, /* pbs_sched.a */
	{1, 2, 0,   drwxrxrx,    tgwow, &dflt_pbs_ug, exlib[ 7], NULL }, /* pm */
	{1, 0, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[ 8], NULL }, /* PBS.pm */
	{1, 2, 0,   drwxrxrx,    tgwow, &dflt_pbs_ug, exlib[ 9], NULL}, /* MPI */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[10], NULL}, /* sgiMPI.awk */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[11], NULL}, /* pbsrun.ch_gm.init.in */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[12], NULL}, /* pbsrun.ch_mx.init.in */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[13], NULL}, /* pbsrun.gm_mpd.init.in */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[14], NULL}, /* pbsrun.mx_mpd.init.in */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[15], NULL}, /* pbsrun.mpich2.init.in */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[16], NULL},  /* pbsrun.intelmpi.init.in */
	{1, 1, 0,    frwrr,  xsgswxowx, &dflt_pbs_ug, exlib[17], NULL},  /* SLOT_AVAILABLE */
	{1, 6, 0,    drwxrxrx,   tgwow, &dflt_pbs_ug, exlib[18], NULL},  /* lib/python */
	{1, 2, 0,    drwxrxrx,   tgwow, &dflt_pbs_ug, exlib[19], NULL},  /* lib/python/altair */
	{1, 2, 0,    drwxrxrx,   tgwow, &dflt_pbs_ug, exlib[20], NULL},  /* lib/python/altair/pbs */
	{1, 2, 0,    drwxrxrx,   tgwow, &dflt_pbs_ug, exlib[21], NULL},  /* lib/python/altair/pbs/__pycache__ */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[22], NULL},  /* lib/python/altair/pbs/__pycache__
	/__init__.cpython-3?.pyc */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[23], NULL},  /* lib/python/altair/pbs/__init__.py */
	{1, 2, 0,    drwxrxrx,   tgwow, &dflt_pbs_ug, exlib[24], NULL},  /* lib/python/altair/pbs/v1 */
	{1, 2, 0,    drwxrxrx,   tgwow, &dflt_pbs_ug, exlib[25], NULL},  /* lib/python/altair/pbs/v1/__pycache__ */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[26], NULL},  /* lib/python/altair/pbs/v1/__pycache__
	/__init__.cpython-3?.pyc */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[27], NULL},  /* lib/python/altair/pbs/v1/__init__.py */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[28], NULL},  /* lib/python/altair/pbs/v1/_export_types.py */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[29], NULL},  /* lib/python/altair/pbs/v1/_attr_types.py */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[30], NULL},  /* lib/python/altair/pbs/v1/__pycache__
	/_attr_types.cpython-3?.pyc */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[31], NULL},  /* lib/python/altair/pbs/v1/_base_types.py */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[32], NULL},  /* lib/python/altair/pbs/v1/__pycache__
	/_base_types.cpython-3?.pyc */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[33], NULL},  /* lib/python/altair/pbs/v1/_exc_types.py */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[34], NULL},  /* lib/python/altair/pbs/v1/__pycache__
	/_exc_types.cpython-3?.pyc */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[35], NULL},  /* lib/python/altair/pbs/v1/__pycache__
	/_export_types.cpython-3?pyc */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[36], NULL},  /* lib/python/altair/pbs/v1/_svr_types.py */
	{1, 2, 0,    frgror,  sgswxowx, &dflt_pbs_ug, exlib[37], NULL},  /* lib/python/altair/pbs/v1/__pycache__
	/_svr_types.cpython-3?.pyc */
};

static MPUG	man_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/man
	 */
	{1, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, exec[4],    NULL},

	/*
	 * infrastructure data associated with PBS_EXEC/man/man1
	 */
	{1, 0, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, exman1[ 0], NULL }, /* man1 */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 1], NULL }, /* pbs_python.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 2], NULL }, /* pbs_rdel.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 3], NULL }, /* pbs_rstat.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 4], NULL }, /* pbs_rsub.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 5], NULL }, /* pbsdsh.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 6], NULL }, /* qalter.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 7], NULL }, /* qdel.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 8], NULL }, /* qhold.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[ 9], NULL }, /* qmove.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[10], NULL }, /* qmsg.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[11], NULL }, /* qorder.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[12], NULL }, /* qrerun.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[13], NULL }, /* qrls.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[14], NULL }, /* qselect.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[15], NULL }, /* qsig.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[16], NULL }, /* qstat.1B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman1[17], NULL }, /* qsub.1B */

	/*
	 * infrastructure data associated with PBS_EXEC/man/man3
	 */
	{1, 0, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, exman3[ 0], NULL }, /* man3 */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 1], NULL }, /* pbs_alterjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 2], NULL }, /* pbs_connect.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 3], NULL }, /* pbs_default.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 4], NULL }, /* pbs_deljob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 5], NULL }, /* pbs_disconnect.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 6], NULL }, /* pbs_geterrmsg.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 7], NULL }, /* pbs_holdjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 8], NULL }, /* pbs_manager.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[ 9], NULL }, /* pbs_movejob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[10], NULL }, /* pbs_msgjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[11], NULL }, /* pbs_orderjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[12], NULL }, /* pbs_rerunjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[13], NULL }, /* pbs_statsched.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[14], NULL }, /* pbs_rescreserve.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[15], NULL }, /* pbs_rlsjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[16], NULL }, /* pbs_runjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[17], NULL }, /* pbs_selectjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[18], NULL }, /* pbs_sigjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[19], NULL }, /* pbs_stagein.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[20], NULL }, /* pbs_statjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[21], NULL }, /* pbs_statnode.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[22], NULL }, /* pbs_statque.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[23], NULL }, /* pbs_statserver.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[24], NULL }, /* pbs_submit.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[25], NULL }, /* pbs_terminate.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[26], NULL }, /* tm.3 */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[27], NULL }, /* pbs_tclapi.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[28], NULL }, /* pbs_delresv.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[20], NULL }, /* pbs_locjob.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[30], NULL }, /* pbs_selstat.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[31], NULL }, /* pbs_statresv.3B */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, exman3[32], NULL }, /* pbs_statfree.3B */

	/*
	 * infrastructure data associated with PBS_EXEC/man/man7
	 */
	{1, 0, 0, drwxrxrx,  tgwow, &dflt_pbs_ug, exman7[ 0], NULL }, /* man7 */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 1], NULL }, /* pbs_job_attributes.7B */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 2], NULL }, /* pbs_node_attributes.7B */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 3], NULL }, /* pbs_queue_attributes.7B */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 4], NULL }, /* pbs_resources.7B */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 5], NULL }, /* pbs_resv_attributes.7B */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 6], NULL }, /* pbs_server_attributes.7B */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 7], NULL }, /* pbs_sched_attributes.7B */
	{1, 0, 0, frwrr, xsgswxowx, &dflt_pbs_ug, exman7[ 8], NULL }, /* pbs_professional.7B */

	/*
	 * infrastructure data associated with PBS_EXEC/man/man8
	 */
	{1, 0, 0,  drwxrxrx,      tgwow, &dflt_pbs_ug, exman8[ 0], NULL }, /* man8 */
	{1, 2, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 1], NULL }, /* pbs_idled.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 2], NULL }, /* pbs_mom.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 3], NULL }, /* pbs_sched.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 4], NULL }, /* pbs_server.8B */
	{1, 2, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 5], NULL }, /* pbsfs.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 6], NULL }, /* pbsnodes.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 7], NULL }, /* qdisable.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 8], NULL }, /* qenable.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[ 9], NULL }, /* qmgr.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[10], NULL }, /* qrun.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[11], NULL }, /* qstart.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[12], NULL }, /* qstop.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[13], NULL }, /* qterm.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[14], NULL }, /* pbs_lamboot.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[15], NULL }, /* pbs_mpilam.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[16], NULL }, /* pbs_mpirun.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[17], NULL }, /* pbs_attach.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[18], NULL }, /* pbs_mkdirs.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[19], NULL }, /* pbs_hostn.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[20], NULL }, /* pbs_probe.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[21], NULL }, /* pbs-report.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[22], NULL }, /* pbs_tclsh.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[23], NULL }, /* pbs_tmrsh.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[24], NULL }, /* pbs_wish.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[25], NULL }, /* printjob.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[26], NULL }, /* pbs.8B */
	{1, 0, 0,     frwrr,  xsgswxowx, &dflt_pbs_ug, exman8[27], NULL } }; /* pbs_interactive.8B */

static MPUG	tcltk_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/tcltk
	 */
	{1, 0, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, exec[6],  NULL},
	{1, 0, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, extcltk[0], NULL }, /* tcltk/bin */
	{1, 0, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, extcltk[1], NULL }, /* tcltk/include */
	{1, 0, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, extcltk[2], NULL }, /* tcltk/lib */
	{1, 0, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, extcltk[3], NULL } }; /* tcltk/license.terms */

static MPUG	python_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/python
	 */
	{1, 2, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, exec[7],  NULL},
	{1, 2, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expython[0], NULL }, /* python/bin */
	{1, 2, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expython[1], NULL }, /* python/include */
	{1, 2, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expython[2], NULL }, /* python/lib */
	{1, 2, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expython[3], NULL }, /* python/man */
	{1, 2, 0,      frwrr,  xsgswxowx, &dflt_pbs_ug, expython[4], NULL }, /* python/python.changes.txt */
	{1, 2, 0,      frwxrxrx,  sgswow, &dflt_pbs_ug, expython[5], NULL } }; /* python/bin/python */

static MPUG	pgsql_mpugs[] = {
	/*
	 * infrastructure data associated with PBS_EXEC/pgsql
	 */
	{1, 6, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, exec[8],  NULL},
	{1, 6, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expgsql[0], NULL }, /* pgsql/bin */
	{1, 6, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expgsql[1], NULL }, /* pgsql/include */
	{1, 6, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expgsql[2], NULL }, /* pgsql/lib */
	{1, 6, 0,   drwxrxrx,      tgwow, &dflt_pbs_ug, expgsql[3], NULL } }; /* pgsql/share */


enum pbshome_mpugs { PH_server, PH_mom, PH_sched, PH_last };

int  home_sizes[PH_last];
char *home_mpug_set[PH_last] = {"pbs_server", "pbs_mom", "pbs_sched"};

enum svr_mpugs { SVR_logs,  SVR_spool, SVR_priv,  SVR_acct,
	SVR_jobs,
	SVR_users, SVR_hooks, SVR_hookswdir, SVR_last };

static MPUG	 svr_mpugs[] = {
	/*
	 * infrastructure data associated with server daemon
	 * home dir, chkfull, required and disallowed modes,
	 * pointer to "valid users, valid groups", path, realpath
	 */
	{2, 0, 0, drwxrxrx,  tgwow,  &dflt_pbs_ug, svrhome[ 0], NULL}, /* logs */
	{2, 0, 0, tdrwxrwxrwx,   0,  &dflt_pbs_ug, svrhome[ 1], NULL}, /* spool */
	{2, 0, 0, drwxrxo, tgworwx,  &dflt_pbs_ug, svrhome[ 2], NULL}, /* priv */
	{1, 1, 0, frwrr, xsgswxowx,  &dflt_pbs_ug, svrhome[ 3], NULL}, /* resourcedef */
	{0, 1, 0, frwgo, sgsrwxorwx, &dflt_pbs_ug, svrhome[ 4], NULL}, /* server.lock */
	{2, 0, 0, frwgo, sgsrwxorwx, &dflt_pbs_ug, svrhome[ 5], NULL}, /* tracking */
	{2, 0, 0, drwxrxrx,  tgwow,  &dflt_pbs_ug, svrhome[ 6], NULL}, /* accounting */
	{2, 0, 0, drwxrxo, tgworwx,  &dflt_pbs_ug, svrhome[ 7], NULL}, /* jobs */
	{2, 0, 0, drwxrxo, tgworwx,  &dflt_pbs_ug, svrhome[ 8], NULL}, /* users */
	{2, 0, 0, drwxrxo, tgworwx,  &dflt_pbs_ug, svrhome[ 9], NULL}, /* hooks */
	{2, 0, 0, drwxrxo, tgworwx,  &dflt_pbs_ug, svrhome[10], NULL}, /* hooks' workdir */
	{1, 0, 0, frwgo, sgsrwxorwx, &dflt_pbs_ug, svrhome[11], NULL}, /* prov_tracking */
	{1, 6, 0, frwgo, sgsrwxorwx, &dflt_pbs_ug, svrhome[12], NULL}, /* db_password */
	{1, 1, 0, frwgo, sgsrwxorwx, &dflt_pbs_ug, svrhome[13], NULL}, /* db_svrhost */
	{1, 1, 0, frwgo, sgsrwxorwx, &dflt_pbs_ug, svrhome[14], NULL}, /* db_svrhost.new */
	{1, 6, 0, frwgo, sgsrwxorwx, &dflt_pbs_ug, svrhome[15], NULL}, /* svrlive */
	{1, 6, 0, drwxgo, tgworwx, &dflt_pbs_data, svrhome[16], NULL}  /* datastore (must be last) */
};


enum mom_mpugs { MOM_aux, MOM_checkpoint, MOM_logs, MOM_priv,
	MOM_jobs, MOM_spool, MOM_undelivered, MOM_last };

static MPUG	mom_mpugs[] = {
	/*
	 * infrastructure data associated with mom daemon
	 * dir, chkfull, required and disallowed modes, pointer
	 * to "valid users, valid groups", path, realpath
	 */
	{2, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, momhome[0], NULL}, /* aux */
	{2, 0, 0, drwxgo,  tgrwxorwx, &dflt_pbs_ug, momhome[1], NULL}, /* checkpoint */
	{2, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_ug, momhome[2], NULL}, /* mom_logs */
	{2, 0, 0, drwxrxx,    tgworw, &dflt_pbs_ug, momhome[3], NULL}, /* mom_priv */
	{0, 1, 0, frwrr,   xsgswxowx, &dflt_pbs_ug, momhome[4], NULL}, /* mom.lock */
	{2, 0, 0, frwrr,   xsgswxowx, &dflt_pbs_ug, momhome[5], NULL}, /* config */
	{2, 0, 0, drwxrxx,    tgworw, &dflt_pbs_ug, momhome[6], NULL}, /* jobs */
	{2, 0, 0, tdrwxrwxrwx,     0, &dflt_pbs_ug, momhome[7], NULL}, /* spool */
	{2, 0, 0, tdrwxrwxrwx,     0, &dflt_pbs_ug, momhome[8], NULL}, /* undelivered */
	{0, 1, 0, drwxgo,     tgworw, &dflt_pbs_ug, momhome[9], NULL}, /* config.d */
	{0, 1, 0, drwxgo,     tgworw, &dflt_pbs_ug, momhome[10], NULL}, /* mom_priv/hooks */
	{0, 1, 0, drwxgo,     tgworw, &dflt_pbs_ug, momhome[11], NULL}};/* mom_priv/hooks/tmp */



enum sched_mpugs { SCHED_logs, SCHED_priv, SCHED_last };

static MPUG	sched_mpugs[] = {
	/*
	 * infrastructure data associated with sched daemon
	 * dir, chkfull, required and disallowed modes, pointer
	 * to "valid users, valid groups", path, realpath
	 */
	{2, 0, 0, drwxrxrx,    tgwow, &dflt_pbs_service, schedhome[0], NULL}, /* sched_logs */
	{2, 0, 0, drwxrxo,   tgworwx, &dflt_pbs_service, schedhome[1], NULL}, /* sched_priv */
	{2, 0, 0, frwrr,   xsgswxowx, &dflt_pbs_service, schedhome[2], NULL}, /* dedicated_time */
	{2, 0, 0, frwrr,   xsgswxowx, &dflt_pbs_service, schedhome[3], NULL}, /* holidays */
	{2, 0, 0, frwrr,   xsgswxowx, &dflt_pbs_service, schedhome[4], NULL}, /* sched_config */
	{2, 0, 0, frwrr,   xsgswxowx, &dflt_pbs_service, schedhome[5], NULL}, /* resource_group */
	{0, 1, 0, frwrr,   xsgswxowx, &dflt_pbs_service, schedhome[6], NULL}, /* sched.lock */
	{2, 1, 0, frwrr,   xsgswxowx, &dflt_pbs_service, schedhome[7], NULL} }; /* sched_out */




enum  msg_sources { SRC_pri, SRC_home, SRC_exec, SRC_last, SRC_none };
enum  msg_categories { MSG_md, MSG_mf, MSG_po, MSG_unr, MSG_real, MSG_pri, MSG_oth, MSG_last, MSG_none };
/*
 * MSG_md   - missing directories
 * MSG_mf   - missing files
 * MSG_po   - permission/owner errors
 * MSG_unr  - unrecognized directory entry
 * MSG_pri  - primary data
 * MSG_real - real path problem
 * MSG_oth  - other problems
 * MSG_last - last enumeration value
 */

/*
 * The structure below is used in mechanizing storage of messages in
 * memory for subsequent output.  Things are done this in order that
 * there be more flexibility/control over how information flowing on
 * stdout is organized.
 *
 * For each "source" of output messages, there will be an instance of
 * PROBEMSGS data structure - i.e.,
 * there will be an instance for messages relating to the PRIMARY data,
 * one relating to messages associated with PBS HOME data, and one
 * relating to messages associated with PBS EXEC data.
 */

typedef struct	probemsgs {
	/*
	 * each pointer in mtbls will point to an array of
	 * pointers to messages.  The message pointers in each
	 * array are pointing to output messages from pbs_probe that
	 * belong to the same "category" of message - e.g. messages
	 * about a file being "missing". (see enum msg_categories)
	 *
	 * Structure member "idx" is an array of index values, one for
	 * each array of message pointers - e.g. idx[MSG_mf] holds the
	 * index of the last "missing file" message placed in the array.
	 */
	char **mtbls[MSG_last];
	int  idx[MSG_last];
}  PROBEMSGS;


typedef struct	infrastruct {

	int	mode;		/* pbs_probe "mode" */
	char*	phost;		/* host running pbs_probe */

	/* PRIMARY related MPUGS and their sources */

	PRIMARY	pri;

	/* pointers to PBS HOME related MPUG arrays */

	MPUG	*home[PH_last];

	/* pointers to PBS EXEC related MPUG arrays */

	MPUG	*exec[EXEC_last];

	PROBEMSGS *msgs[SRC_last];

	struct utsdata	utsd;
	struct statdata statd;
} INFRA;

static void	am_i_authorized(void);
static void	infrastruct_params(struct infrastruct *, int);
static void	adjust_for_os(struct infrastruct *pinf);
static void	print_infrastruct(struct infrastruct *);
static void	title_string(enum code_title, int, INFRA *);
static void	print_problems(INFRA *);
static void	msg_table_set_defaults(INFRA *, int, int);
static int	put_msg_in_table(INFRA *, int, int, char*);
static int	get_primary_values(struct infrastruct *);
static int	get_realpath_values(struct infrastruct *);
static int	is_parent_rpathnull(char *, MPUG **, int, int *);
#if 0
static int	is_suffix_ok(char *, char *);
static int	inspect_dir_entries(struct infrastruct *);
static const	char *which_suffixset(MPUG *);
static MPUG	**which_knwn_mpugs(MPUG *, MPUG *[], int *, int asz);
static MPUG	**which_Knwn_mpugs(MPUG *, MPUG *, int);
static void	chk_entries(MPUG *, MPUG **);
static void	pbs_dirtype(int *, MPUG *);
static int	non_db_resident(MPUG*, char*, int, char *entryname);
static int	is_a_numericname(char *);
#endif
static int	check_paths(struct infrastruct *);
static int	check_owner_modes(char *, MPUG *, int);
static int	mbits_and_owner(struct stat *, MPUG *, int);
static char	*perm_string(mode_t);

static const char *perm_owner_msg(struct stat *, MPUG *, ADJ *, int);
static const char *owner_string(struct stat *, MPUG *, int);

static int	process_ret_code(enum func_names, int, struct infrastruct *);
static int	conf4primary(FILE *, struct infrastruct *);
static int	env4primary(struct infrastruct *);
static void     fix(int, int, int, MPUG *, ADJ *, struct stat *, int);
static void     fix_perm_owner(MPUG *, struct stat *, ADJ *);

/* Variables visible to all functions in this file */

static int   flag_verbose;
static	int  mode = 0;
static	int  max_level = FIX_po;
int	nonlocaldata = 0;
/**
 * @Brief
 *      This is main function of pbs_probe process.
 *
 * @return	int
 * @retval	0	: On Success
 * @retval	!=0	: failure
 *
 */
int
main(int argc, char *argv[])
{
	int rc;
	int i=0;
	int err=0;
	struct infrastruct infra;

	extern int optind;

	/*the real deal or output pbs_version and exit?*/
	PRINT_VERSION_AND_EXIT(argc, argv);

	/* If not authorized, don't proceed any further */
	am_i_authorized();

	/*
	 * Check that this invocation of pbs_probe is properly formed
	 * compute the "run mode"
	 */

	while (err == 0 && (i = getopt(argc, argv, "fcv")) != EOF) {

		switch (i) {

				/*other two "recognized" modes*/

			case 'v':
				flag_verbose = 1;
				break;

			case 'f':
				if (mode)
					/*
				 *program allows only one mode at a time, so if
				 *already has a value that is bad
				 */
					err = 1;
				else
					mode = i;
				break;

				/*
				 * Currently, only options are: "none", f, v
				 * Also, for any non-recognized option getopt outputs
				 * an error message to stderr.
				 */

			case 'c':
			default: err = 1;
		}
	}


	if (err == 0 && mode != 'c' && argv[optind] == NULL) {

		/*
		 * Determine name of this host, pbs.conf pathname,
		 * and values for certain primary parameters
		 */

		infrastruct_params(&infra, mode);
		msg_table_set_defaults(&infra, SRC_pri, MSG_oth);

		/*
		 * generate for each infrastructure file/directory
		 * the canonicalized, absolute pathname
		 */

		if ((rc = get_realpath_values(&infra)))
			exit(rc);

		/*
		 * check modes/ownership on those database paths which
		 * successfully mapped to a realpath
		 */

		check_paths(&infra);

		/*
		 * For existing infrastucture directories, inspect their
		 * entries for validity:
		 *   - valid name  (name in database, other general criteria)
		 *   - valid modes (modes from database or suitable default)
		 *
		 * example:
		 * checking content of server's "jobs" directory by checking
		 * entry's suffix and mode
		 */

#if 0
		inspect_dir_entries(&infra);
#endif
		print_problems(&infra);

	} else {

		/*
		 * err == 0 || (for the time being) mode == 'c'
		 * output typical kind of usage message
		 */
		title_string(TC_use, mode, &infra);
		exit(1);
	}

	if (flag_verbose)
		print_infrastruct(&infra);
	exit(0);
}
/**
 * @brief
 * 		Check whether user is authorized to use pbs_probe.
 *
 * @par MT-safe:	No
 */
static void
am_i_authorized(void)
{
	static char allow[] = "root";
	uid_t getuid(void);
	struct passwd *ppwd = getpwuid(getuid()) ;

	if (ppwd && strcmp(ppwd->pw_name, allow) == 0)
		return;

	/*problem encountered*/

	if (ppwd)
		fprintf(stderr, "User %s not authorized to use pbs_probe\n", ppwd->pw_name);
	else
		fprintf(stderr, "Problem checking user authorization for utility\n");
	exit(1);
}
/**
 * @brief
 * 		configure values for various infrastructure parameters.
 *
 * @param[out]	pinf	-	 structpointer to infrastruct
 * @param[out]	mode	-	 pbs_probe "mode"
 */
static void
infrastruct_params(struct infrastruct *pinf, int mode)
{

	int	i, rc;			/* return code */
	char	hname[PBS_MAXHOSTNAME+1];

	memset((void *)pinf, 0, (size_t)sizeof(struct infrastruct));

	for (i=0; i<SRC_last; ++i) {
		pinf->msgs[i] = (PROBEMSGS *)malloc(sizeof(PROBEMSGS));
		if (pinf->msgs[i] == NULL) {
			fprintf(stderr, "pbs_probe: Out of Memory\n");
			exit(1);
		}
		memset((void *)pinf->msgs[i], 0, sizeof(PROBEMSGS));
	}

	pinf->mode = mode;
	pinf->pri.pbs_mpug = &pbs_mpugs[0];

	if (gethostname(hname, (sizeof(hname) - 1)))
		strcpy(hname, "localhost");
	pinf->phost = strdup(hname);

	if (uname(&pinf->utsd.ub) >= 0) {
		pinf->utsd.populated = 1;
		adjust_for_os(pinf);
	}

	/*
	 * output a title and accompanying system information
	 */

	title_string(TC_sys, mode, pinf);

	/*
	 * determine values for the primary variables:
	 * paths - pbs_home, ps_exec,
	 * pbs_start_server, pbs_start_mom, pbs_start_sched
	 */

	if ((rc = get_primary_values(pinf)))
		if (process_ret_code(GET_PRIMARY_VALUES, rc, pinf)) {
			print_problems(pinf);
			exit(1);
		}

	if (nonlocaldata)	/* don't check datastore if it is nonlocal */
		home_sizes[PH_server] -= 1;

	/*
	 * PBS HOME:  load pointers to the various arrays of MPUG data
	 * relevant to value of PBS HOME stored in *pinf's pri element
	 */

	if (pinf->pri.started.server)
		pinf->home[PH_server] = &svr_mpugs[0];

	if (pinf->pri.started.mom)
		pinf->home[PH_mom] =    &mom_mpugs[0];

	if (pinf->pri.started.sched)
		pinf->home[PH_sched] =  &sched_mpugs[0];

	/*
	 * Record install type in the "notbits" variable
	 */

	if (pinf->pri.started.server == 0 &&
		pinf->pri.started.sched == 0  &&  pinf->pri.started.mom) {

		/* did "execution-only" install */

		notbits |= 0x4;
	}
	else if (!pinf->pri.started.server && !pinf->pri.started.sched &&
		!pinf->pri.started.mom) {
		/* did "cmds-only" install */
		notbits |= 0x2;
	}

	home_sizes[PH_server] = sizeof(svr_mpugs)/sizeof(MPUG);
	home_sizes[PH_mom] =  sizeof(mom_mpugs)/sizeof(MPUG);
	home_sizes[PH_sched] = sizeof(sched_mpugs)/sizeof(MPUG);

	/*
	 * PBS EXEC:  load pointers to the various arrays of MPUG data
	 * relevant to value of PBS EXEC stored in *pinf's pri element
	 */

	pinf->exec[EXEC_exec] =  &exec_mpugs[0]; /* make irix compiler happy */
	pinf->exec[EXEC_exec] =  NULL;
	pinf->exec[EXEC_bin] =   &bin_mpugs[0];
	pinf->exec[EXEC_sbin] =  &sbin_mpugs[0];
	pinf->exec[EXEC_etc] =   &etc_mpugs[0];
	pinf->exec[EXEC_lib] =   &lib_mpugs[0];
	pinf->exec[EXEC_man] =   &man_mpugs[0];
	pinf->exec[EXEC_man1] =  NULL;
	pinf->exec[EXEC_man3] =  NULL;
	pinf->exec[EXEC_man7] =  NULL;
	pinf->exec[EXEC_man8] =  NULL;

	pinf->exec[EXEC_tcltk] =   &tcltk_mpugs[0];
	pinf->exec[EXEC_python] =   &python_mpugs[0];
	pinf->exec[EXEC_include] = &include_mpugs[0];
	pinf->exec[EXEC_pgsql] =   &pgsql_mpugs[0];

	exec_sizes[EXEC_exec] = sizeof(exec_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_bin] =  sizeof(bin_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_sbin] = sizeof(sbin_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_etc] =  sizeof(etc_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_lib] =  sizeof(lib_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_man] =  sizeof(man_mpugs)/sizeof(MPUG);

	exec_sizes[EXEC_man1] = 0;
	exec_sizes[EXEC_man3] = 0;
	exec_sizes[EXEC_man7] = 0;
	exec_sizes[EXEC_man8] = 0;

	exec_sizes[EXEC_tcltk] =   sizeof(tcltk_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_python] =   sizeof(python_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_include] = sizeof(include_mpugs)/sizeof(MPUG);
	exec_sizes[EXEC_pgsql] =   sizeof(pgsql_mpugs)/sizeof(MPUG);
}
/**
 * @brief
 * 		adjust the infrastruct parameter values based on the os.
 *
 * @param[out]	pinf	-	 pointer to infrastruct
 */
static void
adjust_for_os(struct infrastruct *pinf)
{
	/* offset to use with specific MPUG array */

	int	ofs_bin = 1;  /* use with bin_mpugs[] */
	int	ofs_lib = 1;  /* use with lib_mpugs[] */

	if (strstr(pinf->utsd.ub.sysname, "Linux") != NULL) {

		/* Linux: pbs_lamboot, pbs_mpilam, pbs_mpirun, mpiexec, pbsrun, pbsrun_wrap, pbsrun_unwrap  */

		bin_mpugs[ofs_bin + 31].notReq &= ~(0x1);
		bin_mpugs[ofs_bin + 32].notReq &= ~(0x1);
		bin_mpugs[ofs_bin + 33].notReq &= ~(0x1);
		bin_mpugs[ofs_bin + 38].notReq &= ~(0x1);
		bin_mpugs[ofs_bin + 39].notReq &= ~(0x1);
		bin_mpugs[ofs_bin + 40].notReq &= ~(0x1);
		bin_mpugs[ofs_bin + 41].notReq &= ~(0x1);

		/* Linux + /etc/sgi-compute-node_release => SGI ICE	*/
		if (access("/etc/sgi-compute-node-release", R_OK) == 0) {
			lib_mpugs[ofs_lib + 23].notReq = 0;    /* sgiMPI.awk       */
		}

		/* Linux: pbsrun.<keyword>.init.in files must exist */
		lib_mpugs[ofs_lib + 24].notReq &= ~(0x1);
		lib_mpugs[ofs_lib + 25].notReq &= ~(0x1);
		lib_mpugs[ofs_lib + 26].notReq &= ~(0x1);
		lib_mpugs[ofs_lib + 27].notReq &= ~(0x1);
		lib_mpugs[ofs_lib + 28].notReq &= ~(0x1);
		lib_mpugs[ofs_lib + 29].notReq &= ~(0x1);
		bin_mpugs[ofs_bin + 30].notReq &= ~(0x1);
	}
}

/**
 * @brief
 * 		print the values of infrstruct.
 *
 * @param[in]	pinf	-	 pointer to infrastruct
 */
static void
print_infrastruct(struct infrastruct *pinf)
{
	int	i, j;
	int	tflag;
	MPUG	*pmpug;

	tflag = 0;
	for (i=0; i<PBS_last; ++i) {

		if (!tflag) {
			++tflag;
			title_string(TC_tvrb, mode, pinf);
		}

		if (pinf->pri.pbs_mpug[i].path) {

			if (tflag == 1) {
				++tflag;
				title_string(TC_datpri, mode, pinf);
			}
			fprintf(stdout, "%s: %s\n", mhp[i], pinf->pri.pbs_mpug[i].path);
		}
	}
	if (tflag) {
		fprintf(stdout, "%s: %d\n", mhp[MHP_svr], pinf->pri.started.server);
		fprintf(stdout, "%s: %d\n", mhp[MHP_mom], pinf->pri.started.mom);
		fprintf(stdout, "%s: %d\n", mhp[MHP_sched], pinf->pri.started.sched);
	}

	tflag = 0;
	for (i=0; i<PH_last; ++i) {

		if ((pmpug = pinf->home[i]) == NULL || (pmpug->notReq & notbits))
			continue;

		if (!tflag++)
			title_string(TC_datho, mode, pinf);

		fprintf(stdout, "\nHierarchy %s:\n", home_mpug_set[i]);

		for (j=0; j<home_sizes[i]; ++j, ++pmpug) {
			if (pmpug->path == NULL || (pmpug->notReq & notbits))
				continue;
                        fprintf(stdout, "%-70s(%s, %s)\n", pmpug->path, perm_string((mode_t)pmpug->req_modes), owner_string(NULL, pmpug, 0));
		}
	}

	tflag = 0;
	for (i=0; i<EXEC_last; ++i) {
                if ((pmpug = pinf->exec[i]) == NULL || (pmpug->notReq & notbits))
			continue;

		if (!tflag++)
			title_string(TC_datex, mode, pinf);

		fprintf(stdout, "\nHierarchy %s:\n\n", exec_mpug_set[i]);

		for (j=0; j<exec_sizes[i]; ++j, ++pmpug) {

			if (pmpug->path == NULL || (pmpug->notReq & notbits))
				continue;
			fprintf(stdout, "%-70s(%s, %s)\n", pmpug->path, perm_string((mode_t)pmpug->req_modes), owner_string(NULL, pmpug, 0));
		}
	}
}
/**
 * @brief
 * 		print the title string based on the code_title value.
 *
 * @param[in]	tc	-	code_title value.
 * @param[in]	mode	-	mode (not used here)
 * @param[in]	pinf	-	pointer to infrastruct
 */
static void
title_string(enum code_title tc, int mode, INFRA *pinf)
{
	switch (tc) {
		case TC_sys:
			fprintf(stdout, "\n\n====== System Information =======\n\n");
			fprintf(stdout,
				"\nsysname=%s\nnodename=%s\nrelease=%s\nversion=%s\nmachine=%s\n",
				pinf->utsd.ub.sysname, pinf->utsd.ub.nodename,
				pinf->utsd.ub.release, pinf->utsd.ub.version,
				pinf->utsd.ub.machine);
			break;

		case TC_top:
			fprintf(stdout,
				"\n\n====== PBS Infrastructure Report =======\n\n");
			break;

		case TC_pri:
			fprintf(stdout,
				"\n\n====== Problems in pbs_probe's Primary Data =======\n\n");
			break;

		case TC_ho:
			fprintf(stdout,
				"\n\n====== Problems in PBS HOME Hierarchy =======\n\n");
			break;

		case TC_ex:
			fprintf(stdout,
				"\n\n====== Problems in PBS EXEC Hierarchy =======\n\n");
			break;

		case TC_ro:
		case TC_fx:
		case TC_cnt:
			/* Not explicitely handled, but keeps compiler quiet. */
			break;

			/*
			 * verbose related strings
			 */

		case TC_tvrb:
			fprintf(stdout,
				"\n\n=== Primary variables and specific hierarchies checked by pbs_probe ===\n\n");
			break;

		case TC_datpri:
			fprintf(stdout, "\nPbs_probe's Primary variables:\n\n");
			break;

		case TC_datho:
			fprintf(stdout, "\n\n=== PBS HOME Infrastructure ===\n");
			break;

		case TC_datex:
			fprintf(stdout, "\n\n=== PBS EXEC Infrastructure ===\n");
			break;

		case TC_noerr:
			fprintf(stdout,
				"\n\n=== No PBS Infrastructure Problems Detected ===\n");
			break;

		case TC_use:
			fprintf(stderr, "Usage: pbs_probe [ -fv ]\n");
			fprintf(stderr, "       pbs_probe --version\n");
			fprintf(stderr,
				"\tno option - run in 'report' mode\n");
			fprintf(stderr,
				"\t-f        - run in 'fix' mode\n");
			fprintf(stderr,
				"\t-v        - show hierarchy examined\n");
			fprintf(stderr,
				"\t--version - show version and exit\n");
			break;
	}
}
/**
 * @brief
 * 		print the title string based on the code_title value.
 *
 * @param[in]	tc	-	code_title value.
 * @param[in]	mode	-	mode (not used here)
 * @param[in]	pinf	-	pointer to infrastruct
 */
static void
print_problems(INFRA *pinf)
{
	int i, j, k;
	int idx;
	int tflag, output_err = 0;
	char **pa;

	for (i=0; i<SRC_last; ++i) {
		tflag = 0;
		for (j=0; j < MSG_last; ++j) {

			if (pinf->msgs[i]->mtbls[j] == NULL)
				continue;

			if (!tflag++)
				switch (i) {
					case SRC_pri:
						title_string(TC_pri, mode, pinf);
						break;

					case SRC_home:
						title_string(TC_ho, mode, pinf);
						break;

					case SRC_exec:
						title_string(TC_ex, mode, pinf);
						break;

					default:
						break;
				}
			idx = pinf->msgs[i]->idx[j];
			pa = pinf->msgs[i]->mtbls[j];
			for (k=0; k < idx; ++k) {
				output_err = 1;
				fprintf(stdout, "%s\n", pa[k]);
			}
		}
	}
	if (output_err == 0)
		title_string(TC_noerr, mode, pinf);
}

/**
 * @brief
 * 		Calling put_msg_in_table with a NULL message pointer is the
 * 		mechanism used to cause the loading of new values into the
 *	 	function's three internal static variables: dflt_pinf, dflt_src,
 * 		dflt_cat - i.e. causing new default values to be established.
 *
 * @param[in]	pinf	-	pointer to infrastruct
 * @param[in]	src	-	default source.
 * @param[in]	category	-default category.
 */
static void
msg_table_set_defaults(INFRA *pinf, int src, int category)
{

	put_msg_in_table(pinf, src, category, NULL);
}
/**
 * @brief
 * 		put values in message table.
 *
 * @param[in]	pinf	-	pointer to infrastruct
 * @param[in]	src	-	source. can be SRC_pri, SRC_home,
 * 						SRC_exec, SRC_last, SRC_none
 * @param[in]	category	-	message category.
 * @param[in]	msg	-	message which needs to be put into table.
 *
 * @return	int
 * @retval	0	: things are fine.
 * @retval	1	: something smells bad!
 *
 * @par MT-safe: No
 */
static int
put_msg_in_table(INFRA *pinf, int src, int category, char* msg)
{
	static INFRA			*dflt_pinf = NULL;
	static enum  msg_sources	dflt_src = SRC_none;
	static enum  msg_categories	dflt_cat = MSG_none;
	static char  *msg_headers[MSG_last] = { NULL};

	char   **ptbl;
	char   **mtb;
	int    idx;

	/*
	 * One shot: Create pointers to table headings
	 */

	if (msg_headers[0] == NULL) {
		msg_headers[MSG_md]   = "Missing Directory Problems:";
		msg_headers[MSG_mf]   = "Missing File Problems:";
		msg_headers[MSG_po]   = "Permission/Ownership Problems:";
		msg_headers[MSG_unr]  = "Directory Entry Problems:";
		msg_headers[MSG_pri]  = "Primary Data Problems:";
		msg_headers[MSG_oth]  = "Other Problems:";
		msg_headers[MSG_real] = "Real Path Problems:";
	}

	if (msg == NULL) {

		/* Load new default values */

		if (pinf)
			dflt_pinf = pinf;

		if (src != SRC_none) {
			if (src != SRC_pri && src != SRC_home && src != SRC_exec) {

				fprintf(stderr, "put_msg_in_table: Bad value for argument \"src\"\n");
				exit(1);
			}
			dflt_src = (enum  msg_sources)src;
		}

		if (category != MSG_none) {

			if (category != MSG_mf   &&  category  != MSG_md  &&
				category != MSG_po   &&  category  != MSG_unr &&
				category != MSG_real &&  category  != MSG_pri &&
				category != MSG_oth) {

				fprintf(stderr, "put_msg_in_table: Bad value for argument \"category\"\n");
				exit(1);
			}
			dflt_cat = (enum  msg_categories)category;
		}

		return (0);
	} /* end of msg == NULL */

	if (pinf == NULL) {
		if (dflt_pinf == NULL) {
			fprintf(stderr, "put_msg_in_table: No default set for pinf\n");
			exit(1);
		}
		pinf = dflt_pinf;
	}

	if (src == SRC_none) {
		if (dflt_src == SRC_none) {
			fprintf(stderr, "put_msg_in_table: No default value for \"argument\" src\n");
			exit(1);
		}
		src = dflt_src;
	}

	if (src != SRC_pri && src != SRC_home && src != SRC_exec) {

		fprintf(stderr, "put_msg_in_table: Bad value for message source\n");
		fprintf(stderr, "message %s:  not saved to table\n\n", msg);
		return (1);
	}

	if (category == MSG_none) {
		if (dflt_cat == MSG_none) {
			fprintf(stderr, "put_msg_in_table: No default value for \"argument\" category\n");
			exit(1);
		}
		category = dflt_cat;
	}

	if (category != MSG_mf  && category != MSG_md  && category != MSG_po &&
		category != MSG_unr && category != MSG_pri && category != MSG_oth &&
		category != MSG_real) {

		fprintf(stderr, "put_msg_in_table: Bad value for message category\n");
		fprintf(stderr, "message %s:  not saved to table\n\n", msg);
		return (1);
	}

	if (pinf->msgs[src] != NULL) {
		if (pinf->msgs[src]->mtbls[category] == NULL) {

			/*
			 * No table exists, malloc memory for one and store
			 * in the first location a pointer to a header message
			 */

			mtb = (char **)malloc(DFLT_MSGTBL_SZ * sizeof(char *));
			if (mtb == NULL) {
				fprintf(stderr, "pbs_probe: Out of Memory\n");
				return (1);
			}
			pinf->msgs[src]->mtbls[category] = mtb;
			idx = pinf->msgs[src]->idx[category];

			pinf->msgs[src]->mtbls[category][idx] = msg_headers[category];
			++pinf->msgs[src]->idx[category];
		}
	} else {

		fprintf(stderr, "put_msg_in_table: No initialization of pinf->msgs\n");
		exit(1);
	}

	idx = pinf->msgs[src]->idx[category];
	if (idx >= DFLT_MSGTBL_SZ) {
		fprintf(stderr, "put_msg_in_table: Table full\n");
		fprintf(stderr, "message %s:  not saved to table\n\n", msg);
		return (1);
	}

	/* add pointer to the message into the table and bump table index */

	ptbl = pinf->msgs[src]->mtbls[category];
	ptbl [ idx ] = strdup(msg);
	++pinf->msgs[src]->idx[category];
	return (0);
}
/**
 * @brief
 * 		get primary vaues from configuration file Then,
 * 		over ride conf derived settings with any values
 * 		set in the process's environment.
 *
 * @param[in]	pinf	-	pointer to infrastruct
 *
 * @return	int
 * @retval	0	: things are fine.
 * @retval	!=0	: something smells bad!
 */
static int
get_primary_values(struct infrastruct *pinf)
{
	FILE	*fp;
	int	rc;
	char	*gvalue;		/* used with getenv() */


	origin_names[PBS_conf] = "PBS CONF FILE";
	origin_names[PBS_home] = "PBS HOME";
	origin_names[PBS_exec] = "PBS EXEC";

	/*
	 * determine path for PBS infrastructure configuration file
	 */

	pinf->pri.pbs_mpug = &pbs_mpugs[0];

	gvalue = getenv("PBS_CONF_FILE");
	if (gvalue == NULL || *gvalue == '\0') {
		pinf->pri.pbs_mpug[PBS_conf].path = default_pbsconf;
		pinf->pri.src_path.conf = SRC_DFLT;
	} else {
		pinf->pri.pbs_mpug[PBS_conf].path = strdup(gvalue);
		pinf->pri.src_path.conf = SRC_ENV;
	}

	if ((fp = fopen(pinf->pri.pbs_mpug[PBS_conf].path, "r")) == NULL) {
		if (stat(pinf->pri.pbs_mpug[PBS_conf].path, &pinf->statd.sb)) {
			if (errno == ENOENT)
				if (mode != 'f')
					return (PBS_CONF_NO_EXIST);
			else {
#if 0
				/*
				 * In "fix" mode and pbs.conf doesn't exist
				 * try to find and run pbs_postinstall to create it
				 */
				path = pinf->pri.pbs_mpug[PBS_conf].path;
				return (pbsdotconf(path));
				return (PBS_CONF_NO_EXIST);
#endif
				return (PBS_CONF_CAN_NOT_OPEN);
			}
			else
				return (PBS_CONF_CAN_NOT_OPEN);
		}
	}

	/*
	 * first source for the primary variables is the config file
	 * Then, over ride conf derived settings with any values set
	 * in the process's environment
	 */

	if ((rc = conf4primary(fp, pinf))) {
	}

	if ((rc = env4primary(pinf))) {
	}
	return (rc);
}
/**
 * @brief
 * 		Read the PBS_CONF_FILE path and store in a buffer.
 *
 * @param[in]	path	-	PBS_CONF_FILE path
 *
 * @return	int
 * @retval	PBS_CONF_NO_EXIST	: No PBS_CONF_FILE.
 */
#if 0
static int
pbsdotconf(char * path)
{

	char	*gvalue_save = NULL;

	if (path == NULL)
		return (PBS_CONF_NO_EXIST);

	pbuf = malloc(strlen("PBS_CONF_FILE=") + strlen(path) + 1);
	if (pbuf == NULL)
		return (PBS_CONF_NO_EXIST);

	if ((gvalue = getenv("PBS_CONF_FILE")) != NULL)
		if ((len = strlen(gvalue)))
			gvalue_save = strdup(gvalue);

	strcpy(pbuf, "PBS_CONF_FILE=");
	strcat(pbuf, path);
	if ((rc = putenv(pbuf))) {
		free(pbuf);
		if (gvalue_save)
			free(gvalue_save);
		return (PBS_CONF_NO_EXIST);
	}
}
#endif
/**
 * @brief
 * 		First try and resolve to a real path the MPUG path
 * 		data belonging to *pinf's "pri" member.
 * @par
 * 		If the PBS HOME pathname was resolvable to a realpath in
 * 		the file system - i.e. have good PBS HOME primary value,
 * 		compute MPUG data for PBS_HOME hierarchy.
 *
 * @param[in]	pinf	-	PBS_CONF_FILE path
 *
 * @return	int
 * @retval	0	: good to go.
 */
static	int
get_realpath_values(struct infrastruct *pinf)
{
	char *real = NULL;
	char path[MAXPATHLEN + 1];
	char *endhead;
	char demarc[]="/";
	int  i, j;
	MPUG *pmpug;
	int  good_prime[PBS_last];
	char *msgbuf;
	const char *pycptr;
        /*
	 * First try and resolve to a real path the MPUG path
	 * data belonging to *pinf's "pri" member
	 */
	for (i = 0; i < PBS_last; ++i) {
		good_prime[i] = 0;
		if (pinf->pri.pbs_mpug[i].path) {
			if ((real = realpath(pinf->pri.pbs_mpug[i].path, NULL)) != NULL) {
				pinf->pri.pbs_mpug[i].realpath = strdup(real);
				good_prime[i] = 1;
				free(real);
			} else if (pinf->pri.pbs_mpug[i].notReq == 0) {
				/*
				 * system not able to convert path string to valid
				 * file system path
				 */
				pbs_asprintf(&msgbuf,
					"Unable to convert the primary, %s, string to a real path\n%s\n",
					origin_names[i], strerror(errno));
				put_msg_in_table(pinf, SRC_pri, MSG_pri, msgbuf);
				free(msgbuf);
				pbs_asprintf(&msgbuf, "%s: %s\n",
					origin_names[i], pinf->pri.pbs_mpug[i].path);
				put_msg_in_table(pinf, SRC_pri, MSG_pri, msgbuf);
				free(msgbuf);
				/* good_prime[i] = 0; */
			}
		} else {
			if (pinf->pri.pbs_mpug[i].notReq == 0) {
				pbs_asprintf(&msgbuf, "Missing primary path %s",
					origin_names[i]);
				put_msg_in_table(pinf, SRC_pri, MSG_pri, msgbuf);
				free(msgbuf);
			}
		}
	}
	for (i = 0; i < PBS_last; ++i) {
		if (good_prime[i] == 0 && pinf->pri.pbs_mpug[i].notReq == 0) {
			print_problems(pinf);
			exit(0);
		}
	}

	/*
	 * If the PBS HOME pathname was resolvable to a realpath in
	 * the file system - i.e. have good PBS HOME primary value,
	 * compute MPUG data for PBS_HOME hierarchy.
	 */

	if (good_prime[PBS_home]) {
		/* only need to check database directory if it is local */
		if (nonlocaldata == 0) {
			int fd;
			struct stat st;
			char buf[MAXPATHLEN+1];
			struct passwd	*pw;

			/*
			 * create path for db_user
			 * This is done outside of the table driven files
			 * because it is optional and no message should
			 * be generated if it does not exist.
			 */
			strcpy(path, pinf->pri.pbs_mpug[PBS_home].path);
			strcat(path, "/server_priv/db_user");

			if ((fd = open(path, O_RDONLY)) != -1) {
				if (fstat(fd, &st) != -1) {
					if ((st.st_mode & 0777) != 0600) {
						pbs_asprintf(&msgbuf,
							"%s, permission must be 0600\n",
							path);
						put_msg_in_table(NULL,
							SRC_home, MSG_real, msgbuf);
						free(msgbuf);
					}
					if (st.st_uid != 0) {
						pbs_asprintf(&msgbuf,
							"%s, owner must be root\n",
							path);
						put_msg_in_table(NULL,
							SRC_home, MSG_real, msgbuf);
						free(msgbuf);
					}
					if (st.st_size < sizeof(buf) &&
						read(fd, buf, st.st_size) ==
						st.st_size) {
						buf[st.st_size] = 0;
						pw = getpwnam(buf);
						if (pw != NULL)
							pbs_dataname[0] = strdup(buf);
						else {
							pbs_asprintf(&msgbuf,
								"db_user %s does not exist\n",
								buf);
							put_msg_in_table(NULL,
								SRC_home, MSG_real, msgbuf);
							free(msgbuf);
						}
					}
				}
				close(fd);
			}
			pw = getpwnam(pbs_dataname[0]);
			if (pw != NULL)
				pbsdata[0] = pw->pw_uid;
		}

		strcpy(path, pinf->pri.pbs_mpug[PBS_home].path);
		strcat(path, demarc);
		endhead = &path[strlen(path)];

		for (i = 0; i < PH_last; ++i) {
			if ((pmpug = pinf->home[i]) == NULL)
				continue;

			for (j = 0; j < home_sizes[i]; ++j) {
				if (pmpug[j].path) {

					/* proceed only if parent realpath is not NULL */

					if (is_parent_rpathnull(pmpug[j].path, pinf->home, PH_last, home_sizes))
						continue;

					strcpy(endhead, pmpug[j].path);

					if ((real = realpath(path, NULL)) != NULL) {
						pmpug[j].realpath = strdup(real);
						free(real);
					} else if ((pmpug[j].notReq & notbits) == 0) {

						if (errno == ENOENT)
							pbs_asprintf(&msgbuf, "%s, %s\n",
								path, strerror(errno));
						else
							pbs_asprintf(&msgbuf,
								"%s,  errno = %d\n",
								path, errno);

						put_msg_in_table(NULL, SRC_home, MSG_real, msgbuf);
						free(msgbuf);
					}
				}
			}
		}
	}


	/*
	 * If the PBS EXEC string was  resolvable to a realpath in
	 * the file system - i.e. have good PBS HOME primary value,
	 * compute MPUG data for PBS EXEC hierarchy
	 */

	if (good_prime[PBS_exec]) {
		strcpy(path, pinf->pri.pbs_mpug[PBS_exec].path);
		strcat(path, demarc);
		endhead = &path[strlen(path)];

		for (i = 0; i < EXEC_last; ++i) {

			if ((pmpug = pinf->exec[i]) == NULL)
				continue;

			for (j = 0; j < exec_sizes[i]; ++j) {
				if (pmpug[j].path) {

					/* proceed only if parent realpath is not NULL */

					if ((is_parent_rpathnull(pmpug[j].path, pinf->exec, EXEC_last, exec_sizes)))
						continue;

					strcpy(endhead, pmpug[j].path);
					if ((real = realpath(path, NULL)) != NULL) {
						pmpug[j].realpath = strdup(real);
						free(real);
					} else if ((pycptr = strstr(path, ".pyc")) != NULL){
						glob_t pycbuf;
						glob(path, 0, NULL, &pycbuf);
						if (pycbuf.gl_pathc == 1){
							pmpug[j].realpath = strdup(pycbuf.gl_pathv[0]);
							pmpug[j].path = strdup((pycbuf.gl_pathv[0] + strlen(pinf->pri.pbs_mpug[PBS_exec].path) + strlen(demarc)));
						}
						globfree(&pycbuf);
					} else if ((pmpug[j].notReq & notbits) == 0) {
                        			if (errno == ENOENT)
							pbs_asprintf(&msgbuf, "%s, %s\n",
								path, strerror(errno));
						else
							pbs_asprintf(&msgbuf,
								"%s,  errno = %d\n",
								path, errno);
						put_msg_in_table(NULL, SRC_exec, MSG_real, msgbuf);
						free(msgbuf);
					}
				}
			}
		}
	}
	return (0);
}

/**
 * @brief
 * 		Does path have a parent directory?
 * @par
 * 		replace demarc value
 *
 * @param[in]	path	-	location of file/directory
 * @param[in]	mpa	-	pointer to MPUG structure which stores file/directory properties.
 * @param[in]	nelts	-	number of elements in mpa
 * @param[in]	nmems	-	array storing number of members for each MPUG.
 *
 * @return	int
 * @retval	0	: good to go.
 * @retval	1	: parent unresolved.
 */
static int
is_parent_rpathnull(char *path, MPUG **mpa, int nelts, int * nmems)
{
	char *dp;
	MPUG *mpug;
	int  i, j;
	int  rc = 0, done = 0;

	/*
	 * Does path have a parent directory?
	 */

	if (path == NULL)
		return (0);
	else if (!((dp = strrchr(path, DEMARC)) && (dp != path)))
		return (0);

	*dp = '\0';	/* temporarily overwrite demarc */

	for (i=0; i<nelts; ++i) {

		if ((mpug = mpa[i]) == NULL)
			continue;

		for (j=0; j<nmems[i]; ++j, ++mpug)

			if (strcmp(path, mpug->path) == 0) {

				/* is parent unresolved */
				if (mpug->realpath == NULL) {
					rc = 1;
				}
				done = 1;
				break;
			}

		if (done)
			break;
	}

	/* replace demarc value */

	*dp = DEMARC;
	return rc;
}
/**
 * @brief
 * 		inspect the directory entries in infrastruct
 *
 * @param[in]	pinf	-	pointer to infrastruct
 *
 * @return	int
 * @retval	0	: good to go.
 */
#if 0
static	int
inspect_dir_entries(struct infrastruct *pinf)
{
	int	i, j;
	MPUG	*pmpug;
	MPUG	**knwn_set;
	int	tsz;


	for (i=0; i<PH_last; ++i) {

		if ((pmpug = pinf->home[i]) == NULL)
			continue;
		tsz = home_sizes[i];

		for (j=0; j<home_sizes[i]; ++j) {

			if (pmpug[j].path && pmpug[j].realpath) {

				/*
				 * If pmpug[j] relates to a directory, find all database
				 * MPUG's for entries that belong to that directory.
				 *
				 * A pointer to an array of MPUG pointers is returned.
				 * These are MPUGS gleened from pbs_probe's database and
				 * is thought of as the, "known set of MPUGS".
				 */

				knwn_set = which_Knwn_mpugs(&pmpug[j], pmpug, tsz);
				msg_table_set_defaults(pinf, SRC_home, MSG_none);

				/*
				 * If *pmpug[j] happens to the MPUG data for a directory,
				 * check each entry of that directory either against
				 * MPUG data from the "known set" or against some other
				 * criteria to ascertain its "correctness"
				 */

				chk_entries(&pmpug[j], knwn_set);
			}
		}
	}

	for (i=0; i<EXEC_last; ++i) {

                if ((pmpug = pinf->exec[i]) == NULL)
			continue;
		tsz = exec_sizes[i];

		for (j=0; j<exec_sizes[i]; ++j) {

			if ((pmpug[j].path)) {
				/*
				 * Refer to block comments in previous code block
				 * for explanation of what this code block does
				 */

				knwn_set = which_Knwn_mpugs(&pmpug[j], pmpug, tsz);
				msg_table_set_defaults(pinf, SRC_exec, MSG_none);
				chk_entries(&pmpug[j], knwn_set);
			}
		}
	}

	return 0;
}
#endif	/* 0 */
/**
 * @brief
 * 		defines the suffix set and returns the set corresponding to the path of directory.
 *
 * @param[in]	pmpug	-	pointer to MPUG struct
 *
 * @return	char *
 * @retval	NULL	: No match found.
 * @retval	the suffix set	: corresponding to the directory.
 */
#if 0
static const char *
which_suffixset(MPUG *pmpug)
{

	static char vld_job[] = ".JB,.SC,.CR,.XP,.OU,.ER,.CK,.TK,.CS,.BD";
	static char vld_hooks[] = ".HK,.PY";
	static char vld_resv[] = ".RB,.RBD";
	static char vld_tcltk[] = ".h,8.3,8.3.a,.sh";
	static char vld_python[] = ".py,.pyc,.so";
	char buf[MAXPATHLEN];
	char py_version[4];
	/* Get version of the Python interpreter */
	strncpy(py_version, Py_GetVersion(), 3);
	py_version[4] = '\0';

	if (pmpug->path == NULL)
		return NULL;
	if (strcmp("server_priv/jobs", pmpug->path) == 0)
		return (vld_job);
	if (strcmp("server_priv/users", pmpug->path) == 0)
		return (vld_job);
	if (strcmp("server_priv/hooks", pmpug->path) == 0)
		return (vld_hooks);
	if (strcmp("mom_priv/jobs", pmpug->path) == 0)
		return (vld_job);
	if (strcmp("undelivered", pmpug->path) == 0)
		return (vld_job);
	if (strcmp("spool", pmpug->path) == 0)
		return (vld_job);
	if (strcmp("tcltk/bin", pmpug->path) == 0)
		return (vld_tcltk);
	if (strcmp("tcltk/include", pmpug->path) == 0)
		return (vld_tcltk);
	if (strcmp("tcltk/lib", pmpug->path) == 0)
		return (vld_tcltk);
	if (strcmp("lib/python", pmpug->path) == 0)
		return (vld_python);
	if (strcmp("lib/python/altair", pmpug->path) == 0)
		return (vld_python);
	if (strcmp("lib/python/altair/pbs", pmpug->path) == 0)
		return (vld_python);
	if (strcmp("lib/python/altair/pbs/v1", pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s/logging", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s/shared", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s/xml", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s/xml/dom", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s/xml/etree", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s/xml/parsers", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	snprintf(buf, sizeof(buf), "lib/python/python%s/xml/sax", py_version);
	if (strcmp(buf, pmpug->path) == 0)
		return (vld_python);
	return NULL;
}
#endif /* 0 */

#if 0
static	int
is_suffix_ok(char *entryname, char *psuf)
{
	char	tbuf[100];
	char	*tok;
	int	len;
	int	elen = strlen(entryname);

	if (psuf == NULL)
		return 1;

	strcpy(tbuf, psuf);

	tok = strtok(tbuf, ",");
	for (; tok; tok = strtok(NULL,  ",")) {

		len = strlen(tok);
		if (elen <= len)
			continue;
		else if (strcmp(&entryname[elen - len], tok))
			continue;
		else {
			/* matched */
			return (1);
		}
	}
	return 0;
}
#endif	/* 0 */


#if 0
static 	MPUG  **
which_knwn_mpugs(MPUG *pmpug, MPUG *sets[], int *ssizes, int asz)
{
	/* Assumption being made that argument setsz < 100 */

	static	MPUG *knwn_mpugs[100];
	MPUG	     *pm;
	char	     *dp;
	char	     tmp_path[MAXPATHLEN];
	int i, j, idx=0;

	knwn_mpugs[0] = NULL;

	if ((pmpug == NULL) ||  !(pmpug->req_modes & S_IFDIR))
		return knwn_mpugs;

	for (i=0, pm=sets[0]; i<asz; ++i, pm = sets[i]) {
		for (j=0; j<ssizes[i]; ++j, ++pm) {

			/*
			 * copy to temporary avoids a problem when pmpug->path
			 * and pm->path never point to the same memory location
			 */

			strcpy(tmp_path, pm->path);

			if ((dp = strrchr(tmp_path, (int)'/')) == NULL)
				continue;

			*dp = '\0';
			if (strcmp(pmpug->path, tmp_path) == 0)
				knwn_mpugs[idx++] = pm;
			*dp = DEMARC;
		}
	}

	/*
	 * MPUG pointer array _must_ end with a NULL pointer
	 */

	knwn_mpugs[idx] = NULL;
	return	(knwn_mpugs);
}
#endif	/* 0 */

#if 0
static 	MPUG  **
which_Knwn_mpugs(MPUG *pmpug, MPUG *base, int tsize)
{
	/* Assumption being made that argument setsz < 100 */

	static	MPUG *knwn_mpugs[100];
	MPUG	     *pm;
	char	     *dp;
	char	     tmp_path[MAXPATHLEN];
	int	     j, idx=0;

	knwn_mpugs[0] = NULL;

	if ((pmpug == NULL) ||  !(pmpug->req_modes & S_IFDIR))
		return knwn_mpugs;

	for (j=0, pm=base; j<tsize; ++j, ++pm) {

		/*
		 * copy to temporary avoids a problem when pmpug->path
		 * and pm->path never point to the same memory location
		 */

		strcpy(tmp_path, pm->path);

		if ((dp = strrchr(tmp_path, (int)'/')) == NULL)
			continue;

		*dp = '\0';
		if (strcmp(pmpug->path, tmp_path) == 0)
			knwn_mpugs[idx++] = pm;

		*dp = DEMARC;
	}

	/*
	 * MPUG pointer array _must_ end with a NULL pointer
	 */

	knwn_mpugs[idx] = NULL;
	return	(knwn_mpugs);
}
#endif	/* 0 */

#if 0
/**
 * @brief
 * If pmpug happens to the MPUG data for a directory,
 * check each entry of that directory either against
 * MPUG data from the "known set" or against some other
 * criteria to ascertain its "correctness"
 *
 * @param[in] pmpug - pointer to struct modes_path_user_group
 * @param[in] knwn_set - known set of MPUGS
 */
static void
chk_entries(MPUG *pmpug, MPUG **knwn_set)
{
	DIR		*dir;
	struct dirent	*pdirent;
	char		*dirpath = pmpug->realpath;
	int		i;
	int		dirtype;
	char		*name;
	char		*psuf;
	char		msg[1024];

	if ((dirpath == NULL) || !(pmpug->req_modes & S_IFDIR))
		return;

	if ((dir = opendir(dirpath)) == NULL) {

		snprintf(msg, sizeof(msg), "Can't open directory %s for inspection\n", dirpath);
		put_msg_in_table(NULL, SRC_none, MSG_oth, msg);
		return;
	}

	/*
	 * Certain directories will have a list of associated suffixes.
	 * Get the location of any such list.
	 */

	psuf = (char *)which_suffixset(pmpug);

	/*
	 * Determine PBS directory type
	 */

	pbs_dirtype(&dirtype, pmpug);

	while (errno = 0, (pdirent = readdir(dir)) != NULL) {

		/*
		 * Ignore non-relevant directory entries
		 */

		if (strcmp(".", pdirent->d_name) == 0)
			continue;
		else if (strcmp("..", pdirent->d_name) == 0)
			continue;

		/*
		 * Begin by checking if the name of this entry matches any one
		 * of the names stored in the "known names (MPUGS)" subset
		 * supplied as input to this function
		 */

		for (i=0; knwn_set[i]; ++i) {
			if ((name = strrchr(knwn_set[i]->path, DEMARC))) {
				++name;
				if (strcmp(name, pdirent->d_name) == 0)
					break;
			}
		}

		if (knwn_set[i] != NULL) {

			/* matched a known entry, call readdir again */
			continue;
		}

		/*
		 * See if there is any, "name is outside the database,"
		 * kind of processing that would apply, and do it
		 */

		if (non_db_resident(pmpug, psuf, dirtype, pdirent->d_name))
			continue;

		/*
		 * entry is not a known name in pbs_probe's database and none
		 * of the other mechanisms for evaluating, in so way, the
		 * fitness of this entry were found to apply.
		 */

		snprintf(msg, sizeof(msg), "%s, unrecognized entry appears in %s\n", pdirent->d_name, pmpug->path);
		put_msg_in_table(NULL, SRC_none, MSG_unr, msg);
	}
	if (errno != 0 && errno != ENOENT) {

		snprintf(msg, sizeof(msg), "Can't read directory %s for inspection\n", dirpath);
		put_msg_in_table(NULL, SRC_none, MSG_oth, msg);
		(void)closedir(dir);
		return;
	}
	(void)closedir(dir);
}
#endif	/* 0 */

#if 0
static	void
pbs_dirtype(int *dirtype, MPUG *pmpug)
{
	if (strstr(pmpug->path, "logs"))
		*dirtype = PBS_logsdir;
	else if (strstr(pmpug->path, "accounting"))
		*dirtype = PBS_acctdir;
	else if (strstr(pmpug->path, "spool"))
		*dirtype = PBS_spooldir;
	else if (strstr(pmpug->path, "jobs"))
		*dirtype = PBS_jobsdir;
	else if (strstr(pmpug->path, "users"))
		*dirtype = PBS_usersdir;
	else if (strstr(pmpug->path, "hooks"))
		*dirtype = PBS_hooksdir;
	else if (strstr(pmpug->path, "hooks/tmp"))
		*dirtype = PBS_hookswdir;
	else
		*dirtype = PBS_niltype;
}
#endif	/* 0 */

#if 0
static	int
non_db_resident(MPUG *pmpug, char* psuf, int dirtype, char *entryname)
{
	char	msg[1024];

	switch (dirtype) {
		case PBS_acctdir:
		case PBS_logsdir:
			if (is_a_numericname(entryname) == 0) {

				snprintf(msg, sizeof(msg), "%s, unrecognized entry appears in %s\n", entryname, pmpug->path);
				put_msg_in_table(NULL, SRC_none, MSG_unr, msg);
			}
	}

	if (psuf && is_suffix_ok(entryname, psuf)) {
		return (1);
	}

	/* needs further examination to decide */

	return (0);
}
#endif	/* 0 */

#if 0
static	int
is_a_numericname(char *entryname)
{

	char	*endptr;

	(void)strtol(entryname, &endptr, 0);
	if (*endptr == '\0')
		return (1);
	else
		return (0);
}
#endif	/* 0 */
/**
 * @brief
 * 		check owner mode on pbs directories.
 *
 * @param[in]	pinf	-	pointer to infrasruct
 *
 * @return	int
 * @retval	0	: success
 */
static	int
check_paths(struct infrastruct *pinf)
{
	int	i, j;
	MPUG	*pmpug;
	char	*realpath;


	for (i=0; i<PBS_last; ++i) {
		msg_table_set_defaults(pinf, SRC_pri, MSG_po);
		if ((realpath = pinf->pri.pbs_mpug[i].realpath))
			check_owner_modes(realpath, &pinf->pri.pbs_mpug[i], 0);
	}

	for (i=0; i<PH_last; ++i) {
		msg_table_set_defaults(pinf, SRC_home, MSG_po);

		if ((pmpug = pinf->home[i]) == NULL)
			continue;

		for (j=0; j<home_sizes[i]; ++j) {
			if ((realpath = pmpug[j].realpath))
				check_owner_modes(realpath, pmpug + j, 0);
		}
	}

	for (i=0; i<EXEC_last; ++i) {

		msg_table_set_defaults(pinf, SRC_exec, MSG_po);

		if ((pmpug = pinf->exec[i]) == NULL)
			continue;

		for (j=0; j<exec_sizes[i]; ++j) {
			if ((realpath = pmpug[j].realpath) &&
				!(pmpug[j].notReq & notbits)) {
                                check_owner_modes(realpath, pmpug + j, 0);
			}
		}
	}
	return 0;
}
/**
 * @brief
 * 		if full path check is required, see if the path contains
 * 		a sub-path and if it does, call check_owner_modes on that
 * 		sub-path
 * @par
 * 		if lstat on the path is successful, check perms and owners
 * 		against values stored in MPUG structure
 *
 * @param[in]	path	-	path which needs to be checked.
 * @param[in]	p_mpug	-	pointer to MPUG structure
 * @param[in]	sys	-	indicates ownerID < 10, group id < 10
 *
 * @return	int
 * @retval	0	: success
 * @retval	!=0	: something got wrong!
 *
 * @par MT-safe: No
 */
static	int
check_owner_modes(char *path, MPUG *p_mpug, int sys)
{
	int	    rc = 0;		/* encountered no mode problem */
	char	    *dp;
	char	    msg[256];
	const char  *perm_msg;

	struct stat sbuf;
	static int  cnt_recursive = 0;

	/*
	 * if full path check is required, see if the path contains
	 * a sub-path and if it does, call check_owner_modes on that
	 * sub-path
	 */

	if (p_mpug->chkfull &&
		(dp = strrchr(path, DEMARC)) && (dp != path)) {
		/* temporarily overwrite demarc */

		*dp = '\0';

		++cnt_recursive;
		rc = check_owner_modes(path, p_mpug, 0);

		/* replace demarc value and stat this component of real path */

		*dp = DEMARC;

	}

	/*
	 * if lstat on the path is successful, check perms and owners
	 * against values stored in MPUG structure
	 */

	if (rc == LSTAT_PATH_ERR) {
		if (cnt_recursive > 0)
			--cnt_recursive;
		return (rc);
	}

	/*
	 * Clarification for reader may be in order:
	 *
	 * For a fullpath check, getting to this point in the
	 * code means the prior subpath was ok, else would be
	 * taking the above return.
	 *
	 * For a non-fullpath check, we are immediately here
	 */

	if (! lstat(path, &sbuf)) {

		/* successful on the lstat */
		rc = mbits_and_owner(&sbuf, p_mpug, sys);
		if (rc) {
			snprintf(msg, sizeof(msg), "\n%s", path);
			put_msg_in_table(NULL, SRC_none, MSG_po, msg);
			perm_msg = perm_owner_msg(&sbuf, p_mpug, NULL, sys);
			strcpy(msg, perm_msg);
			put_msg_in_table(NULL, SRC_none, MSG_po, msg);
		}
		/*
		 * if running in "fix" mode, do fixing up to and including
		 * the maximum authorized level (max_level).
		 */
		fix(mode, rc, max_level, p_mpug, NULL, &sbuf, FIX_po);

	} else {

		/* lstat complained about something */

		if (errno != ENOENT || ! p_mpug->notReq) {
			/* this PBS file is required */

			snprintf(msg, sizeof(msg), "lstat error: %s, \"%s\"\n", path, strerror(errno));
			put_msg_in_table(NULL, SRC_none, MSG_real, msg);
			rc = LSTAT_PATH_ERR;
		}
	}

	if (cnt_recursive > 0)
		--cnt_recursive;
	return (rc);
}

/**
 * @brief
 * 		Test mode bits and ownerships
 *
 * @param[in]	ps	-	 stat  "buffer"
 * @param[in]	p_mpug	-	pointer to MPUG structure
 * @param[in]	sys	-	indicates ownerID < 10, group id < 10
 *
 * @return	int
 * @retval	0	: success
 * @retval	PATH_ERR	: something got wrong!
 */

static	int
mbits_and_owner(struct stat *ps, MPUG *p_mpug, int sys)
{
	int	    i;
	mode_t	    modes;

	/*
	 * first adjust bits from the MPUG by turning off mode bits that should
	 * be disallowed at this level in the hierarchy and turn on those bits
	 * that are required, before testing the modes produced by lstat call
	 */

	if (sys == 0) {

		modes = (mode_t)p_mpug->req_modes;
		if ((ps->st_mode & modes) != modes)
			return (PATH_ERR);

		modes = (mode_t)p_mpug->dis_modes;
		if (ps->st_mode & modes)
			return (PATH_ERR);
	}

	/*
	 * if the MPUG has associated "user and group"
	 * data, test if this file's user and group is consitent
	 * with what is in the database
	 */

	if (p_mpug->vld_ug) {
		for (i=0; p_mpug->vld_ug->uids[i] != -1; ++i) {
			if (p_mpug->vld_ug->uids[i] == ps->st_uid)
				break;
		}
		if (p_mpug->vld_ug->uids[i] == -1)
			return (PATH_ERR);
	}

	if (p_mpug->vld_ug) {

		for (i=0; p_mpug->vld_ug->gids[i]; ++i) {
			if (p_mpug->vld_ug->gids[i] == ps->st_gid)
				break;
		}
		if (p_mpug->vld_ug->gids[i] == -1)
			return (PATH_ERR);
	}

	return (0);
}
/**
 * @brief
 * 		prepare a permission owner message in the following format
 * 		perm_is, owner_is, perm_need, owner_need
 *
 * @param[in]	ps	-	 stat  "buffer"
 * @param[in]	p_mpug	-	pointer to MPUG structure
 * @param[in]	p_adj	-	pointer to ADJ structure
 * @param[in]	sys	-	indicates ownerID < 10, group id < 10
 *
 * @return	permission owner message
 *
 * @par MT-safe: No
 */
static const	char *
perm_owner_msg(struct stat *ps, MPUG *p_mpug,
	ADJ  *p_adj, int sys)
{
	mode_t	    modes;
	char	    *perm_is;
	char	    *perm_need;
	char	    *owner_is;
	char	    *owner_need;
	static char buf[1024];

	/*
	 * first adjust bits from the MPUG by turning off mode bits that should
	 * be disallowed at this level in the hierarchy and turn on those bits
	 * that are required, before testing the modes produced by lstat call
	 */

	owner_is = strdup(owner_string(ps, NULL, sys));
	owner_need = strdup(owner_string(NULL, p_mpug, sys));

	if (sys) {

		snprintf(buf, sizeof(buf), "(%s) needs to be (%s)", owner_is, owner_need);
		free(owner_is);
		free(owner_need);
		return (buf);
	}

	/* continue with this part if part of PBS hierarchy proper */

	modes = (mode_t)p_mpug->req_modes;
	if (p_adj)
		modes = (modes & ~p_adj->dis) | p_adj->req;

	perm_is = strdup(perm_string(ps->st_mode));
	perm_need = strdup(perm_string(modes));

	snprintf(buf, sizeof(buf), "(%s , %s) needs to be (%s , %s)",
		perm_is, owner_is, perm_need, owner_need);

	free(perm_is);
	free(perm_need);
	free(owner_is);
	free(owner_need);
	return (buf);
}

/**
 * @brief
 * 		perm_string - create permission string from mode.
 *
 * @param[in]	modes	-	required permissions (modes)
 *
 * @return	permission string
 *
 * @par MT-safe: No
 */
static	char *
perm_string(mode_t modes)
{
	static char buf[12];

	strcpy(buf, "----------");

	if (S_IFDIR & modes)
		buf[0] = 'd';

	if (S_IRUSR & modes)
		buf[1] = 'r';
	if (S_IWUSR & modes)
		buf[2] = 'w';

	if (S_IXUSR & modes)
		buf[3] = 'x';

	if (S_ISUID & modes)
		buf[3] = 's';

	if (S_IRGRP & modes)
		buf[4] = 'r';
	if (S_IWGRP & modes)
		buf[5] = 'w';
	if (S_IXGRP & modes)
		buf[6] = 'x';

	if (S_ISGID & modes)
		buf[6] = 's';

	if (S_IROTH & modes)
		buf[7] = 'r';
	if (S_IWOTH & modes)
		buf[8] = 'w';
	if (S_IXOTH & modes)
		buf[9] = 'x';

	if (S_ISVTX & modes)
		buf[9] = 't';

	return buf;
}
/**
 * @brief
 * 		formulate a string contains owner user info and group info.
 *
 * @param[in]	ps	-	data returned by the stat() function
 * @param[in]	p_mpug	-	modes_path_user_group structure
 * @param[in]	sys	-	indicates ownerID < 10, group id < 10
 *
 * @return	string contains owner user info and group info.
 *
 * @par MT-safe: No
 */
static	const char *
owner_string(struct stat *ps, MPUG *p_mpug, int sys)
{
	struct passwd	*ppw;
	struct group	*pgrp;

	static char buf[1024];

	buf[0] = '\0';
	if (ps) {
		ppw = getpwuid(ps->st_uid);
		pgrp = getgrgid(ps->st_gid);

		if (ppw != NULL && pgrp != NULL &&
			ppw->pw_name != NULL && pgrp->gr_name != NULL)

			snprintf(buf, sizeof(buf), "%s , %s", ppw->pw_name, pgrp->gr_name);
		else
			snprintf(buf, sizeof(buf), "%d , %d", ps->st_uid, ps->st_gid);

	} else if (p_mpug) {
		if (p_mpug->vld_ug) {
			if (sys)
				snprintf(buf, sizeof(buf), "ownerID < 10, group id < 10");
			else
				snprintf(buf, sizeof(buf), "%s, group id < 10", p_mpug->vld_ug->unames[0]);
		} else
			snprintf(buf, sizeof(buf), " ");
	}
	return buf;
}

/**
 * @brief
 * 		process return code and arrive at a return code that will determine the fate of pbs_probe
 *
 * @param[in]	from	-	Numeric codes, options - GET_PRIMARY_VALUES, END_FUNC_NAMES.
 * @param[in]	rc	-	return code to be processed.
 * @param[in]	pinf	-	pointer to infrastruct
 *
 * @return	int
 * @retval	0	: primary data is fine, continue with pbs_probe.
 * @retval	1	:  primary data is bogus, pbs_probe must exit
 */
static int
process_ret_code(enum func_names from, int rc, struct infrastruct *pinf)
{
	int  ret = 0;
	char msg[1024];

	if (from == GET_PRIMARY_VALUES) {

		if (rc != 0) {
			if (pinf->pri.pbs_mpug[PBS_conf].path) {

				if (rc == PBS_CONF_NO_EXIST)
					snprintf(msg, sizeof(msg), "File %s does not exist\n",
						pinf->pri.pbs_mpug[PBS_conf].path);
				else if (rc == PBS_CONF_CAN_NOT_OPEN)
					snprintf(msg, sizeof(msg), "Could not open PBS configuration file %s\n",
						pinf->pri.pbs_mpug[PBS_conf].path);
				else
					snprintf(msg, sizeof(msg),
						"Internal pbs_probe problem, unknown return code\n");

				put_msg_in_table(pinf, SRC_pri, MSG_pri, msg);
			}
			ret = 1;	/* primary data is bogus, pbs_probe must exit */
		}
	}

	return (ret);
}

/**
 * @brief
 * 		read the configuration file and obtain primary data for infrastruct structureS
 *
 * @param[in]	fp	-	file pointer to config file
 * @param[out]	pointer to infrastuct structure
 */
static	int
conf4primary(FILE *fp, struct infrastruct *pinf)
{
	char buf[1024];
	char *conf_name;              /* the name of the conf parameter */
	char *conf_value;             /* the value from the conf file or env*/
	unsigned int uvalue;          /* used with sscanf() */

	/* should not be calling with a NULL value for fp */

	assert(fp != NULL);

	while (fgets(buf, 1024, fp) != NULL) {
		if (buf[0] != '#') {
			/* replace '\n' with '\0' */
			buf[strlen(buf)-1] = '\0';
			conf_name = strtok(buf, "=");
			conf_value = strtok(NULL, "     ");

			/* ignore the unexpected (inserted blank line?) */

			if ((conf_name == NULL) || (conf_value == NULL))
				continue;

			if (!strcmp(conf_name, "PBS_START_SERVER")) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pinf->pri.started.server = ((uvalue > 0) ? 1 : 0);
				pinf->pri.src_started.server = SRC_CONF;
			}
			else if (!strcmp(conf_name, "PBS_START_MOM")) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pinf->pri.started.mom = ((uvalue > 0) ? 1 : 0);
				pinf->pri.src_started.mom = SRC_CONF;
			}
			else if (!strcmp(conf_name, "PBS_START_SCHED")) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pinf->pri.started.sched = ((uvalue > 0) ? 1 : 0);
				pinf->pri.src_started.sched = SRC_CONF;
			}
			else if (!strcmp(conf_name, "PBS_HOME")) {
				if (pinf->pri.pbs_mpug[PBS_home].path)
					free(pinf->pri.pbs_mpug[PBS_home].path);
				pinf->pri.pbs_mpug[PBS_home].path = strdup(conf_value);
				pinf->pri.src_path.home = SRC_CONF;
			}
			else if (!strcmp(conf_name, "PBS_CONF_DATA_SERVICE_HOST")) {
				nonlocaldata = 1;
			}
			else if (!strcmp(conf_name, "PBS_EXEC")) {
				if (pinf->pri.pbs_mpug[PBS_exec].path)
					free(pinf->pri.pbs_mpug[PBS_exec].path);
				pinf->pri.pbs_mpug[PBS_exec].path = strdup(conf_value);
				pinf->pri.src_path.exec = SRC_CONF;
			}
			else if (!strcmp(conf_name, "PBS_DAEMON_SERVICE_USER")) {
				struct passwd *pw;
				pw = getpwnam(conf_value);
				if (pw != NULL) {
					pbs_servicename[0] = strdup(conf_value);
					pbsservice[0] = pw->pw_uid;
				}
				else {
					char *msgbuf;
					pbs_asprintf(&msgbuf, "Service user %s does not exist\n", conf_value);
					put_msg_in_table(NULL, SRC_CONF, MSG_real, msgbuf);
					free(msgbuf);
				}
			}

		} else {
			/* ignore comment lines (# in column 1) */
			continue;
		}
	}
	return (0);
}
/**
 * @brief
 * 		read the environment values and store in infrastruct.
 *
 * @param[out]	pinf	-	pointer to environment structure.
 *
 * @return	int
 * @retval	0	: success
 */
static	int
env4primary(struct infrastruct *pinf)
{
	char *gvalue;                 /* used with getenv() */
	unsigned int uvalue;          /* used with sscanf() */

	if ((gvalue = getenv("PBS_START_SERVER"))) {
		if (sscanf(gvalue, "%u", &uvalue) == 1) {
			pinf->pri.started.server = ((uvalue > 0) ? 1 : 0);
			pinf->pri.src_started.server = SRC_ENV;
		}
	}
	if ((gvalue = getenv("PBS_START_MOM"))) {
		if (sscanf(gvalue, "%u", &uvalue) == 1) {
			pinf->pri.started.mom = ((uvalue > 0) ? 1 : 0);
			pinf->pri.src_started.mom = SRC_ENV;
		}
	}
	if ((gvalue = getenv("PBS_START_SCHED"))) {
		if (sscanf(gvalue, "%u", &uvalue) == 1) {
			pinf->pri.started.sched = ((uvalue > 0) ? 1 : 0);
			pinf->pri.src_started.sched = SRC_ENV;
		}
	}
	if ((gvalue = getenv("PBS_HOME"))) {

		if (pinf->pri.pbs_mpug[PBS_home].path)
			free(pinf->pri.pbs_mpug[PBS_home].path);

		pinf->pri.pbs_mpug[PBS_home].path = strdup(gvalue);
		pinf->pri.src_path.home = SRC_ENV;
	}
	if ((gvalue = getenv("PBS_EXEC"))) {

		if (pinf->pri.pbs_mpug[PBS_exec].path)
			free(pinf->pri.pbs_mpug[PBS_exec].path);

		pinf->pri.pbs_mpug[PBS_exec].path = strdup(gvalue);
		pinf->pri.src_path.exec = SRC_ENV;
	}
	if ((gvalue = getenv("PBS_CONF_DATA_SERVICE_HOST")) != NULL) {
		nonlocaldata = 1;
	}
	if ((gvalue = getenv("PBS_DAEMON_SERVICE_USER")) != NULL) {
		struct passwd *pw;
		pw = getpwnam(gvalue);
		if (pw != NULL) {
			pbs_servicename[0] = strdup(gvalue);
			pbsservice[0] = pw->pw_uid;
		}
		else {
			char *msgbuf;
			pbs_asprintf(&msgbuf, "Service user %s does not exist\n", gvalue);
			put_msg_in_table(NULL, SRC_CONF, MSG_real, msgbuf);
			free(msgbuf);
		}
	}


	return (0);
}

/**
 * @brief
 * 		fix - check is a fix is necessary and, if it is, attempt to do
 * 		the fix, being careful not to attempt a fix whose code is higher
 * 		than the maximum allowed (max_level.)
 * @par
 * 		If a fix is attempted, add an appropriate message(s) to the end of
 * 		the relevant message category.
 *
 * @param[in]	probemode	-	probe mode
 * @param[in]	need	-	required or not ?
 * @param[in]	max_level	-	maximum allowed
 * @param[in]	pmpug	-	pointer to modes_path_user_group structure
 * @param[in]	padj	-	pointer to a structure which holds data for modeadjustments.
 * @param[in]	ps	-	data returned by the stat() function
 * @param[in]	fc	-	fix codes.
 *
 * @return	none
 */
static void
fix(int probemode, int need, int max_level, MPUG *pmpug, ADJ *padj, struct stat *ps, int fc)
{
	if ((need == 0) || (probemode != (int)'f') || (fc > max_level))
		return;

	switch (fc) {
		case FIX_po:
			if (padj == NULL)
				fix_perm_owner(pmpug, ps, padj);
			break;
	}
}

/**
 * @brief
 * 		fix_perm_owner - attempt a fix of permission or ownership problems on
 * 		the input file and add a message(s) to whatever default message category
 * 		is currently set.
 *
 * @param[in]	p_mpug	-	pointer to modes_path_user_group structure
 * @param[in]	ps	-	data returned by the stat() function
 * @param[in]	p_adj	-	pointer to a structure which holds data for modeadjustments.
 *
 * @return	none
 */
static void
fix_perm_owner(MPUG *p_mpug, struct stat *ps, ADJ *p_adj)
{
	char		msg[512];
	mode_t		modes;
	mode_t		dis_modes;
	unsigned	fixes = 0;
	int		i, rc;

	if (ps == NULL)
		return;

	modes = (mode_t)p_mpug->req_modes;
	if (p_adj)
		modes = (modes & ~p_adj->dis) | p_adj->req;

	if (p_adj)
		dis_modes = (~modes & (mode_t)p_mpug->dis_modes) | p_adj->dis;
	else
		dis_modes = (mode_t)p_mpug->dis_modes;

	if (dis_modes & modes) {
		snprintf(msg, sizeof(msg), "%s: database problem, 'allowed/disallowed' modes overlap", p_mpug->path);
		put_msg_in_table(NULL, SRC_none, MSG_po, msg);
		return;
	}

	if (ps->st_mode != modes) {
		if ((rc = chmod(p_mpug->realpath, modes))) {
			snprintf(msg, sizeof(msg), "%s: permission correction failed, %s", p_mpug->path, strerror(errno));
			put_msg_in_table(NULL, SRC_none, MSG_po, msg);
		} else {
			fixes |= 0x1;	/* permission */
		}
	}

	/*
	 * Fix any ownership problems (user/group) if they exist
	 */

	if (p_mpug->vld_ug) {
		for (i=0; p_mpug->vld_ug->uids[i] != -1; ++i) {
			if (p_mpug->vld_ug->uids[i] == ps->st_uid)
				break;
		}
		if (p_mpug->vld_ug->uids[i] == -1) {
			rc = chown(p_mpug->realpath, p_mpug->vld_ug->uids[0], -1);
			if (rc) {
				snprintf(msg, sizeof(msg), "%s: ownership correction failed, %s", p_mpug->path, strerror(errno));
				put_msg_in_table(NULL, SRC_none, MSG_po, msg);
			} else {
				fixes |= 0x2;
			}
		}
	}

	if (p_mpug->vld_ug) {
		for (i=0; p_mpug->vld_ug->gids[i]; ++i) {
			if (p_mpug->vld_ug->gids[i] == ps->st_gid)
				break;
		}
		if (p_mpug->vld_ug->gids[i] == -1) {
			/*
			 * Remark: we are using the gid value "0" because
			 * on most of the systems checked the group value was
			 * this value.  On a few it was "1".
			 */
			rc = chown(p_mpug->realpath, -1, p_mpug->vld_ug->gids[0]);
			if (rc) {
				snprintf(msg, sizeof(msg), "%s: group correction failed, %s", p_mpug->path, strerror(errno));
				put_msg_in_table(NULL, SRC_none, MSG_po, msg);
			} else {
				fixes |= 0x4;
			}
		}
	}

	switch (fixes) {
		case 1:
			snprintf(msg, sizeof(msg), "%s: corrected permissions", p_mpug->path);
			put_msg_in_table(NULL, SRC_none, MSG_po, msg);
			break;

		case 2:
		case 4:
		case 6:
		  	snprintf(msg, sizeof(msg), "%s: corrected ownership(s)", p_mpug->path);
			put_msg_in_table(NULL, SRC_none, MSG_po, msg);
			break;

		case 3:
		case 5:
		case 7:
			snprintf(msg, sizeof(msg), "%s: corrected permissions and ownership(s)", p_mpug->path);
			put_msg_in_table(NULL, SRC_none, MSG_po, msg);
			break;
	}
}
// clang-format on