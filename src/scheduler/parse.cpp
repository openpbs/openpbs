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
 * @file    parse.c
 *
 * @brief
 * 	parse.c - contains functions to related to parsing the config file.
 *
 * Functions included are:
 * 	parse_config()
 * 	is_speccase_sort()
 * 	init_config()
 * 	scan()
 * 	preempt_bit_field()
 * 	preempt_cmp()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <ctype.h>
#include <log.h>
#include <libutil.h>
#include <unistd.h>
#include "data_types.h"
#include "parse.h"
#include "constant.h"
#include "config.h"
#include "misc.h"
#include "globals.h"
#include "fairshare.h"
#include "prime.h"
#include "node_info.h"
#include "resource.h"
#include "pbs_internal.h"

config::config() 
{
	prime_rr = 0;
	non_prime_rr = 0;
	prime_bq = 0;
	non_prime_bq = 0;
	prime_sf = 0;
	non_prime_sf = 0;
	prime_so = 0;
	non_prime_so = 0;
	prime_fs = 0;
	non_prime_fs = 0;
	prime_hsv = 0;
	non_prime_hsv = 0;
	prime_bf = 1;
	non_prime_bf = 1;
	prime_sn = 0;
	non_prime_sn = 0;
	prime_bp = 0;
	non_prime_bp = 0;
	prime_pre = 0;
	non_prime_pre = 0;
	update_comments = 1;
	prime_exempt_anytime_queues = 0;
	preempt_starving = 1;
	preempt_fairshare = 1;
	dont_preempt_starving = 0;
	enforce_no_shares = 1;
	node_sort_unused = 0;
	resv_conf_ignore = 0;
	allow_aoe_calendar = 0;
#ifdef NAS /* localmod 034 */
	prime_sto = 0;
	non_prime_sto = 0;
#endif /* localmod 034 */

	prime_smp_dist = SMP_NODE_PACK;
	non_prime_smp_dist = SMP_NODE_PACK;
	prime_spill = 0;
	nonprime_spill = 0;
	decay_time = 86400;
	fairshare_res = "cput";
	fairshare_ent = "euser";
	ignore_res.insert("mpiprocs");
	ignore_res.insert("ompthreads");
	memset(prime, 0, sizeof(prime));
	holiday_year = 0;			/* the year the holidays are for */
	unknown_shares = 0;			/* unknown group shares */
	max_preempt_attempts = SCHD_INFINITY;					/* max num of preempt attempts per cyc*/
	max_jobs_to_check = SCHD_INFINITY;			/* max number of jobs to check in cyc*/
	fairshare_decay_factor = .5;		/* decay factor used when decaying fairshare tree */
	max_starve = 0;
#ifdef NAS
	/* localmod 034 */
	max_borrow = 0;			/* job share borrowing limit */
	per_share_topjobs = 0;		/* per share group guaranteed top jobs*/
	/* localmod 038 */
	per_queues_topjobs = 0;		/* per queues guaranteed top jobs */
	/* localmod 030 */
	min_intrptd_cycle_length = 0;		/* min length of interrupted cycle */
	max_intrptd_cycles = 0;		/* max consecutive interrupted cycles */
#endif

	/* selection criteria of nodes for provisioning */
	provision_policy = AGGRESSIVE_PROVISION;
}


/* strtok delimiters for parsing the sched_config file are space and tab */
#define DELIM "\t "

/**
 * @brief
 * 		parse the config file into the global struct config conf
 *
 * @param[in]	fname	-	file name of the config file
 *
 * @see	GLOBAL:	conf  - config structure
 *
 * @return struct config
 * 
 * @par
 *	FILE FORMAT:
 *	config_name [white space] : [white space] config_value [prime_value]
 *	EX: sort_by: shortest_job_first prime
 */
config
parse_config(const char *fname)
{
	FILE *fp;			/* file pointer to config file */
	char *buf = NULL;
	int buf_size = 0;
	char errbuf[1024];		/* buffer for reporting errors */
	char *config_name;		/* parse first word of line */
	char *config_value;		/* parsed second word - right after colen (:) */
	char *prime_value;		/* optional third word */
	char *tok;			/* used with strtok() */
	const char *obsolete[2];		/* used to log messages for obsolete params */
	int num = -1;			/* used to convert string -> integer */
	char *endp;			/* used for strtol() */
	bool error = false;		/* boolean: is there an error? */
	enum prime_time prime;		/* used to convert string -> prime value */
	int linenum = 0;		/* the current line number in the file */
	int i;

	/* resource type for validity checking */
	struct resource_type type = {0};

	struct config tmpconf;

	if ((fp = fopen(fname, "r")) == NULL) {
		log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE,
			fname, "Can not open file: %s", fname);
		return config();
	}

#ifdef NAS
	/* localmod 034 */
	tmpconf.max_borrow = UNSPECIFIED;
	tmpconf.per_share_topjobs = 0;
	/* localmod 038 */
	tmpconf.per_queues_topjobs = 0;
	/* localmod 030 */
	tmpconf.min_intrptd_cycle_length = 30;
	tmpconf.max_intrptd_cycles = 1;
#endif

	/* auto-set any internally needed config values before reading the file */
	while (pbs_fgets_extend(&buf, &buf_size, fp) != NULL) {
		errbuf[0] = '\0';
		linenum++;
		error = false;
		obsolete[0] = obsolete[1] = NULL;
		prime = PT_ALL;
		num = -1;

		/* skip blank lines and comments */
		if (!error && !skip_line(buf)) {
			config_name = scan(buf, ':');
			config_value = scan(NULL, 0);
			prime_value = scan(NULL, 0);
			if (config_name != NULL && config_value != NULL) {
				if (strcasecmp(config_value, "true") == 0) {
					/* value is true */
					num = 1;
				} else if (strcasecmp(config_value, "false") == 0) {
					/* value is false */
					num = 0;
				} else if (isdigit((int)config_value[0])) {
					/* value is number */
					num = strtol(config_value, &endp, 10);
				}

				if (prime_value != NULL) {
					if (!strcmp(prime_value, "prime") || !strcmp(prime_value, "PRIME"))
						prime = PRIME;
					else if (!strcmp(prime_value, "non_prime") ||
						!strcmp(prime_value, "NON_PRIME"))
						prime = NON_PRIME;
					else if (!strcmp(prime_value, "all") || !strcmp(prime_value, "ALL"))
						prime = PT_ALL;
					else if (!strcmp(prime_value, "none") || !strcmp(prime_value, "NONE"))
						prime = PT_NONE;
					else {
						snprintf(errbuf, sizeof(errbuf), "Invalid prime keyword: %s", prime_value);
						error = true;
					}
				}

				if (!strcmp(config_name, PARSE_ROUND_ROBIN)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_rr = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_rr = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_BY_QUEUE)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_bq = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_bq = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_STRICT_FIFO)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_sf = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_sf = num ? 1 : 0;
					obsolete[0] = config_name;
					obsolete[1] = "strict_ordering";
				}
				else if (!strcmp(config_name, PARSE_STRICT_ORDERING)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_so = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_so = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_FAIR_SHARE)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_fs = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_fs = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_HELP_STARVING_JOBS)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_hsv = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_hsv = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_BACKFILL)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_bf = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_bf = num ? 1 : 0;

					obsolete[0] = config_name;
					obsolete[1] = "server's backfill_depth=0";
				}
				else if (!strcmp(config_name, PARSE_SORT_QUEUES)) {
					obsolete[0] = config_name;
				}
				else if (!strcmp(config_name, PARSE_UPDATE_COMMENTS)) {
					tmpconf.update_comments = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_BACKFILL_PRIME)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_bp = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_bp = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_PREEMPIVE_SCHED)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_pre = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_pre = num ? 1 : 0;
				}
				else if (!strcmp(config_name, PARSE_PRIME_EXEMPT_ANYTIME_QUEUES))
					tmpconf.prime_exempt_anytime_queues = num ? 1 : 0;
				else if (!strcmp(config_name, PARSE_PREEMPT_STARVING))
					tmpconf.preempt_starving = num ? 1 : 0;
				else if (!strcmp(config_name, PARSE_PREEMPT_FAIRSHARE))
					tmpconf.preempt_fairshare = num ? 1 : 0;
				else if (!strcmp(config_name, PARSE_DONT_PREEMPT_STARVING))
					tmpconf.dont_preempt_starving = num ? 1 : 0;
				else if (!strcmp(config_name, PARSE_ENFORCE_NO_SHARES))
					tmpconf.enforce_no_shares = num ? 1 : 0;
				else if (!strcmp(config_name, PARSE_ALLOW_AOE_CALENDAR))
					tmpconf.allow_aoe_calendar = 1;
				else if (!strcmp(config_name, PARSE_PRIME_SPILL)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_spill = res_to_num(config_value, &type);
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.nonprime_spill = res_to_num(config_value, &type);

					if (!type.is_time) {
						snprintf(errbuf, sizeof(errbuf), "Invalid time %s", config_value);
						error = true;
					}
				}
				else if (!strcmp(config_name, PARSE_MAX_STARVE)) {
					tmpconf.max_starve = res_to_num(config_value, &type);
					if (!type.is_time) {
						snprintf(errbuf, sizeof(errbuf), "Invalid time %s", config_value);
						error = true;
					}
				}
				else if (!strcmp(config_name, PARSE_HALF_LIFE) || !strcmp(config_name, PARSE_FAIRSHARE_DECAY_TIME)) {
					if(!strcmp(config_name, PARSE_HALF_LIFE)) {
						obsolete[0] = PARSE_HALF_LIFE;
						obsolete[1] = PARSE_FAIRSHARE_DECAY_TIME " and " PARSE_FAIRSHARE_DECAY_FACTOR " instead";
					}
					tmpconf.decay_time = res_to_num(config_value, &type);
					if (!type.is_time) {
						snprintf(errbuf, sizeof(errbuf), "Invalid time %s", config_value);
						error = true;
					}
				}
				else if (!strcmp(config_name, PARSE_UNKNOWN_SHARES))
					tmpconf.unknown_shares = num;
				else if (!strcmp(config_name, PARSE_FAIRSHARE_DECAY_FACTOR)) {
					float fnum;
					fnum = strtod(config_value, &endp);
					if(*endp == '\0')  {
						if (fnum <= 0 || fnum >= 1) {
							sprintf(errbuf, "%s: Invalid value: %.*f.  Valid values are between 0 and 1.", PARSE_FAIRSHARE_DECAY_FACTOR, float_digits(fnum, 2), fnum);
							error = true;
						} else
							tmpconf.fairshare_decay_factor = fnum;
					} else {
						pbs_strncpy(errbuf, "Invalid " PARSE_FAIRSHARE_DECAY_FACTOR, sizeof(errbuf));
						error = true;
					}
				}
				else if (!strcmp(config_name, PARSE_FAIRSHARE_RES)) {
					tmpconf.fairshare_res = config_value;
				}
				else if (!strcmp(config_name, PARSE_FAIRSHARE_ENT)) {
					if (strcmp(config_value, ATTR_euser) &&
						strcmp(config_value, ATTR_egroup) &&
						strcmp(config_value, ATTR_A) &&
						strcmp(config_value, "queue") &&
						strcmp(config_value, "egroup:euser")) {
						error = true;
						sprintf(errbuf, "%s %s is erroneous (or deprecated).",
							PARSE_FAIRSHARE_ENT, config_value);
					}
					tmpconf.fairshare_ent = config_value;
				}
				else if (!strcmp(config_name, PARSE_NODE_GROUP_KEY)) {
					obsolete[0] = PARSE_NODE_GROUP_KEY;
					obsolete[1] = "nothing - set via qmgr";
				}
				else if (!strcmp(config_name, PARSE_LOG_FILTER)) {
					obsolete[0] = PARSE_LOG_FILTER;
					obsolete[1] = "nothing - set log_events via qmgr";
				}
				else if (!strcmp(config_name, PARSE_PREEMPT_QUEUE_PRIO)) {
					obsolete[0] = PARSE_PREEMPT_QUEUE_PRIO;
					obsolete[1] = "nothing - set via qmgr";
				}
				else if (!strcmp(config_name, PARSE_RES_UNSET_INFINITE)) {
					char **strarr;
					
					// mpiprocs and ompthreads are added in the constructor
					strarr = break_comma_list(config_value);
					for (int i = 0; strarr[i] != NULL; i++)
						tmpconf.ignore_res.insert(strarr[i]);
					free_string_array(strarr);

				}
				else if (!strcmp(config_name, PARSE_RESV_CONFIRM_IGNORE)) {
					if (!strcmp(config_value, "dedicated_time"))
						tmpconf.resv_conf_ignore = 1;
					else if (!strcmp(config_value, "none"))
						tmpconf.resv_conf_ignore = 0;
					else {
						error = true;
						sprintf(errbuf, "%s valid values: dedicated_time or none",
							PARSE_RESV_CONFIRM_IGNORE);
					}
				}
				else if (!strcmp(config_name, PARSE_RESOURCES)) {
					bool need_host = false;
					bool need_vnode = false;
					char **strarr;
					/* hack: add in "host" into resources list because this was
					 * done by default prior to 7.1.
					 */
					if (strstr(config_value, "host") == NULL)
						need_host = true;

					/* hack: add in "vnode" in 8.0 */
					if (strstr(config_value, "vnode") == NULL)
						need_vnode = true;

					strarr = break_comma_list(config_value);
					for (int i = 0; strarr[i] != NULL; i++)
						tmpconf.res_to_check.insert(strarr[i]);
					free_string_array(strarr);

					if (need_host)
						tmpconf.res_to_check.insert("host");
					if (need_vnode)
						tmpconf.res_to_check.insert("vnode");
				} else if (!strcmp(config_name, PARSE_DEDICATED_PREFIX))
					tmpconf.ded_prefix = config_value;
				else if (!strcmp(config_name, PARSE_PRIMETIME_PREFIX))
					tmpconf.pt_prefix = config_value;
				else if (!strcmp(config_name, PARSE_NONPRIMETIME_PREFIX)) {
					tmpconf.npt_prefix = config_value;
				} else if (!strcmp(config_name, PARSE_SMP_CLUSTER_DIST)) {
					for (i = 0; i < HIGH_SMP_DIST; i++)
						if (!strcmp(smp_cluster_info[i].str, config_value)) {
							if (prime == PRIME || prime == PT_ALL)
								tmpconf.prime_smp_dist = (enum smp_cluster_dist) smp_cluster_info[i].value;
							if (prime == NON_PRIME || prime == PT_ALL)
								tmpconf.non_prime_smp_dist = (enum smp_cluster_dist) smp_cluster_info[i].value;
						}
				} else if (!strcmp(config_name, PARSE_PREEMPT_PRIO)) {
					obsolete[0] = PARSE_PREEMPT_PRIO;
					obsolete[1] = "nothing - set via qmgr";
				} else if (!strcmp(config_name, PARSE_PREEMPT_ORDER)) {
					obsolete[0] = PARSE_PREEMPT_ORDER;
					obsolete[1] = "nothing - set via qmgr";
				} else if (!strcmp(config_name, PARSE_PREEMPT_SORT)) {
					obsolete[0] = PARSE_PREEMPT_SORT;
					obsolete[1] = "nothing - set via qmgr";
				} else if (!strcmp(config_name, PARSE_JOB_SORT_KEY)) {
					sort_info si;

					tok = strtok(config_value, DELIM);

					if (tok != NULL) {
						si.res_name = tok;
						tok = strtok(NULL, DELIM);
						if (tok != NULL) {
							if (!strcmp(tok, "high") || !strcmp(tok, "HIGH") ||
								!strcmp(tok, "High")) {
								si.order = DESC;
							}
							else if (!strcmp(tok, "low") || !strcmp(tok, "LOW") ||
								!strcmp(tok, "Low")) {
								si.order = ASC;
							}
							else
								error = true;
						}
						else
							error = true;

						if (!error) {
							if (si.res_name == SORT_PRIORITY) {
								obsolete[0] = SORT_PRIORITY " in " PARSE_JOB_SORT_KEY;
								obsolete[1] = SORT_JOB_PRIORITY;
								si.res_name = SORT_JOB_PRIORITY;
							}
							if (prime == PRIME || prime == PT_ALL)
								tmpconf.prime_sort.push_back(si);

							if (prime == NON_PRIME || prime == PT_ALL)
								tmpconf.non_prime_sort.push_back(si);
						} else
							pbs_strncpy(errbuf, "Invalid job_sort_key", sizeof(errbuf));
					}
				} else if (!strcmp(config_name, PARSE_NODE_SORT_KEY)) {
					sort_info si;
					tok = strtok(config_value, DELIM);

					if (tok != NULL) {
						si.res_name = tok;
						tok = strtok(NULL, DELIM);
						if (tok != NULL) {
							if (!strcmp(tok, "high") || !strcmp(tok, "HIGH") ||
								!strcmp(tok, "High")) {
								si.order = DESC;
							}
							else if (!strcmp(tok, "low") || !strcmp(tok, "LOW") ||
								!strcmp(tok, "Low")) {
								si.order = ASC;
							}
							else
								error = true;
						}
						else
							error = true;

						if (!error) {
							tok = strtok(NULL, DELIM);
							if (tok == NULL)
								si.res_type = RF_AVAIL;
							else {
								if (!strcmp(tok, "total"))
									si.res_type = RF_AVAIL;
								else if (!strcmp(tok, "assigned"))
									si.res_type = RF_ASSN;
								else if (!strcmp(tok, "unused"))
									si.res_type = RF_UNUSED;
								else
									error = true;
							}
						}

						if (!error) {
							if (prime == PRIME || prime == PT_ALL) {
								tmpconf.prime_node_sort.push_back(si);
								if (si.res_type == RF_UNUSED || si.res_type == RF_ASSN)
									tmpconf.node_sort_unused = 1;
							}

							if (prime == NON_PRIME || prime == PT_ALL) {
								tmpconf.non_prime_node_sort.push_back(si);
								if (si.res_type == RF_UNUSED || si.res_type == RF_ASSN)
									tmpconf.node_sort_unused = 1;
							}
						} else
							pbs_strncpy(errbuf, "Invalid node_sort_key", sizeof(errbuf));
					}
				} else if (!strcmp(config_name, PARSE_SERVER_DYN_RES)) {
					char *res;
					char *command_line;
					char *filename;
					/* get the resource name */
					tok = strtok(config_value, DELIM);
					if (tok != NULL) {
						res = tok;

						/* tok is the rest of the config_value string - the program */
						tok = strtok(NULL, "");
						while (tok != NULL && isspace(*tok))
							tok++;

						if (tok != NULL && tok[0] == '!') {
							tok++;
							command_line = tok;
							filename = get_script_name(tok);
							if (filename == NULL) {
								snprintf(errbuf, sizeof(errbuf), "server_dyn_res script %s does not exist", tok);
								error = true;
							} else {
								#if !defined(DEBUG) && !defined(NO_SECURITY_CHECK)
									int err;
									err = tmp_file_sec_user(filename, 0, 1, S_IWGRP|S_IWOTH, 1, getuid());
									if (err != 0) {
										snprintf(errbuf, sizeof(errbuf),
											"error: %s file has a non-secure file access, errno: %d", filename, err);
										error = true;
									}
								#endif
								tmpconf.dynamic_res.emplace_back(res, command_line, filename);
								free(filename);
							}
						}
						else {
							pbs_strncpy(errbuf, "Invalid server_dyn_res", sizeof(errbuf));
							error = true;
						}
					}
					else {
						pbs_strncpy(errbuf, "Invalid server_dyn_res", sizeof(errbuf));
						error = true;
					}
				} else if (!strcmp(config_name, PARSE_SORT_NODES)) {
					obsolete[0] = config_name;
					obsolete[1] = PARSE_NODE_SORT_KEY;
					sort_info si;

					si.res_name = SORT_PRIORITY;
					si.order = DESC;

					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_node_sort.push_back(si);
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_node_sort.push_back(si);
				} else if (!strcmp(config_name, PARSE_PEER_QUEUE)) {
					const char *lqueue;
					const char *rqueue;
					const char *rserver;
					lqueue = strtok(config_value, DELIM);
					if (lqueue != NULL) {
						rqueue = strtok(NULL, "@");
						if (rqueue != NULL) {
							while (isspace(*rqueue)) rqueue++;
							rserver = strtok(NULL, DELIM);
							if (rserver == NULL)
								rserver = "";
							if (!error)
								tmpconf.peer_queues.emplace_back(lqueue, rqueue, rserver);

						} else
							error = true;
					} else
						error = true;

					if (error)
						sprintf(errbuf, "Invalid peer queue");

				} else if (!strcmp(config_name, PARSE_PREEMPT_ATTEMPTS))
					tmpconf.max_preempt_attempts = num;
				else if (!strcmp(config_name, PARSE_MAX_JOB_CHECK)) {
					if (!strcmp(config_value, "ALL_JOBS"))
						tmpconf.max_jobs_to_check = SCHD_INFINITY;
					else
						tmpconf.max_jobs_to_check = num;
				} else if (!strcmp(config_name, PARSE_SELECT_PROVISION)) {
					if (!strcmp(config_value, PROVPOLICY_AVOID))
						tmpconf.provision_policy = AVOID_PROVISION;
				}
#ifdef NAS
				/* localmod 034 */
				else if (!strcmp(config_name, PARSE_MAX_BORROW)) {
					tmpconf.max_borrow = res_to_num(config_value, &type);
					if (!type.is_time)
						error = true;
				} else if (!strcmp(config_name, PARSE_SHARES_TRACK_ONLY)) {
					if (prime == PRIME || prime == PT_ALL)
						tmpconf.prime_sto = num ? 1 : 0;
					if (prime == NON_PRIME || prime == PT_ALL)
						tmpconf.non_prime_sto = num ? 1 : 0;
				} else if (!strcmp(config_name, PARSE_PER_SHARE_DEPTH) ||
					   !strcmp(config_name, PARSE_PER_SHARE_TOPJOBS)) {
					tmpconf.per_share_topjobs = num;
				}
				/* localmod 038 */
				else if (!strcmp(config_name, PARSE_PER_QUEUES_TOPJOBS)) {
					tmpconf.per_queues_topjobs = num;
				}
				/* localmod 030 */
				else if (!strcmp(config_name, PARSE_MIN_INTERRUPTED_CYCLE_LENGTH)) {
					tmpconf.min_intrptd_cycle_length = num;
				} else if (!strcmp(config_name, PARSE_MAX_CONS_INTERRUPTED_CYCLES)) {
					tmpconf.max_intrptd_cycles = num;
				}
#endif
				else {
					pbs_strncpy(errbuf, "Unknown config parameter", sizeof(errbuf));
					error = true;
				}
			} else {
				pbs_strncpy(errbuf, "Config line invalid", sizeof(errbuf));
				error = true;
			}
		}

		if (error)
			log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, fname,
				"Error reading line %d: %s", linenum, errbuf);

		if (obsolete[0] != NULL) {
			if (obsolete[1] != NULL)
				log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, fname,
					"Obsolete config name %s, instead use %s", obsolete[0], obsolete[1]);
			else
				log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, fname,
					"Obsolete config name %s", obsolete[0]);
		}
	}
	fclose(fp);

	if (buf != NULL)
		free(buf);

	if ((tmpconf.prime_smp_dist != SMP_NODE_PACK || tmpconf.non_prime_smp_dist != SMP_NODE_PACK) && tmpconf.node_sort_unused) {
		log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_WARNING, "", "smp_cluster_dist and node sorting by unused/assigned resources are not compatible.  The smp_cluster_dist option is being set to pack.");
		tmpconf.prime_smp_dist = tmpconf.non_prime_smp_dist = SMP_NODE_PACK;
	}

	return tmpconf;
}

/**
 * @brief
 * 		Check if sort_res is a valid special case sorting string
 *
 * @param[in]	sort_res	-	sorting keyword
 * @param[in]	sort_type	-	sorting object type (job or node)
 *
 * @return	int
 * @retval	1	: is special case sort
 * @retval	0	: not special case sort
 */
int is_speccase_sort(const std::string& sort_res, int sort_type) {
	if (sort_type == SOBJ_JOB) {
		if (sort_res == SORT_JOB_PRIORITY)
			return 1;
#ifdef NAS
		/* localmod 034 */
		if (sort_res == SORT_ALLOC)
			return 1;
		/* localmod 039 */
		if (sort_res == SORT_QPRI)
			return 1;
#endif
		else
			return 0;
	} else if (sort_type == SOBJ_NODE) {
		if (sort_res == SORT_PRIORITY || sort_res == SORT_FAIR_SHARE || sort_res == SORT_PREEMPT)
			return 1;
		else
			return 0;
	}

	return 0;
}

/**
 * @brief
 *		scan - Scan through the string looking for a white space delimited
 *	       word or quoted string.  If the target parameter is not 0, then
 *	       use that as a delimiter as well.
 *
 * @param[in]	str	-	the string to scan through.  If NULL, start where we left
 *		   				off last time.
 * @param[in]	target	-	if target is 0, set it to a space.  It is already a delimiter
 *
 * @return	scanned string or NULL
 *
 */
char *
scan(char *str, char target)
{
	static char *isp = NULL;	/* internal state pointer used if a NULL is
					 * passed in to str
					 */
	char *ptr;			/* pointer used to search through the str */
	char quote;			/* pointer used to store the quote ' or " */
	char *start;

	if (str == NULL && isp == NULL)
		return NULL;

	if (str == NULL)
		ptr = isp;
	else
		ptr = str;

	/* if target is 0, set it to a space.  It is already a delimiter */
	if (target == 0)
		target = ' ';

	while (isspace(*ptr) || *ptr == target) ptr++;

	start = ptr;

	if (*ptr != '\0') {
		if (*ptr == '\"' || *ptr == '\'') {
			quote = *ptr;
			start = ++ptr;
			while (*ptr != '\0' && *ptr != quote)
				ptr++;
		}
		else {
			while (*ptr != '\0' && !isspace(*ptr) && *ptr != target)
				ptr++;
		}
		if (*ptr == '\0')
			isp = NULL;
		else {
			*ptr = '\0';
			isp = ptr + 1;
		}
		return start;
	}

	isp = NULL;
	return NULL;
}

/**
 * @brief
 *		preempt_bit_field - take list of preempt names seperated by +'s and
 * 			    create a bitfield representing it.  The bitfield
 *			    is created by taking the name in the prempt enum
 *			    and shifting a bit into that position.
 *
 * @param[in]	plist	-	a preempt list
 *
 * @return	a bitfield of -1 on error
 *
 */
int
preempt_bit_field(char *plist)
{
	int bitfield = 0;
	int obitfield;
	int i;
	char *tok;

	tok = strtok(plist, "+");

	while (tok != NULL) {
		obitfield = bitfield;
		for (i = 0; i < PREEMPT_HIGH; i++) {
			if (!strcmp(preempt_prio_info[i].str, tok))
				bitfield |= PREEMPT_TO_BIT(preempt_prio_info[i].value);
		}

		/* invalid preempt string */
		if (obitfield == bitfield) {
			bitfield = -1;
			break;
		}

		tok = strtok(NULL, "+");
	}

	return bitfield;
}

/**
 * @brief
 * 	sort compare function for preempt status's
 * 	sort by descending number of bits in the bitfields (most number of preempt
 * 	statuses at the top) and then priorities
 *
 * @param[in]	p1	-	preempt status 1
 * @param[in]	p2	-	preempt status 2
 *
 * @return	int
 * @retval	1	: p1 < p2
 * @retval	-1	: p1 > p2
 * @retval	0	: Equal
 */
int
preempt_cmp(const void *p1, const void *p2)
{
	int *i1, *i2;

	i1 = (int *) p1;
	i2 = (int *) p2;

	if (BITCOUNT16(*i1) < BITCOUNT16(*i2))
		return 1;
	else if (BITCOUNT16(*i1) > BITCOUNT16(*i2))
		return -1;
	else {
		if (*(i1+1) < *(i2+1))
			return 1;
		else if (*(i1+1) > *(i2+1))
			return -1;
		else
			return 0;
	}
}