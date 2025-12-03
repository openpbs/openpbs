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
 * @file	pbs_loadconf.c
 */
#include <pbs_config.h>
#include <ctype.h>
#include <sys/types.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <netdb.h>
#include <pbs_ifl.h>
#include <pwd.h>
#include <pthread.h>
#include "pbs_internal.h"
#include <limits.h>
#include <pbs_error.h>
#include "pbs_client_thread.h"
#include "net_connect.h"
#include "portability.h"
#include "cmds.h"

#include <sys/stat.h>
#include <unistd.h>

#ifndef WIN32
#define shorten_and_cleanup_path(p) strdup(p)
#endif

char *pbs_conf_env = "PBS_CONF_FILE";

static char *pbs_loadconf_buf = NULL;
static int pbs_loadconf_len = 0;

/*
 * Initialize the pbs_conf structure.
 *
 * The order of elements must be kept in sync with the pbs_config
 * structure definition in src/include/pbs_internal.h
 */
struct pbs_config pbs_conf = {
	0,			    /* loaded */
	0,			    /* load_failed */
	0,			    /* start_server */
	0,			    /* start_mom */
	0,			    /* start_sched */
	0,			    /* start comm */
	0,			    /* locallog */
	NULL,			    /* default to NULL for supported auths */
	NULL,			    /* auth service users list, will default to just "root" if not set explicitly */
	{'\0'},			    /* default no auth method to encrypt/decrypt data */
	AUTH_RESVPORT_NAME,	    /* default to reserved port authentication */
	AUTH_RESVPORT_NAME,	    /* default to reserved port qsub -I authentication. Possible values: resvport, munge */
	{'\0'},			    /* default no method to encrypt/decrypt data in an interatcive job */
	0,			    /* sched_modify_event */
	0,			    /* syslogfac */
	3,			    /* syslogsvr - LOG_ERR from syslog.h */
	PBS_BATCH_SERVICE_PORT,	    /* batch_service_port */
	PBS_BATCH_SERVICE_PORT_DIS, /* batch_service_port_dis */
	PBS_MOM_SERVICE_PORT,	    /* mom_service_port */
	PBS_MANAGER_SERVICE_PORT,   /* manager_service_port */
	PBS_DATA_SERVICE_PORT,	    /* pbs data service port */
	NULL,			    /* pbs_conf_file */
	NULL,			    /* pbs_home_path */
	NULL,			    /* pbs_exec_path */
	NULL,			    /* pbs_server_name */
	NULL,			    /* cp_path */
	NULL,			    /* scp_path */
	NULL,			    /* scp_args */
	NULL,			    /* rcp_path */
	NULL,			    /* pbs_demux_path */
	NULL,			    /* pbs_environment */
	NULL,			    /* iff_path */
	NULL,			    /* primary name   */
	NULL,			    /* secondary name */
	NULL,			    /* aux Mom home   */
	NULL,			    /* pbs_core_limit */
	NULL,			    /* default database host  */
	NULL,			    /* pbs_tmpdir */
	NULL,			    /* pbs_server_host_name */
	NULL,			    /* pbs_public_host_name */
	NULL,			    /* pbs_mail_host_name */
	NULL,			    /* pbs_output_host_name */
	NULL,			    /* pbs_smtp_server_name */
	1,			    /* use compression by default with TCP */
	1,			    /* use mcast by default with TCP */
	NULL,			    /* default leaf name */
	NULL,			    /* for leaf, default communication routers list */
	NULL,			    /* default router name */
	NULL,			    /* for router, default communication routers list */
	0,			    /* default comm logevent mask */
	4,			    /* default number of threads */
	NULL,			    /* mom short name override */
	0,			    /* high resolution timestamp logging */
	0,			    /* number of scheduler threads */
	NULL,			    /* default scheduler user */
	NULL,			    /* default scheduler auth user */
	NULL,			    /* privileged auth user */
	NULL,			    /* path to user credentials program */
	{'\0'}			    /* current running user */
#ifdef WIN32
	,
	NULL /* remote viewer launcher executable along with launch options */
#endif
};

/**
 * @brief
 *	identify_service_entry - Maps a service name to a variable location in pbs_conf
 *
 * @par
 *	Calls to getservbyname() are expensive. Instead we want to parse the
 *	service entries using getsrvent(). This static function is used to
 *	map a service name (or alias) to the proper location in the pbs_conf
 *	structure defined above.
 *
 * @param[in] name	The name of the service being parsed
 *
 * @return unsigned int *
 * @retval !NULL for success
 * @retval NULL for not found
 */
static unsigned int *
identify_service_entry(char *name)
{
	unsigned int *p = NULL;
	if ((name == NULL) || (*name == '\0'))
		return NULL;
	if (strcmp(name, PBS_BATCH_SERVICE_NAME) == 0) {
		p = &pbs_conf.batch_service_port;
	} else if (strcmp(name, PBS_BATCH_SERVICE_NAME_DIS) == 0) {
		p = &pbs_conf.batch_service_port_dis;
	} else if (strcmp(name, PBS_MOM_SERVICE_NAME) == 0) {
		p = &pbs_conf.mom_service_port;
	} else if (strcmp(name, PBS_MANAGER_SERVICE_NAME) == 0) {
		p = &pbs_conf.manager_service_port;
	} else if (strcmp(name, PBS_DATA_SERVICE_NAME) == 0) {
		p = &pbs_conf.pbs_data_service_port;
	}
	return p;
}

/**
 * @brief
 *	pbs_get_conf_file - Identify the configuration file location
 *
 * @return char *
 * @retval !NULL pointer to the configuration file name
 * @retval NULL should never be returned
 */
static char *
pbs_get_conf_file(void)
{
	char *conf_file;

	/* If pbs_conf already been populated use that value. */
	if ((pbs_conf.loaded != 0) && (pbs_conf.pbs_conf_file != NULL))
		return (pbs_conf.pbs_conf_file);

	if (pbs_conf_env == NULL) {
		if ((conf_file = getenv("PBS_CONF_FILE")) == NULL)
			conf_file = PBS_CONF_FILE;
	} else {
		if ((conf_file = getenv(pbs_conf_env)) == NULL)
			conf_file = PBS_CONF_FILE;
	}
	return (shorten_and_cleanup_path(conf_file));
}

/**
 * @brief
 *	parse_config_line - Read and parse one line of the pbs.conf file
 *
 * @param[in] fp	File pointer to use for reading
 * @param[in/out] key	Pointer to variable name pointer
 * @param[in/out] val	Pointer to variable value pointer
 *
 * @return int
 * @retval !NULL Input remains
 * @retval NULL End of input
 */
static char *
parse_config_line(FILE *fp, char **key, char **val)
{
	char *start;
	char *end;
	char *split;
	char *ret;

	*key = "";
	*val = "";

	/* Use a do-while rather than a goto. */
	do {
		int len;

		ret = pbs_fgets(&pbs_loadconf_buf, &pbs_loadconf_len, fp);
		if (ret == NULL)
			break;
		len = strlen(pbs_loadconf_buf);
		if (len < 1)
			break;
		/* Advance the start pointer past any whitespace. */
		for (start = pbs_loadconf_buf; (*start != '\0') && isspace((int) *start); start++)
			;
		/* Is this a comment line. */
		if (*start == '#')
			break;
		/* Remove whitespace from the end. */
		for (end = pbs_loadconf_buf + len - 1; (end >= start) && isspace((int) *end); end--)
			*end = '\0';
		/* Was there nothing but white space? */
		if (start >= end)
			break;
		split = strchr(start, '=');
		if (split == NULL)
			break;
		*key = start;
		*split++ = '\0';
		*val = split;
	} while (0);

	return ret;
}

/**
 * @brief
 *	pbs_loadconf - Populate the pbs_conf structure
 *
 * @par
 *	Load the pbs_conf structure.  The variables can be filled in
 *	from either the environment or the pbs.conf file.  The
 *	environment gets priority over the file.  If any of the
 *	primary variables are not filled in, the function fails.
 *	Primary vars: pbs_home_path, pbs_exec_path, pbs_server_name
 *
 * @note
 *	Clients can now be multithreaded. So dont call pbs_loadconf with
 *	reload = TRUE. Currently, the code flow ensures that the configuration
 *	is loaded only once (never used with reload true). Thus in the rest of
 *	the code a direct read of the pbs_conf.variables is fine. There is no
 *	race of access of pbs_conf vars against the loading of pbs_conf vars.
 *	However, if pbs_loadconf is called with reload = TRUE, this assumption
 *	will be void. In that case, access to every pbs_conf.variable has to be
 *	synchronized against the reload of those variables.
 *
 * @param[in] reload	Whether to attempt a reload
 *
 * @return int
 * @retval 1 Success
 * @retval 0 Failure
 */
int
__pbs_loadconf(int reload)
{
	FILE *fp;
	char buf[256];
	char *conf_name;     /* the name of the conf parameter */
	char *conf_value;    /* the value from the conf file or env*/
	char *gvalue;	     /* used with getenv() */
	unsigned int uvalue; /* used with sscanf() */
	struct passwd *pw;
	uid_t pbs_current_uid;
#ifndef WIN32
	struct servent *servent; /* for use with getservent */
	char **servalias;	 /* service alias list */
	unsigned int *pui;	 /* for use with identify_service_entry */
#endif

	/* initialize the thread context data, if not already initialized */
	if (pbs_client_thread_init_thread_context() != 0)
		return 0;

	/* this section of the code modified the procecss-wide
	 * tcp array. Since multiple threads can get into this
	 * simultaneously, we need to serialize it
	 */
	if (pbs_client_thread_lock_conf() != 0)
		return 0;

	if (pbs_conf.loaded && !reload) {
		(void) pbs_client_thread_unlock_conf();
		return 1;
	} else if (pbs_conf.load_failed && !reload) {
		(void) pbs_client_thread_unlock_conf();
		return 0;
	}

	/*
	 * If there are service port definitions available, use them
	 * as the defaults. They may be overridden later by the config
	 * file or environment variables. If not available, retain
	 * whatever we were using before.
	 */
#ifdef WIN32
	/* Windows does not have the getservent() call. */
	pbs_conf.batch_service_port = get_svrport(
		PBS_BATCH_SERVICE_NAME, "tcp",
		pbs_conf.batch_service_port);
	pbs_conf.batch_service_port_dis = get_svrport(
		PBS_BATCH_SERVICE_NAME_DIS, "tcp",
		pbs_conf.batch_service_port_dis);
	pbs_conf.mom_service_port = get_svrport(
		PBS_MOM_SERVICE_NAME, "tcp",
		pbs_conf.mom_service_port);
	pbs_conf.manager_service_port = get_svrport(
		PBS_MANAGER_SERVICE_NAME, "tcp",
		pbs_conf.manager_service_port);
	pbs_conf.pbs_data_service_port = get_svrport(
		PBS_DATA_SERVICE_NAME, "tcp",
		pbs_conf.pbs_data_service_port);
#else
	/* Non-Windows uses getservent() for better performance. */
	while ((servent = getservent()) != NULL) {
		if (strcmp(servent->s_proto, "tcp") != 0)
			continue;
		/* First, check the official service name. */
		pui = identify_service_entry(servent->s_name);
		if (pui != NULL) {
			*pui = (unsigned int) ntohs(servent->s_port);
			continue;
		}
		/* Next, check any aliases that may be defined. */
		for (servalias = servent->s_aliases; (servalias != NULL) && (*servalias != NULL); servalias++) {
			pui = identify_service_entry(*servalias);
			if (pui != NULL) {
				*pui = (unsigned int) ntohs(servent->s_port);
				break;
			}
		}
	}
	endservent();
#endif

	/*
	 * Once we determine the location of the pbs.conf file, it never changes.
	 * The fact that it is saved to the pbs_conf global structure means that
	 * we can always see its location when debugging.
	 */
	if (pbs_conf.pbs_conf_file == NULL)
		pbs_conf.pbs_conf_file = pbs_get_conf_file();

	/*
	 * Parse through the configuration file and set variables based
	 * on the contents of the file.
	 */
	if ((fp = fopen(pbs_conf.pbs_conf_file, "r")) != NULL) {
		while (parse_config_line(fp, &conf_name, &conf_value) != NULL) {
			if ((conf_name == NULL) || (*conf_name == '\0'))
				continue;

			if (!strcmp(conf_name, PBS_CONF_START_SERVER)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.start_server = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_START_MOM)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.start_mom = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_START_SCHED)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.start_sched = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_START_COMM)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.start_comm = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_LOCALLOG)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.locallog = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_SYSLOG)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.syslogfac = ((uvalue <= (23 << 3)) ? uvalue : 0);
			} else if (!strcmp(conf_name, PBS_CONF_SYSLOGSEVR)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.syslogsvr = ((uvalue <= 7) ? uvalue : 0);
			} else if (!strcmp(conf_name, PBS_CONF_BATCH_SERVICE_PORT)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.batch_service_port =
						((uvalue <= 65535) ? uvalue : pbs_conf.batch_service_port);
			} else if (!strcmp(conf_name, PBS_CONF_BATCH_SERVICE_PORT_DIS)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.batch_service_port_dis =
						((uvalue <= 65535) ? uvalue : pbs_conf.batch_service_port_dis);
			} else if (!strcmp(conf_name, PBS_CONF_MOM_SERVICE_PORT)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.mom_service_port =
						((uvalue <= 65535) ? uvalue : pbs_conf.mom_service_port);
			} else if (!strcmp(conf_name, PBS_CONF_MANAGER_SERVICE_PORT)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.manager_service_port =
						((uvalue <= 65535) ? uvalue : pbs_conf.manager_service_port);
			} else if (!strcmp(conf_name, PBS_CONF_DATA_SERVICE_PORT)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.pbs_data_service_port =
						((uvalue <= 65535) ? uvalue : pbs_conf.pbs_data_service_port);
			} else if (!strcmp(conf_name, PBS_CONF_DATA_SERVICE_HOST)) {
				free(pbs_conf.pbs_data_service_host);
				pbs_conf.pbs_data_service_host = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_USE_COMPRESSION)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.pbs_use_compression = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_USE_MCAST)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.pbs_use_mcast = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_LEAF_NAME)) {
				if (pbs_conf.pbs_leaf_name)
					free(pbs_conf.pbs_leaf_name);
				pbs_conf.pbs_leaf_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_LEAF_ROUTERS)) {
				if (pbs_conf.pbs_leaf_routers)
					free(pbs_conf.pbs_leaf_routers);
				pbs_conf.pbs_leaf_routers = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_COMM_NAME)) {
				if (pbs_conf.pbs_comm_name)
					free(pbs_conf.pbs_comm_name);
				pbs_conf.pbs_comm_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_COMM_ROUTERS)) {
				if (pbs_conf.pbs_comm_routers)
					free(pbs_conf.pbs_comm_routers);
				pbs_conf.pbs_comm_routers = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_COMM_THREADS)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.pbs_comm_threads = uvalue;
			} else if (!strcmp(conf_name, PBS_CONF_COMM_LOG_EVENTS)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.pbs_comm_log_events = uvalue;
			} else if (!strcmp(conf_name, PBS_CONF_HOME)) {
				free(pbs_conf.pbs_home_path);
				pbs_conf.pbs_home_path = shorten_and_cleanup_path(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_EXEC)) {
				free(pbs_conf.pbs_exec_path);
				pbs_conf.pbs_exec_path = shorten_and_cleanup_path(conf_value);
			}
			/* Check for PBS_DEFAULT for backward compatibility */
			else if (!strcmp(conf_name, PBS_CONF_DEFAULT_NAME)) {
				free(pbs_conf.pbs_server_name);
				pbs_conf.pbs_server_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_SERVER_NAME)) {
				free(pbs_conf.pbs_server_name);
				pbs_conf.pbs_server_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_RCP)) {
				free(pbs_conf.rcp_path);
				pbs_conf.rcp_path = shorten_and_cleanup_path(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_SCP)) {
				free(pbs_conf.scp_path);
				pbs_conf.scp_path = shorten_and_cleanup_path(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_SCP_ARGS)) {
				free(pbs_conf.scp_args);
				pbs_conf.scp_args = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_CP)) {
				free(pbs_conf.cp_path);
				pbs_conf.cp_path = shorten_and_cleanup_path(conf_value);
			}
			/* rcp_path can be inferred from pbs_conf.pbs_exec_path - see below */
			/* pbs_demux_path is inferred from pbs_conf.pbs_exec_path - see below */
			else if (!strcmp(conf_name, PBS_CONF_ENVIRONMENT)) {
				free(pbs_conf.pbs_environment);
				pbs_conf.pbs_environment = shorten_and_cleanup_path(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_PRIMARY)) {
				free(pbs_conf.pbs_primary);
				pbs_conf.pbs_primary = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_SECONDARY)) {
				free(pbs_conf.pbs_secondary);
				pbs_conf.pbs_secondary = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_MOM_HOME)) {
				free(pbs_conf.pbs_mom_home);
				pbs_conf.pbs_mom_home = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_CORE_LIMIT)) {
				free(pbs_conf.pbs_core_limit);
				pbs_conf.pbs_core_limit = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_SERVER_HOST_NAME)) {
				free(pbs_conf.pbs_server_host_name);
				pbs_conf.pbs_server_host_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_PUBLIC_HOST_NAME)) {
				free(pbs_conf.pbs_public_host_name);
				pbs_conf.pbs_public_host_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_MAIL_HOST_NAME)) {
				free(pbs_conf.pbs_mail_host_name);
				pbs_conf.pbs_mail_host_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_SMTP_SERVER_NAME)) {
				free(pbs_conf.pbs_smtp_server_name);
				pbs_conf.pbs_smtp_server_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_OUTPUT_HOST_NAME)) {
				free(pbs_conf.pbs_output_host_name);
				pbs_conf.pbs_output_host_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_SCHEDULER_MODIFY_EVENT)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.sched_modify_event = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_MOM_NODE_NAME)) {
				free(pbs_conf.pbs_mom_node_name);
				pbs_conf.pbs_mom_node_name = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_LOG_HIGHRES_TIMESTAMP)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.pbs_log_highres_timestamp = ((uvalue > 0) ? 1 : 0);
			} else if (!strcmp(conf_name, PBS_CONF_SCHED_THREADS)) {
				if (sscanf(conf_value, "%u", &uvalue) == 1)
					pbs_conf.pbs_sched_threads = uvalue;
			}
#ifdef WIN32
			else if (!strcmp(conf_name, PBS_CONF_REMOTE_VIEWER)) {
				free(pbs_conf.pbs_conf_remote_viewer);
				pbs_conf.pbs_conf_remote_viewer = strdup(conf_value);
			}
#endif
			else if (!strcmp(conf_name, PBS_CONF_INTERACTIVE_AUTH_METHOD)) {
				char *value = convert_string_to_lowercase(conf_value);
				if (value == NULL)
					goto err;
				memset(pbs_conf.interactive_auth_method, '\0', sizeof(pbs_conf.interactive_auth_method));
				strcpy(pbs_conf.interactive_auth_method, value);
				free(value);
			} else if (!strcmp(conf_name, PBS_CONF_INTERACTIVE_ENCRYPT_METHOD)) {
				char *value = convert_string_to_lowercase(conf_value);
				if (value == NULL)
					goto err;
				memset(pbs_conf.interactive_encrypt_method, '\0', sizeof(pbs_conf.interactive_encrypt_method));
				strcpy(pbs_conf.interactive_encrypt_method, value);
				free(value);
			} else if (!strcmp(conf_name, PBS_CONF_AUTH)) {
				char *value = convert_string_to_lowercase(conf_value);
				if (value == NULL)
					goto err;
				memset(pbs_conf.auth_method, '\0', sizeof(pbs_conf.auth_method));
				strcpy(pbs_conf.auth_method, value);
				free(value);
			} else if (!strcmp(conf_name, PBS_CONF_ENCRYPT_METHOD)) {
				char *value = convert_string_to_lowercase(conf_value);
				if (value == NULL)
					goto err;
				memset(pbs_conf.encrypt_method, '\0', sizeof(pbs_conf.encrypt_method));
				strcpy(pbs_conf.encrypt_method, value);
				free(value);
			} else if (!strcmp(conf_name, PBS_CONF_SUPPORTED_AUTH_METHODS)) {
				char *value = convert_string_to_lowercase(conf_value);
				if (value == NULL)
					goto err;
				pbs_conf.supported_auth_methods = break_comma_list(value);
				if (pbs_conf.supported_auth_methods == NULL) {
					free(value);
					goto err;
				}
				free(value);
			} else if (!strcmp(conf_name, PBS_CONF_AUTH_SERVICE_USERS)) {
				pbs_conf.auth_service_users = break_comma_list(conf_value);
				if (pbs_conf.auth_service_users == NULL) {
					goto err;
				}
			} else if (!strcmp(conf_name, PBS_CONF_DAEMON_SERVICE_USER)) {
				free(pbs_conf.pbs_daemon_service_user);
				pbs_conf.pbs_daemon_service_user = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_DAEMON_SERVICE_AUTH_USER)) {
				free(pbs_conf.pbs_daemon_service_auth_user);
				pbs_conf.pbs_daemon_service_auth_user = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_PRIVILEGED_AUTH_USER)) {
				free(pbs_conf.pbs_privileged_auth_user);
				pbs_conf.pbs_privileged_auth_user = strdup(conf_value);
			} else if (!strcmp(conf_name, PBS_CONF_GSS_USER_CREDENTIALS_BIN)) {
				free(pbs_conf.pbs_gss_user_creds_bin);
				pbs_conf.pbs_gss_user_creds_bin = strdup(conf_value);
			}
			/* iff_path is inferred from pbs_conf.pbs_exec_path - see below */
		}
		fclose(fp);
		free(pbs_loadconf_buf);
		pbs_loadconf_buf = NULL;
		pbs_loadconf_len = 0;
	}

	/*
	 * Next, check the environment variables and set values accordingly
	 * overriding those that were set in the configuration file.
	 */

	if ((gvalue = getenv(PBS_CONF_START_SERVER)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.start_server = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_START_MOM)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.start_mom = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_START_SCHED)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.start_sched = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_START_COMM)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.start_comm = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_LOCALLOG)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.locallog = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_SYSLOG)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.syslogfac = ((uvalue <= (23 << 3)) ? uvalue : 0);
	}
	if ((gvalue = getenv(PBS_CONF_SYSLOGSEVR)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.syslogsvr = ((uvalue <= 7) ? uvalue : 0);
	}
	if ((gvalue = getenv(PBS_CONF_BATCH_SERVICE_PORT)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.batch_service_port =
				((uvalue <= 65535) ? uvalue : pbs_conf.batch_service_port);
	}
	if ((gvalue = getenv(PBS_CONF_BATCH_SERVICE_PORT_DIS)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.batch_service_port_dis =
				((uvalue <= 65535) ? uvalue : pbs_conf.batch_service_port_dis);
	}
	if ((gvalue = getenv(PBS_CONF_MOM_SERVICE_PORT)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.mom_service_port =
				((uvalue <= 65535) ? uvalue : pbs_conf.mom_service_port);
	}
	if ((gvalue = getenv(PBS_CONF_MANAGER_SERVICE_PORT)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.manager_service_port =
				((uvalue <= 65535) ? uvalue : pbs_conf.manager_service_port);
	}
	if ((gvalue = getenv(PBS_CONF_HOME)) != NULL) {
		free(pbs_conf.pbs_home_path);
		pbs_conf.pbs_home_path = shorten_and_cleanup_path(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_EXEC)) != NULL) {
		free(pbs_conf.pbs_exec_path);
		pbs_conf.pbs_exec_path = shorten_and_cleanup_path(gvalue);
	}
	/* Check for PBS_DEFAULT for backward compatibility */
	if ((gvalue = getenv(PBS_CONF_DEFAULT_NAME)) != NULL) {
		free(pbs_conf.pbs_server_name);
		if ((pbs_conf.pbs_server_name = strdup(gvalue)) == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_SERVER_NAME)) != NULL) {
		free(pbs_conf.pbs_server_name);
		if ((pbs_conf.pbs_server_name = strdup(gvalue)) == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_RCP)) != NULL) {
		free(pbs_conf.rcp_path);
		pbs_conf.rcp_path = shorten_and_cleanup_path(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_SCP)) != NULL) {
		free(pbs_conf.scp_path);
		pbs_conf.scp_path = shorten_and_cleanup_path(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_SCP_ARGS)) != NULL) {
		free(pbs_conf.scp_args);
		pbs_conf.scp_args = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_CP)) != NULL) {
		free(pbs_conf.cp_path);
		pbs_conf.cp_path = shorten_and_cleanup_path(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_PRIMARY)) != NULL) {
		free(pbs_conf.pbs_primary);
		if ((pbs_conf.pbs_primary = strdup(gvalue)) == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_SECONDARY)) != NULL) {
		free(pbs_conf.pbs_secondary);
		if ((pbs_conf.pbs_secondary = strdup(gvalue)) == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_MOM_HOME)) != NULL) {
		free(pbs_conf.pbs_mom_home);
		if ((pbs_conf.pbs_mom_home = strdup(gvalue)) == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_CORE_LIMIT)) != NULL) {
		free(pbs_conf.pbs_core_limit);
		if ((pbs_conf.pbs_core_limit = strdup(gvalue)) == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_DATA_SERVICE_HOST)) != NULL) {
		free(pbs_conf.pbs_data_service_host);
		if ((pbs_conf.pbs_data_service_host = strdup(gvalue)) == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_USE_COMPRESSION)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.pbs_use_compression = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_USE_MCAST)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.pbs_use_mcast = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_LEAF_NAME)) != NULL) {
		if (pbs_conf.pbs_leaf_name)
			free(pbs_conf.pbs_leaf_name);
		pbs_conf.pbs_leaf_name = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_LEAF_ROUTERS)) != NULL) {
		if (pbs_conf.pbs_leaf_routers)
			free(pbs_conf.pbs_leaf_routers);
		pbs_conf.pbs_leaf_routers = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_COMM_NAME)) != NULL) {
		if (pbs_conf.pbs_comm_name)
			free(pbs_conf.pbs_comm_name);
		pbs_conf.pbs_comm_name = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_COMM_ROUTERS)) != NULL) {
		if (pbs_conf.pbs_comm_routers)
			free(pbs_conf.pbs_comm_routers);
		pbs_conf.pbs_comm_routers = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_COMM_THREADS)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.pbs_comm_threads = uvalue;
	}
	if ((gvalue = getenv(PBS_CONF_COMM_LOG_EVENTS)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.pbs_comm_log_events = uvalue;
	}
	if ((gvalue = getenv(PBS_CONF_DATA_SERVICE_PORT)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.pbs_data_service_port =
				((uvalue <= 65535) ? uvalue : pbs_conf.pbs_data_service_port);
	}
	if ((gvalue = getenv(PBS_CONF_SERVER_HOST_NAME)) != NULL) {
		free(pbs_conf.pbs_server_host_name);
		pbs_conf.pbs_server_host_name = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_PUBLIC_HOST_NAME)) != NULL) {
		free(pbs_conf.pbs_public_host_name);
		pbs_conf.pbs_public_host_name = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_MAIL_HOST_NAME)) != NULL) {
		free(pbs_conf.pbs_mail_host_name);
		pbs_conf.pbs_mail_host_name = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_SMTP_SERVER_NAME)) != NULL) {
		free(pbs_conf.pbs_smtp_server_name);
		pbs_conf.pbs_smtp_server_name = strdup(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_OUTPUT_HOST_NAME)) != NULL) {
		free(pbs_conf.pbs_output_host_name);
		pbs_conf.pbs_output_host_name = strdup(gvalue);
	}

	/* support PBS_MOM_NODE_NAME to tell MOM natural node name on server */
	if ((gvalue = getenv(PBS_CONF_MOM_NODE_NAME)) != NULL) {
		free(pbs_conf.pbs_mom_node_name);
		pbs_conf.pbs_mom_node_name = strdup(gvalue);
	}

	/* rcp_path is inferred from pbs_conf.pbs_exec_path - see below */
	/* pbs_demux_path is inferred from pbs_conf.pbs_exec_path - see below */
	if ((gvalue = getenv(PBS_CONF_ENVIRONMENT)) != NULL) {
		free(pbs_conf.pbs_environment);
		pbs_conf.pbs_environment = shorten_and_cleanup_path(gvalue);
	}
	if ((gvalue = getenv(PBS_CONF_LOG_HIGHRES_TIMESTAMP)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.pbs_log_highres_timestamp = ((uvalue > 0) ? 1 : 0);
	}
	if ((gvalue = getenv(PBS_CONF_SCHED_THREADS)) != NULL) {
		if (sscanf(gvalue, "%u", &uvalue) == 1)
			pbs_conf.pbs_sched_threads = uvalue;
	}

	if ((gvalue = getenv(PBS_CONF_DAEMON_SERVICE_USER)) != NULL) {
		free(pbs_conf.pbs_daemon_service_user);
		pbs_conf.pbs_daemon_service_user = strdup(gvalue);
	}

	if ((gvalue = getenv(PBS_CONF_DAEMON_SERVICE_AUTH_USER)) != NULL) {
		free(pbs_conf.pbs_daemon_service_auth_user);
		pbs_conf.pbs_daemon_service_auth_user = strdup(gvalue);
	}

	if ((gvalue = getenv(PBS_CONF_PRIVILEGED_AUTH_USER)) != NULL) {
		free(pbs_conf.pbs_privileged_auth_user);
		pbs_conf.pbs_privileged_auth_user = strdup(gvalue);
	}

	if ((gvalue = getenv(PBS_CONF_GSS_USER_CREDENTIALS_BIN)) != NULL) {
		free(pbs_conf.pbs_gss_user_creds_bin);
		pbs_conf.pbs_gss_user_creds_bin = strdup(gvalue);
	}

#ifdef WIN32
	if ((gvalue = getenv(PBS_CONF_REMOTE_VIEWER)) != NULL) {
		free(pbs_conf.pbs_conf_remote_viewer);
		pbs_conf.pbs_conf_remote_viewer = strdup(gvalue);
	}
#endif

	/* iff_path is inferred from pbs_conf.pbs_exec_path - see below */

	/*
	 * Now that we have parsed through the configuration file and the
	 * environment variables, check to make sure that all the critical
	 * items are set.
	 */

	buf[0] = '\0';
	if (pbs_conf.pbs_home_path == NULL)
		strcat(buf, PBS_CONF_HOME);
	if (pbs_conf.pbs_exec_path == NULL) {
		if (buf[0] != '\0')
			strcat(buf, " ");
		strcat(buf, PBS_CONF_EXEC);
	}
	if (pbs_conf.pbs_server_name == NULL) {
		if (buf[0] != '\0')
			strcat(buf, " ");
		strcat(buf, PBS_CONF_SERVER_NAME);
	}
	if (buf[0] != '\0') {
		fprintf(stderr, "pbsconf error: pbs conf variables not found: %s\n", buf);
		goto err;
	}

	/*
	 * Perform sanity checks on PBS_*_HOST_NAME values and PBS_CONF_SMTP_SERVER_NAME.
	 * See IDD for SPID 4534.
	 */
	buf[0] = '\0';
	if ((pbs_conf.pbs_server_host_name != NULL) &&
	    (strchr(pbs_conf.pbs_server_host_name, ':') != NULL))
		strcpy(buf, PBS_CONF_SERVER_HOST_NAME);
	else if ((pbs_conf.pbs_public_host_name != NULL) &&
		 (strchr(pbs_conf.pbs_public_host_name, ':') != NULL))
		strcpy(buf, PBS_CONF_PUBLIC_HOST_NAME);
	else if ((pbs_conf.pbs_mail_host_name != NULL) &&
		 (strchr(pbs_conf.pbs_mail_host_name, ':') != NULL))
		strcpy(buf, PBS_CONF_MAIL_HOST_NAME);
	else if ((pbs_conf.pbs_smtp_server_name != NULL) &&
		 (strchr(pbs_conf.pbs_smtp_server_name, ':') != NULL))
		strcpy(buf, PBS_CONF_SMTP_SERVER_NAME);
	else if ((pbs_conf.pbs_output_host_name != NULL) &&
		 (strchr(pbs_conf.pbs_output_host_name, ':') != NULL))
		strcpy(buf, PBS_CONF_OUTPUT_HOST_NAME);
	else if ((pbs_conf.pbs_mom_node_name != NULL) &&
		 (strchr(pbs_conf.pbs_mom_node_name, ':') != NULL))
		strcpy(buf, PBS_CONF_MOM_NODE_NAME);

	if (buf[0] != '\0') {
		fprintf(stderr, "pbsconf error: illegal value for: %s\n", buf);
		goto err;
	}

	/*
	 * Finally, fill in the blanks for variables with inferred values.
	 */

	if (pbs_conf.pbs_environment == NULL) {
		/* a reasonable default for the pbs_environment file is in pbs_home */
		/* strlen("/pbs_environment") + '\0' == 16 + 1 == 17 */
		if ((pbs_conf.pbs_environment =
			     malloc(strlen(pbs_conf.pbs_home_path) + 17)) != NULL) {
			sprintf(pbs_conf.pbs_environment, "%s/pbs_environment",
				pbs_conf.pbs_home_path);
			fix_path(pbs_conf.pbs_environment, 1);
		} else {
			goto err;
		}
	}

	free(pbs_conf.iff_path);
	/* strlen("/sbin/pbs_iff") + '\0' == 13 + 1 == 14 */
	if ((pbs_conf.iff_path =
		     malloc(strlen(pbs_conf.pbs_exec_path) + 14)) != NULL) {
		sprintf(pbs_conf.iff_path, "%s/sbin/pbs_iff", pbs_conf.pbs_exec_path);
		fix_path(pbs_conf.iff_path, 1);
	} else {
		goto err;
	}

	if (pbs_conf.rcp_path == NULL) {
		if ((pbs_conf.rcp_path =
			     malloc(strlen(pbs_conf.pbs_exec_path) + 14)) != NULL) {
			sprintf(pbs_conf.rcp_path, "%s/sbin/pbs_rcp", pbs_conf.pbs_exec_path);
			fix_path(pbs_conf.rcp_path, 1);
		} else {
			goto err;
		}
	}
	if (pbs_conf.cp_path == NULL) {
#ifdef WIN32
		char *cmd = "xcopy";
#else
		char *cmd = "/bin/cp";
#endif
		pbs_conf.cp_path = strdup(cmd);
		if (pbs_conf.cp_path == NULL) {
			goto err;
		}
	}

	free(pbs_conf.pbs_demux_path);
	/* strlen("/sbin/pbs_demux") + '\0' == 15 + 1 == 16 */
	if ((pbs_conf.pbs_demux_path =
		     malloc(strlen(pbs_conf.pbs_exec_path) + 16)) != NULL) {
		sprintf(pbs_conf.pbs_demux_path, "%s/sbin/pbs_demux",
			pbs_conf.pbs_exec_path);
		fix_path(pbs_conf.pbs_demux_path, 1);
	} else {
		goto err;
	}

	if ((gvalue = getenv(PBS_CONF_INTERACTIVE_AUTH_METHOD)) != NULL) {
		char *value = convert_string_to_lowercase(gvalue);
		if (value == NULL)
			goto err;
		memset(pbs_conf.interactive_auth_method, '\0', sizeof(pbs_conf.interactive_auth_method));
		strcpy(pbs_conf.interactive_auth_method, value);
		free(value);
	}
	if ((gvalue = getenv(PBS_CONF_INTERACTIVE_ENCRYPT_METHOD)) != NULL) {
		char *value = convert_string_to_lowercase(gvalue);
		ensure_string_not_null(&value); /* allow unsetting */
		if (value == NULL)
			goto err;
		memset(pbs_conf.interactive_encrypt_method, '\0', sizeof(pbs_conf.interactive_encrypt_method));
		strcpy(pbs_conf.interactive_encrypt_method, value);
		free(value);
	}
	if ((gvalue = getenv(PBS_CONF_AUTH)) != NULL) {
		char *value = convert_string_to_lowercase(gvalue);
		if (value == NULL)
			goto err;
		memset(pbs_conf.auth_method, '\0', sizeof(pbs_conf.auth_method));
		strcpy(pbs_conf.auth_method, value);
		free(value);
	}
	if ((gvalue = getenv(PBS_CONF_ENCRYPT_METHOD)) != NULL) {
		char *value = convert_string_to_lowercase(gvalue);
		ensure_string_not_null(&value); /* allow unsetting */
		if (value == NULL)
			goto err;
		memset(pbs_conf.encrypt_method, '\0', sizeof(pbs_conf.encrypt_method));
		strcpy(pbs_conf.encrypt_method, value);
		free(value);
	}
	if ((gvalue = getenv(PBS_CONF_SUPPORTED_AUTH_METHODS)) != NULL) {
		char *value = convert_string_to_lowercase(gvalue);
		if (value == NULL)
			goto err;
		free_string_array(pbs_conf.supported_auth_methods);
		pbs_conf.supported_auth_methods = break_comma_list(value);
		if (pbs_conf.supported_auth_methods == NULL) {
			free(value);
			goto err;
		}
		free(value);
	}
	if (pbs_conf.supported_auth_methods == NULL) {
		pbs_conf.supported_auth_methods = break_comma_list(AUTH_RESVPORT_NAME);
		if (pbs_conf.supported_auth_methods == NULL) {
			goto err;
		}
	}
	if ((gvalue = getenv(PBS_CONF_AUTH_SERVICE_USERS)) != NULL) {
		char *value = convert_string_to_lowercase(gvalue);
		if (value == NULL)
			goto err;
		free_string_array(pbs_conf.auth_service_users);
		pbs_conf.auth_service_users = break_comma_list(value);
		if (pbs_conf.auth_service_users == NULL) {
			free(value);
			goto err;
		}
		free(value);
	}
	if (pbs_conf.auth_service_users == NULL) {
		pbs_conf.auth_service_users = break_comma_list("root");
		if (pbs_conf.auth_service_users == NULL) {
			goto err;
		}
	}
	if (pbs_conf.encrypt_method[0] != '\0') {
		/* encryption is not disabled, validate encrypt method */
		if (is_valid_encrypt_method(pbs_conf.encrypt_method) != 1) {
			fprintf(stderr, "The given PBS_ENCRYPT_METHOD = %s does not support encrypt/decrypt of data\n", pbs_conf.encrypt_method);
			goto err;
		}
	}
	if (pbs_conf.interactive_encrypt_method[0] != '\0') {
		/* encryption is not disabled, validate encrypt method */
		if (is_valid_encrypt_method(pbs_conf.interactive_encrypt_method) != 1) {
			fprintf(stderr, "The given PBS_INTERACTIVE_ENCRYPT_METHOD = %s does not support encrypt/decrypt of data\n", pbs_conf.interactive_encrypt_method);
			goto err;
		}
	}

	pbs_conf.pbs_tmpdir = pbs_get_tmpdir();

	/* if routers has null value populate with server name as the default */
	if (pbs_conf.pbs_leaf_routers == NULL) {
		if (pbs_conf.pbs_primary && pbs_conf.pbs_secondary) {
			pbs_conf.pbs_leaf_routers = malloc(strlen(pbs_conf.pbs_primary) + strlen(pbs_conf.pbs_secondary) + 2);
			if (pbs_conf.pbs_leaf_routers == NULL) {
				fprintf(stderr, "Out of memory\n");
				goto err;
			}
			sprintf(pbs_conf.pbs_leaf_routers, "%s,%s", pbs_conf.pbs_primary, pbs_conf.pbs_secondary);
		} else {
			if (pbs_conf.pbs_server_host_name) {
				pbs_conf.pbs_leaf_routers = strdup(pbs_conf.pbs_server_host_name);
			} else if (pbs_conf.pbs_server_name) {
				pbs_conf.pbs_leaf_routers = strdup(pbs_conf.pbs_server_name);
			} else {
				fprintf(stderr, "PBS server undefined\n");
				goto err;
			}
			if (pbs_conf.pbs_leaf_routers == NULL) {
				fprintf(stderr, "Out of memory\n");
				goto err;
			}
		}
	}

	/* determine who we are */
	pbs_current_uid = getuid();
	if ((pw = getpwuid(pbs_current_uid)) == NULL) {
		goto err;
	}
	if (strlen(pw->pw_name) > (PBS_MAXUSER - 1)) {
		goto err;
	}
	strcpy(pbs_conf.current_user, pw->pw_name);

	pbs_conf.loaded = 1;

	if (pbs_client_thread_unlock_conf() != 0)
		return 0;

	return 1; /* success */

err:
	if (pbs_conf.pbs_conf_file) {
		free(pbs_conf.pbs_conf_file);
		pbs_conf.pbs_conf_file = NULL;
	}
	if (pbs_conf.pbs_data_service_host) {
		free(pbs_conf.pbs_data_service_host);
		pbs_conf.pbs_data_service_host = NULL;
	}
	if (pbs_conf.pbs_home_path) {
		free(pbs_conf.pbs_home_path);
		pbs_conf.pbs_home_path = NULL;
	}
	if (pbs_conf.pbs_exec_path) {
		free(pbs_conf.pbs_exec_path);
		pbs_conf.pbs_exec_path = NULL;
	}
	if (pbs_conf.pbs_server_name) {
		free(pbs_conf.pbs_server_name);
		pbs_conf.pbs_server_name = NULL;
	}
	if (pbs_conf.rcp_path) {
		free(pbs_conf.rcp_path);
		pbs_conf.rcp_path = NULL;
	}
	if (pbs_conf.scp_path) {
		free(pbs_conf.scp_path);
		pbs_conf.scp_path = NULL;
	}
	if (pbs_conf.scp_args) {
		free(pbs_conf.scp_args);
		pbs_conf.scp_args = NULL;
	}
	if (pbs_conf.cp_path) {
		free(pbs_conf.cp_path);
		pbs_conf.cp_path = NULL;
	}
	if (pbs_conf.pbs_environment) {
		free(pbs_conf.pbs_environment);
		pbs_conf.pbs_environment = NULL;
	}
	if (pbs_conf.pbs_primary) {
		free(pbs_conf.pbs_primary);
		pbs_conf.pbs_primary = NULL;
	}
	if (pbs_conf.pbs_secondary) {
		free(pbs_conf.pbs_secondary);
		pbs_conf.pbs_secondary = NULL;
	}
	if (pbs_conf.pbs_mom_home) {
		free(pbs_conf.pbs_mom_home);
		pbs_conf.pbs_mom_home = NULL;
	}
	if (pbs_conf.pbs_core_limit) {
		free(pbs_conf.pbs_core_limit);
		pbs_conf.pbs_core_limit = NULL;
	}
	if (pbs_conf.supported_auth_methods) {
		free_string_array(pbs_conf.supported_auth_methods);
		pbs_conf.supported_auth_methods = NULL;
	}
	if (pbs_conf.auth_service_users) {
		free_string_array(pbs_conf.auth_service_users);
		pbs_conf.auth_service_users = NULL;
	}

	pbs_conf.load_failed = 1;
	(void) pbs_client_thread_unlock_conf();
	return 0;
}

/**
 * @brief
 *	pbs_get_tmpdir - Identify the configured tmpdir location
 *
 * @return char *
 * @retval !NULL pointer to the tmpdir string
 * @retval NULL failure
 */
char *
pbs_get_tmpdir(void)
{
	FILE *fp = NULL;
	char *tmpdir = NULL;
	char *conf_file = NULL;
	char *conf_name = NULL;
	char *conf_value = NULL;
	char *p = NULL;
#ifdef WIN32
	struct stat sb;
#endif

	/* If pbs_conf already been populated use that value. */
	if ((pbs_conf.loaded != 0) && (pbs_conf.pbs_tmpdir != NULL))
		return (pbs_conf.pbs_tmpdir);

		/* Next, try the environment. */
#ifdef WIN32
	if ((p = getenv("TMP")) != NULL)
#else
	if ((p = getenv("TMPDIR")) != NULL)
#endif
	{
		tmpdir = shorten_and_cleanup_path(p);
	}
	/* PBS_TMPDIR overrides TMP or TMPDIR if set */
	if ((p = getenv(PBS_CONF_TMPDIR)) != NULL) {
		free(tmpdir);
		tmpdir = shorten_and_cleanup_path(p);
	}
	if (tmpdir != NULL)
		return tmpdir;

	/* Now try pbs.conf */
	conf_file = pbs_get_conf_file();
	if ((fp = fopen(conf_file, "r")) != NULL) {
		while (parse_config_line(fp, &conf_name, &conf_value) != NULL) {
			if ((conf_name == NULL) || (*conf_name == '\0'))
				continue;
			if ((conf_value == NULL) || (*conf_value == '\0'))
				continue;
			if (!strcmp(conf_name, PBS_CONF_TMPDIR)) {
				free(tmpdir);
				tmpdir = shorten_and_cleanup_path(conf_value);
			}
		}
		fclose(fp);
	}
	free(conf_file);
	conf_file = NULL;
	if (tmpdir != NULL)
		return tmpdir;

		/* Finally, resort to the default. */
#ifdef WIN32
	if (stat(TMP_DIR, &sb) == 0) {
		tmpdir = shorten_and_cleanup_path(TMP_DIR);
	} else if (stat("C:\\WINDOWS\\TEMP", &sb) == 0) {
		tmpdir = shorten_and_cleanup_path("C:\\WINDOWS\\TEMP");
	}
#else
	tmpdir = shorten_and_cleanup_path(TMP_DIR);
#endif
	if (tmpdir == NULL) {
		/* strlen("/spool") + '\0' == 6 + 1 = 7 */
		if ((p = malloc(strlen(pbs_conf.pbs_home_path) + 7)) == NULL) {
			return NULL;
		} else {
			sprintf(p, "%s/spool", pbs_conf.pbs_home_path);
			tmpdir = shorten_and_cleanup_path(p);
			free(p);
		}
	}
	/* Strip the trailing separator. */
#ifdef WIN32
	if (tmpdir[strlen(tmpdir) - 1] == '\\')
		tmpdir[strlen(tmpdir) - 1] = '\0';
#else
	if (tmpdir[strlen(tmpdir) - 1] == '/')
		tmpdir[strlen(tmpdir) - 1] = '\0';
#endif
	return tmpdir;
}