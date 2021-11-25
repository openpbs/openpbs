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
 * @file	qmgr.c
 * @brief
 *  	The qmgr command provides an administrator interface to the batch
 *      system.  The command reads directives from standard input.  The syntax
 *      of each directive is checked and the appropriate request is sent to the
 *      batch server or servers.
 * @par	Synopsis:
 *      qmgr [-a] [-c command] [-e] [-n] [-z] [server...]
 *
 * @par Options:
 *      -a      Abort qmgr on any syntax errors or any requests rejected by a
 *              server.
 *
 *      -c command
 *              Execute a single command and exit qmgr.
 *
 *      -e      Echo all commands to standard output.
 *
 *      -n      No commands are executed, syntax checking only is performed.
 *
 *      -z      No errors are written to standard error.
 *
 * 	@par Arguments:
 *      server...
 *              A list of servers to administer.  If no servers are given, then
 *              use the default server.
 *
 *
 *	@par Exitcodes:
 *	  0 - successful
 *	  1 - error in parse
 *	  2 - error in execute
 *	  3 - error connect_servers
 *	  4 - error set_active
 *	  5 - memory allocation error
 *
 * @author 	Bruce Kelly
 * 			National Energy Research Supercomputer Center
 * 			Livermore, CA
 *			March, 1993
 *
 */

#include <pbs_config.h>

#include <stdio.h>
#include <unistd.h>
#include <ctype.h>
#include <pwd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>

/* PBS include files */
#include <cmds.h>
#include <qmgr.h>
#include "libpbs.h"
#include "pbs_version.h"
#include "pbs_share.h"
#include "hook.h"
#include "pbs_ifl.h"
#include "net_connect.h"
#include "server_limits.h"
#include "attribute.h"
#include "pbs_entlim.h"
#include "resource.h"
#include "pbs_ecl.h"
#include "libutil.h"

/* Global Variables */
#define QMGR_TIMEOUT 900 /* qmgr connection timeout set to 15 min */
time_t start_time = 0;
time_t check_time = 0;

char prompt[] = "Qmgr: "; /* Prompt if input is from terminal */
char contin[] = "Qmgr< "; /* Prompt if input is continued across lines */
char *cur_prompt = prompt;
const char hist_init_err[] = "History could not be initialized\n";
const char histfile_access_err[] = "Cannot read/write history file %s, history across sessions disabled\n";
int qmgr_hist_enabled = 0;	     /* history is enabled by default */
char qmgr_hist_file[MAXPATHLEN + 1]; /* history file for this user */

static char hook_tempfile_errmsg[HOOK_MSG_SIZE] = {'\0'};

/*
 * This variable represents the use of the -z option on the command line.
 * It is declared here because it must be used by the pstderr routine to
 * determine if any message should be printed to standard error.
 */
int zopt = FALSE; /* -z option */

static struct server *servers = NULL; /* Linked list of server structures */
static int nservers = 0;	      /* Number of servers */

/* active objects */
struct objname *active_servers;
struct objname *active_queues;
struct objname *active_nodes;
struct objname *active_scheds;

/* The following refer to who is executing the qmgr and from what host */
char cur_host[PBS_MAXHOSTNAME + 1];
char cur_user[PBS_MAXHOSTNAME + 1];
char conf_full_server_name[PBS_MAXHOSTNAME + 1] = {'\0'};

const char syntaxerr[] = "qmgr: Syntax error\n";

/* List of attribute names for attributes of type entlim */
static char *entlim_attrs[] = {
	ATTR_max_run,
	ATTR_max_run_res,
	ATTR_max_run_soft,
	ATTR_max_run_res_soft,
	ATTR_max_queued,
	ATTR_max_queued_res,
	ATTR_queued_jobs_threshold,
	ATTR_queued_jobs_threshold_res,
	NULL /* keep as last one please */
};

/* Hook-related variables and functions */

static char *hook_tempfile = NULL; /* a temporary file in PBS_HOOK_WORKDIR */
static char *hook_tempdir = NULL;  /* PBS_HOOK_WORKDIR path */

extern void qmgr_list_history(int);
extern int init_qmgr_hist(char *);
extern int qmgr_add_history(char *);
extern int get_request_hist(char **);

/**
 * @brief
 * 	dyn_strcpy: copies src string into 'dest', and adjusting the size of
 * 	'dest'  with realloc to fit the value of src.
 *
 * @param[in] dest - destination string for holding hookfile name
 * @param[in] src - src string holding filename
 *
 * @return - Void  (exits the program upon error.)
 *
 */
static void
dyn_strcpy(char **dest, char *src)
{
	char *p;

	if ((dest == NULL) || (*dest == NULL) || (src == NULL)) {

		fprintf(stderr, "dyn_strcpy: bad argument\n");
		exit(1);
	}

	if (strlen(*dest) >= strlen(src)) {
		strcpy(*dest, src);
	} else {
		p = (char *) realloc((char *) *dest, strlen(src) + 1);
		if (p == NULL) {
			fprintf(stderr, "dyn_strcpy: Failed to realloc\n");
			exit(1);
		}
		*dest = p;
	}
	strcpy(*dest, src);
}

/**
 * @brief
 * 	base: returns the basename of the given 'path'.
 *
 * @param[in] path - file path
 *
 * @return string
 * @retval filename
 * exits from program on failure
 *
 */
static char *
base(char *path)
{
	char *p;

	if (path == NULL) {
		fprintf(stderr, "base: bad argument\n");
		exit(1);
	}

	p = (char *) path;

#ifdef WIN32
	if (((p = strrchr(path, '/')) != NULL) || ((p = strrchr(path, '\\')) != NULL))
#else
	if ((p = strrchr(path, '/')))
#endif
	{
		p++;
	}

	return (p);
}

static void
attrlist_add(struct attropl **attrlist, char *attname,
	     size_t attname_len, char *attval, size_t attval_len)
{
	struct attropl *paol;
	int ltxt;

	if ((attrlist == NULL) || (attname == NULL) || (attval == NULL)) {
		fprintf(stderr, "attrlist_add: bad argument\n");
		exit(1);
	}

	/* Allocate storage for attribute structure */
	Mstruct(paol, struct attropl);
	paol->name = NULL;
	paol->resource = NULL;
	paol->value = NULL;
	paol->next = *attrlist;
	*attrlist = paol;

	ltxt = attname_len;
	Mstring(paol->name, ltxt + 1);
	pbs_strncpy(paol->name, attname, ltxt + 1);

	paol->op = SET;

	if (attval_len == 0) { /* don't malloc */
		paol->value = attval;
	} else {
		ltxt = attval_len;
		Mstring(paol->value, ltxt + 1);
		pbs_strncpy(paol->value, attval, ltxt + 1);
	}
}

/* dump_file: dump contents of 'infile' into 'outfile'. If 'infile' is NULL
 or the empty string, then input contents is coming from STDIN; if 'outfile'
 is NULL or the empty string, then contents are dumped into STDOUT.
 Return 0 for success; 1 otherwise, with
 'msg' filled in with error information.
 */
int
dump_file(char *infile, char *outfile, char *infile_encoding, char *msg, size_t msg_len)
{
	FILE *infp;
	FILE *outfp;

	unsigned char in_data[HOOK_BUF_SIZE + 1];
	ssize_t in_len;
	int ret = 0;
	int encode_b64 = 0; /* 1 if encode in base 64 */
	struct stat sb;

	memset(msg, '\0', msg_len);

	if ((infile == NULL) || (infile[0] == '\0')) {
		infp = stdin;
	} else {

		infp = fopen(infile, "rb");

		if (infp == NULL) {
			snprintf(msg, msg_len - 1,
				 "%s - %s", infile, strerror(errno));
			return (1);
		}
		/* need to check if we really opened a file and not a directory/dev */
		if ((fstat(fileno(infp), &sb) != -1) && !S_ISREG(sb.st_mode)) {
			snprintf(msg, msg_len - 1,
				 "%s - Permission denied", infile);

			fclose(infp);
			return (1);
		}
	}

	if ((outfile == NULL) || (outfile[0] == '\0')) {
		outfp = stdout;
	} else {
		outfp = fopen(outfile, "wb");

		if (outfp == NULL) {
			snprintf(msg, msg_len - 1,
				 "%s - %s", outfile, strerror(errno));
			ret = 1;
			goto dump_file_exit;
		}
#ifdef WIN32
		secure_file(outfile, "Administrators",
			    READS_MASK | WRITES_MASK | STANDARD_RIGHTS_REQUIRED);
#endif
	}

	if (strcmp(infile_encoding, HOOKSTR_BASE64) == 0) {
		encode_b64 = 1;
	}

	while (fgets((char *) in_data, sizeof(in_data), infp) != NULL) {
		in_len = strlen((char *) in_data);
		if (encode_b64 &&
		    (strcmp((char *) in_data, "\n") == 0)) { /* empty line */
			/* signals end of processing, especially when     */
			/* qmgr -c print hook output is fed back to qmgr  */
			/* The output will have one or more hooks         */
			/* definitions with their encoded contents, and   */
			/* an empty line terminates a hook content.       */
			break;
		}
		if (in_len > 0) {
			if (fwrite(in_data, 1, in_len, outfp) != in_len) {
				snprintf(msg, msg_len - 1,
					 "write to %s failed! Aborting...",
					 outfile);
				ret = 1;
				goto dump_file_exit;
			}
		}
	}
	if (fflush(outfp) != 0) {
		snprintf(msg, msg_len - 1,
			 "Failed to dump file %s (error %s)", outfile,
			 strerror(errno));
		ret = 1;
	}

dump_file_exit:
	if (infp && infp != stdin)
		fclose(infp);

	if (outfp && outfp != stdout) {
		fclose(outfp);
	}
	if (ret != 0) {
		if (outfile)
			(void) unlink(outfile);
	}
	return (ret);
}

/*
 *
 *	params_import - parse the parameters to the MGR_CMD_IMPORT
 *			<content-type> <content-encoding> <input_file>|-
 *
 *	  attrs        Text of the import command parameters.
 * 	  OUT: attrlist     Address of the attribute-value structure.
 * 	  doper	directive operation type  - must be import.
 *
 * 	Returns:
 *        This routine returns zero upon successful completion.  If there is
 *        a syntax error, it will return the index into attrs where the error
 *        occurred.
 *
 * 	Note:
 *        The following is an example of the text input and what the resulting
 *        data structure should look like.
 *
 *		"content-type" = "application/x-python"
 *	 	"content-encoding" = "base64"
 *		"input-file" = "in_file.PY"
 *
 *      attrlist ---> struct attropl *
 *                      |
 *                      |
 *                      \/
 *                      "content-type"
 *                      ""
 *                      "application/x-python"
 *                      SET
 *                      ---------
 *                              |
 *                      "content-encoding"   <-
 *                      ""
 *                      "base64"
 *                      SET
 *                      ---------
 *                              |
 *                      "input-file"   <-
 *                      ""
 *                      "in_file.PY"
 *                      SET
 *                      NULL
 */
int
params_import(char *attrs, struct attropl **attrlist, int doper)
{
	int i;
	char *c;     /* Pointer into the attrs text */
	char *start; /* Pointer to the start of a word */
	char *v;     /* value returned by pbs_quote_parse */
	char *e;

	if ((attrs == NULL) || (attrlist == NULL)) {
		fprintf(stderr, "params_import: bad argument\n");
		exit(1);
	}

	if (doper != MGR_CMD_IMPORT)
		return 1;

	/* Free the space from the previous structure */
	freeattropl(*attrlist);
	*attrlist = NULL;

	/* Is there any thing to parse? */
	c = attrs;
	while (White(*c))
		c++;

	if (EOL(*c))
		return 1; /* no parameter */

	/* Parse the parameter values */

	/* Get the content-type */

	start = c;
	while (!EOL(*c) && !White(*c))
		c++;

	if (c == start) {
		/* No attribute */
		if (start == attrs)
			start++;
		return (start - attrs);
	}
	attrlist_add(attrlist, CONTENT_TYPE_PARAM, strlen(CONTENT_TYPE_PARAM),
		     start, c - start);

	/* Get the content-encoding */
	while (White(*c))
		c++;

	if (!EOL(*c)) {
		start = c;
		while (!EOL(*c) && !White(*c))
			c++;

		if (c == start) {
			/* No attribute */
			if (start == attrs)
				start++;
			return (start - attrs);
		}

		attrlist_add(attrlist, CONTENT_ENCODING_PARAM,
			     strlen(CONTENT_ENCODING_PARAM), start, c - start);
	} else
		return (c - attrs);

	/* Get the input-file */
	while (White(*c))
		c++;

	if (!EOL(*c)) {
		i = pbs_quote_parse(c, &v, &e, QMGR_NO_WHITE_IN_VALUE);
		if (i == -1) {
			pstderr("qmgr: Out of memory\n");
			clean_up_and_exit(5);
		} else if (i > 0)
			return (c - attrs);

		/* value ok */
		attrlist_add(attrlist, INPUT_FILE_PARAM, strlen(INPUT_FILE_PARAM), v,
			     strlen(v));

		if (EOL(*e)) {
			return 0; /* end of line */
		}
		c = e; /* otherwise more to parse */
	} else
		return (c - attrs);

	/* See if there is another argument */
	while (White(*c))
		c++;

	if (!EOL(*c))
		return (c - attrs);

	return 0;
}

/**
 * @brief
 *	params_export - parse the parameters to the MGR_CMD_EXPORT
 *			<content-type> <content-encoding> <output_file>
 *
 *	attrs        Text of the export command parameters.
 * 	OUT: attrlist     Address of the attribute-value structure.
 *	doper	directive operation type - must be export
 *
 * @return Returns:
 *        This routine returns zero upon successful completion.  If there is
 *        a syntax error, it will return the index into attrs where the error
 *        occurred.
 *
 * 	Note:
 *        The following is an example of the text input and what the resulting
 *        data structure should look like.
 *
 *		"content-type" = "application/x-python"
 *	 	"content-encoding" = "base64"
 *		"input-file" = "in_file.PY"
 *
 *      attrlist ---> struct attropl *
 *                      |
 *                      |
 *                      \/
 *                      "content-type"
 *                      ""
 *                      "application/x-python"
 *                      SET
 *                      ---------
 *                              |
 *                      "content-encoding"   <-
 *                      ""
 *                      "base64"
 *                      SET
 *                      ---------
 *                              |
 *                      "output-file"   <-
 *                      ""
 *                      "out_file.PY"
 *                      SET
 *                      NULL
 */
int
params_export(char *attrs, struct attropl **attrlist, int doper)
{
	int i;
	char *c;     /* Pointer into the attrs text */
	char *start; /* Pointer to the start of a word */
	char *v;     /* value returned by pbs_quote_parse */
	char *e;

	if ((attrs == NULL) || (attrlist == NULL)) {
		fprintf(stderr, "params_export: bad argument\n");
		exit(1);
	}

	if (doper != MGR_CMD_EXPORT)
		return 1;

	/* Free the space from the previous structure */
	freeattropl(*attrlist);
	*attrlist = NULL;

	/* Is there any thing to parse? */
	c = attrs;
	while (White(*c))
		c++;

	if (EOL(*c))
		return 1; /* no parameter */

	/* Parse the parameter values */

	/* Get the content-type */

	start = c;
	while (!EOL(*c) && !White(*c))
		c++;

	if (c == start) {
		/* No attribute */
		if (start == attrs)
			start++;
		return (start - attrs);
	}
	attrlist_add(attrlist, CONTENT_TYPE_PARAM, strlen(CONTENT_TYPE_PARAM),
		     start, c - start);

	/* Get the content-encoding */
	while (White(*c))
		c++;

	if (!EOL(*c)) {
		start = c;
		while (!EOL(*c) && !White(*c))
			c++;

		if (c == start) {
			/* No attribute */
			if (start == attrs)
				start++;
			return (start - attrs);
		}

		attrlist_add(attrlist, CONTENT_ENCODING_PARAM,
			     strlen(CONTENT_ENCODING_PARAM), start, c - start);
	} else
		return (c - attrs);

	/* Get the OUTPUT_FILE_PARAM */
	while (White(*c))
		c++;

	if (!EOL(*c)) {
		i = pbs_quote_parse(c, &v, &e, QMGR_NO_WHITE_IN_VALUE);
		if (i == -1) {
			pstderr("qmgr: Out of memory\n");
			clean_up_and_exit(5);
		} else if (i > 0) {
			return (c - attrs);
		}
		/* value ok */
		attrlist_add(attrlist, OUTPUT_FILE_PARAM, strlen(OUTPUT_FILE_PARAM), v,
			     strlen(v));

		if (EOL(*e)) {
			return 0; /* end of line */
		}
		c = e; /* otherwise more to parse */
	} else {
		/* ok to not have OUTPUT_FILE_PARAM, just put empty string */
		attrlist_add(attrlist, OUTPUT_FILE_PARAM, strlen(OUTPUT_FILE_PARAM), "", 1);
	}

	/* See if there is another argument */
	while (White(*c))
		c++;

	if (!EOL(*c))
		return (c - attrs);
	return 0;
}

/**
 * @brief
 *	who: returns the username currently running this command
 *
 * @return string
 * @retval username
 *
 */
char *
who()
{
#ifdef WIN32
	return (getlogin()); /* Windows version does not return NULL */

#else
	struct passwd *pw;

	if ((pw = getpwuid(getuid())) == NULL) {
		return ("");
	}

	if (pw->pw_name == NULL)
		return ("");

	return (pw->pw_name);
#endif
}

int
main(int argc, char **argv)
{
	static char opts[] = "ac:enz"; /* See man getopt */
	static char usage[] = "Usage: qmgr [-a] [-c command] [-e] [-n] [-z] [server...]\n";
	static char usag2[] = "       qmgr --version\n";
	int aopt = FALSE;		/* -a option */
	int eopt = FALSE;		/* -e option */
	int nopt = FALSE;		/* -n option */
	char *copt = NULL;		/* -c command option */
	int c;				/* Individual option */
	int errflg = 0;			/* Error flag */
	char *request = NULL;		/* Current request */
	int oper = MGR_CMD_CREATE;	/* Operation: create, delete, set, unset, list, print */
	int type = MGR_OBJ_SERVER;	/* Object type: server or queue */
	char *name = NULL;		/* Object name */
	struct attropl *attribs = NULL; /* Pointer to attribute list */
	struct objname *svrs;
#ifndef WIN32
	int htmp_fd; /* for creating hooks temp file */
#endif

	/*test for real deal or just version and exit*/

	PRINT_VERSION_AND_EXIT(argc, argv);

	if (initsocketlib())
		return 1;

	/* Command line options */
	while ((c = getopt(argc, argv, opts)) != EOF) {
		switch (c) {
			case 'a':
				aopt = TRUE;
				break;
			case 'c':
				copt = optarg;
				break;
			case 'e':
				eopt = TRUE;
				break;
			case 'n':
				nopt = TRUE;
				break;
			case 'z':
				zopt = TRUE;
				break;
			case '?':
			default:
				errflg++;
				break;
		}
	}

	if (errflg) {
		pstderr(usage);
		pstderr(usag2);
		exit(1);
	}

	if (argc > optind)
		svrs = strings2objname(&argv[optind], argc - optind, MGR_OBJ_SERVER);
	else
		svrs = default_server_name();

	/*perform needed security library initializations (including none)*/

	if (CS_client_init() != CS_SUCCESS) {
		fprintf(stderr, "qmgr: unable to initialize security library.\n");
		exit(2);
	}

	pbs_strncpy(cur_user, who(), sizeof(cur_user));
	cur_host[0] = '\0';

	/* obtain global information for hooks */
	if (pbs_loadconf(0) == 0) {
		fprintf(stderr, "Failed to load pbs.conf file\n");
		exit(2);
	}

	if (gethostname(cur_host, (sizeof(cur_host) - 1)) == 0)
		get_fullhostname(cur_host, cur_host, (sizeof(cur_host) - 1));

	/*
	 * Get the Server Name which is used in hook related error messages:
	 * 1. from PBS_PRIMARY if defined, if not
	 * 2. from PBS_SERVER_HOST_NAME if defined, if not
	 * 3. from PBS_SERVER, and as last resort
	 * 4. use my host name
	 */
	if (pbs_conf.pbs_primary != NULL) {
		pbs_strncpy(conf_full_server_name, pbs_conf.pbs_primary,
			    sizeof(conf_full_server_name));
	} else if (pbs_conf.pbs_server_host_name != NULL) {
		pbs_strncpy(conf_full_server_name, pbs_conf.pbs_server_host_name,
			    sizeof(conf_full_server_name));
	} else if (pbs_conf.pbs_server_name != NULL) {
		pbs_strncpy(conf_full_server_name, pbs_conf.pbs_server_name,
			    sizeof(conf_full_server_name));
	}
	if (conf_full_server_name[0] != '\0') {
		get_fullhostname(conf_full_server_name, conf_full_server_name,
				 (sizeof(conf_full_server_name) - 1));
	}

	pbs_asprintf(&hook_tempdir, "%s/server_priv/%s",
		     pbs_conf.pbs_home_path, PBS_HOOK_WORKDIR);
	pbs_asprintf(&hook_tempfile, "%s/qmgr_hook%dXXXXXX",
		     hook_tempdir, getpid());

#ifdef WIN32
	/* mktemp() generates a filename */
	if (mktemp(hook_tempfile) == NULL) {
		snprintf(hook_tempfile_errmsg, sizeof(hook_tempfile_errmsg),
			 "unable to generate a hook_tempfile from %s - %s\n",
			 hook_tempfile, strerror(errno));
		hook_tempfile[0] = '\0'; /* hook_tempfile name generation not successful */
	}
#else
	/*
	 * For Linux/Unix, it is recommended to use mkstemp() for mktemp() is
	 * dangerous - see mktemp(3).
	 * mkstemp() generates and CREATES a filename
	 */
	if ((htmp_fd = mkstemp(hook_tempfile)) == -1) {
		snprintf(hook_tempfile_errmsg, sizeof(hook_tempfile_errmsg),
			 "unable to generate a hook_tempfile from %s - %s\n",
			 hook_tempfile, strerror(errno));
		hook_tempfile[0] = '\0'; /* hook_tempfile name generation not successful */
	} else {			 /* success */
		(void) close(htmp_fd);
		(void) unlink(hook_tempfile); /* we'll recreate later if needed */
	}
#endif /* Linux/Unix */

	errflg = connect_servers(svrs, ALL_SERVERS);
	if ((nservers == 0) || (errflg))
		clean_up_and_exit(3);

	errflg = set_active(MGR_OBJ_SERVER, svrs);
	if (errflg && aopt)
		clean_up_and_exit(4);

	/*
	 * If no command was given on the command line, then read them from
	 * stdin until end-of-file.  Otherwise, execute the one command only.
	 */
	if (copt == NULL) {

#ifdef QMGR_HAVE_HIST
		qmgr_hist_enabled = 0;
		if (isatty(0) && isatty(1)) {
			if (init_qmgr_hist(argv[0]) == 0)
				qmgr_hist_enabled = 1;
		}
#endif

		printf("Max open servers: %d\n", pbs_query_max_connections());
		/*
		 * Passing the address of request since the memory is allocated
		 * in the function get_request itself and passed back to the
		 * caller
		 */
		while (get_request(&request) != EOF) {
			check_time = time(0);
			if (attribs) {
				PBS_free_aopl(attribs);
				attribs = NULL;
			}
			if (eopt)
				printf("%s\n", request);

			errflg = parse(request, &oper, &type, &name, &attribs);
			if (errflg == -1) /* help */
				continue;

			if (aopt && errflg)
				clean_up_and_exit(1);

			if (!nopt && !errflg) {
				errflg = execute(aopt, oper, type, name, attribs);
				if (aopt && errflg)
					clean_up_and_exit(2);
			}
			if (request != NULL) {
				free(request);
				request = NULL;
			}
			/*
			 * Deallocate the memory for the variable name whose memory
			 * is allocated originally in the function parse
			 */
			if (name != NULL) {
				free(name);
				name = NULL;
			}
		}
	} else {
		if (eopt)
			printf("%s\n", copt);

		errflg = parse(copt, &oper, &type, &name, &attribs);
		if (aopt && errflg)
			clean_up_and_exit(1);

		if (!nopt && !errflg) {
			errflg = execute(aopt, oper, type, name, attribs);
			if (aopt && errflg)
				clean_up_and_exit(2);
		}
		/*
		 * Deallocate the memory for the variable name whose memory
		 * is allocated originally in the function parse
		 */
		if (name != NULL) {
			free(name);
			name = NULL;
		}
	}
	if (errflg)
		clean_up_and_exit(errflg);

	clean_up_and_exit(0);

	return 0;
}

/*
 * chk_special_attr_values - do additional syntax checking on the values
 *	of certain attributes
 */
static int
chk_special_attr_values(struct attropl *paol)
{
	int i;
	char *dupval;
	int r;

	i = 0;
	while (entlim_attrs[i]) {
		if (strcmp(paol->name, entlim_attrs[i]) == 0) {
			dupval = strdup(paol->value);
			if (dupval == NULL)
				return 0;
			r = entlim_parse(dupval, paol->resource, NULL, NULL);
			free(dupval);
			return (-r);
		}
		++i;
	}
	return 0;
}

/*
 *
 *	attributes - parse attribute-value pairs in the format:
 *		     attribute OP value
 *		     which are on the qmgr input
 *
 * 	  attrs        Text of the attribute-value pairs.
 * 	  OUT: attrlist     Address of the attribute-value structure.
 * 	  doper	directive operation type (create, delete, set, ...)
 *
 * 	Returns:
 *        This routine returns zero upon successful completion.  If there is
 *        a syntax error, it will return the index or offset into the attrs
 *	  character string (input) where the error occurred.  This can be used
 *	  by the calling function to indicate to the user the character in error
 *
 * 	Note:
 *        The following is an example of the text input and what the resulting
 *        data structure should look like.
 *
 *      a1 = v1, a2.r2 += v2 , a3-=v3
 *
 *      attrlist ---> struct attropl *
 *                      |
 *                      |
 *                      \/
 *                      "a1"
 *                      ""
 *                      "v1"
 *                      SET
 *                      ---------
 *                              |
 *                      "a2"   <-
 *                      "r2"
 *                      "v2"
 *                      INCR
 *                      ---------
 *                              |
 *                      "a3"   <-
 *                      ""
 *                      "v3"
 *                      DECR
 *                      NULL
 */
int
attributes(char *attrs, struct attropl **attrlist, int doper)
{
	int i;
	char *c;     /* Pointer into the attrs text */
	char *start; /* Pointer to the start of a word */
	char *v;     /* value returned by pbs_quote_parse */
	char *e;
	int ltxt; /* Length of a word */
	struct attropl *paol;
	char **pentlim_name;

	/* Free the space from the previous structure */
	freeattropl(*attrlist);
	*attrlist = NULL;

	/* Is there any thing to parse? */
	c = attrs;
	while (White(*c))
		c++;

	if (EOL(*c))
		return 0;

	/* Parse the attribute-values */
	while (TRUE) {
		/* Get the attribute and resource */
		while (White(*c))
			c++;
		if (!EOL(*c)) {
			start = c;
			while ((*c != '.') && (*c != ',') && !EOL(*c) && !Oper(c) && !White(*c))
				c++;

			if (c == start) {
				/* No attribute */
				if (start == attrs)
					start++;
				return (start - attrs);
			}

			/* Allocate storage for attribute structure */
			Mstruct(paol, struct attropl);
			paol->name = NULL;
			paol->resource = NULL;
			paol->value = NULL;
			paol->next = *attrlist;
			*attrlist = paol;

			/* Copy attribute into structure */
			ltxt = c - start;
			Mstring(paol->name, ltxt + 1);
			pbs_strncpy(paol->name, start, ltxt + 1);

			/* Resource, if any */
			if (*c == '.') {
				start = ++c;
				if ((doper == MGR_CMD_UNSET) ||
				    (doper == MGR_CMD_LIST) ||
				    (doper == MGR_CMD_PRINT)) {
					while (!White(*c) && !Oper(c) && !EOL(*c) && !(*c == ','))
						c++;
				} else {
					while (!White(*c) && !Oper(c) && !EOL(*c))
						c++;
				}

				ltxt = c - start;
				if (ltxt == 0) /* No resource */
					return (start - attrs);

				Mstring(paol->resource, ltxt + 1);
				pbs_strncpy(paol->resource, start, ltxt + 1);
			}
		} else
			return (c - attrs);

		/* Get the operator */
		while (White(*c))
			c++;

		if (!EOL(*c)) {
			switch (*c) {
				case '=':
					paol->op = SET;
					c++;
					break;
				case '+':
					paol->op = INCR;
					c += 2;
					break;
				case '-':
					paol->op = DECR;
					c += 2;
					break;
				case ',':
					/* Attribute with no value */
					Mstring(paol->value, 1);
					paol->value[0] = '\0';
					goto next;
				default:
					return (c - attrs);
			}

			/* The unset command must not have a operator or value */
			if (doper == MGR_CMD_UNSET)
				return (c - attrs);
		} else if (doper != MGR_CMD_CREATE && doper != MGR_CMD_SET) {
			Mstring(paol->value, 1);
			paol->value[0] = '\0';
			return 0;
		} else
			return (c - attrs);

		/* Get the value */
		while (White(*c))
			c++;

		/* need to know if the attrbute is of the entlim variety */
		/* look through the list of attribute names which are    */
		pentlim_name = entlim_attrs;
		while (*pentlim_name) {
			if (strcasecmp(*pentlim_name, paol->name) == 0)
				break;
			++pentlim_name;
		}

		if (!EOL(*c)) {
			if (*pentlim_name == NULL) {
				/* regular type of attribute, unquoted white space not allowed in val */
				i = pbs_quote_parse(c, &v, &e, QMGR_NO_WHITE_IN_VALUE);
			} else {
				/* entlim type of attribute, unquoted white space is allowed in val */
				i = pbs_quote_parse(c, &v, &e, QMGR_ALLOW_WHITE_IN_VALUE);
			}
			if (i == -1) {
				pstderr("qmgr: Out of memory\n");
				clean_up_and_exit(5);
			} else if (i > 0)
				return (c - attrs);
			/* value ok */
			paol->value = v;

			/* Add special checks for syntax of value for certain attributes */
			i = chk_special_attr_values(paol);
			if (i > 0)			    /* error return,  i is offset of error in input */
				return (c - attrs + i - 1); /* c - attrs = start + offset is err loc */

			if (EOL(*e))
				return 0; /* end of line */
			c = e;		  /* otherwise more to parse */
		} else
			return (c - attrs);

		/* See if there is another attribute-value pair */
	next:
		while (White(*c))
			c++;
		if (EOL(*c))
			return 0;

		if (*c == ',')
			c++;
		else
			return (c - attrs);
	}
}

/**
 * @brief
 *	make_connection - open a connection to the server and assign
 *			  server entry
 *
 * @param[in] name - name of server to connect to
 *
 *	returns server struct if connection can be made or NULL if not
 *
 */
struct server *
make_connection(char *name)
{
	int connection;
	struct server *svr = NULL;

	if ((connection = cnt2server(name)) > 0) {
		svr = new_server();
		Mstring(svr->s_name, strlen(name) + 1);
		strcpy(svr->s_name, name);
		svr->s_connect = connection;
	} else
		PSTDERR1("qmgr: cannot connect to server %s\n", name)

	return svr;
}

/**
 * @brief
 *	connect_servers - call connect to connect to each server in list
 *			  and add then to the global server list
 *
 * @param[on] server_names - list of objnames
 * @param[in] numservers   - the number of servers to connect to or -1 for all
 *			 the servers on the list
 *
 * @return int
 * @retval False/1   Failure
 * @retval True      Success
 *
 */
int
connect_servers(struct objname *server_names, int numservers)
{
	int error = FALSE;
	struct server *cur_svr;
	struct objname *cur_obj;
	int i;
	int max_servers;

	max_servers = pbs_query_max_connections();

	close_non_ref_servers();

	if (nservers < max_servers) {
		cur_obj = server_names;

		/* if numservers == -1 (all servers) the var i will never equal zero */
		for (i = numservers; i && cur_obj; i--, cur_obj = cur_obj->next) {
			nservers++;
			if ((cur_svr = make_connection(cur_obj->svr_name)) == NULL) {
				nservers--;
				error = TRUE;
			}

			if (cur_svr != NULL) {
				cur_obj->svr = cur_svr;
				cur_svr->ref++;
				cur_svr->next = servers;
				servers = cur_svr;
			}
		}
	} else {
		pstderr("qmgr: max server connections reached.\n");
		error = 1;
	}
	return error;
}

/**
 * @brief
 *	blanks - print requested spaces
 *
 * @param[in] number - The number spaces
 *
 * @return Void
 *
 */
void
blanks(int number)
{
	char spaces[1024];
	int i;

	if (number < 1023) {
		for (i = 0; i < number; i++)
			spaces[i] = ' ';
		spaces[i] = '\0';

		pstderr(spaces);
	} else
		pstderr("Too many blanks requested.\n");
}

/**
 * @brief
 *	check_list - check a comma delimited list for valid syntax
 *
 * @param[in] list  - A comma delimited list.
 * @param[in] type  - server, queue, node, or resource
 *
 * valid syntax: name[@server][,name]
 *		example: batch@svr1,debug
 *
 * @return int
 * @retval	0	If the syntax of the list is correct for all commands.
 * @retval     >0	The number of chars into the list where the error occured
 *
 */
int
check_list(char *list, int type)
{
	char *foreptr, *backptr;

	backptr = list;

	while (!EOL(*backptr)) {
		foreptr = backptr;

		/* object names (except nodes ) have to start with an alpha character or
		 * can be left off if all object of the same type are wanted
		 */
		if (type == MGR_OBJ_NODE) {
			if (!isalnum((int) *backptr) && *backptr != '@')
				return (backptr - list ? backptr - list : 1);
		} else if (!isalpha((int) *backptr) && *backptr != '@')
			return (backptr - list ? backptr - list : 1);

		while (*foreptr != ',' && *foreptr != '@' && !EOL(*foreptr))
			foreptr++;

		if (*foreptr == '@') {
			foreptr++;

			/* error on "name@" or "name@," */
			if (EOL(*foreptr) || *foreptr == ',')
				return (foreptr - list);

			while (!EOL(*foreptr) && *foreptr != ',')
				foreptr++;

			/* error on name@svr@blah */
			if (*foreptr == '@')
				return (foreptr - list);
		}

		if (*foreptr == ',') {
			foreptr++;
			/* error on "name," */
			if (EOL(*foreptr))
				return (foreptr - list ? foreptr - list : 1);
		}
		backptr = foreptr;
	}
	return 0; /* Success! */
}

/**
 * @brief
 *	disconnect_from_server  - disconnect from one server and clean up
 *
 * @param[in] svr - the server to disconnect from
 *
 * @return  Void
 *
 */
static void
disconnect_from_server(struct server *svr)
{
	pbs_disconnect(svr->s_connect);
	free_server(svr);
	nservers--;
}

/**
 * @brief
 *	clean_up_and_exit - disconnect from the servers and free memory used
 *			    by active object lists and then exits
 *
 * @param[in]  exit_val - value to pass to exit
 *
 * @return Void
 *
 */
void
clean_up_and_exit(int exit_val)
{
	struct server *cur_svr, *next_svr;

	free(hook_tempdir);
	free(hook_tempfile);
	free_objname_list(active_servers);
	free_objname_list(active_queues);
	free_objname_list(active_nodes);

	cur_svr = servers;

	while (cur_svr) {
		next_svr = cur_svr->next;
		disconnect_from_server(cur_svr);
		cur_svr = next_svr;
	}

	/*cleanup security library initializations before exiting*/
	CS_close_app();

	exit(exit_val);
}

/**
 * @brief
 *	remove_char - remove char from a string
 *
 * @param[in]  ptr    pointer to a string
 * @param[in]  ch     character to be removed
 *
 * @return Void
 *
 */
void
remove_char(char *ptr, int ch)
{
	int index = 0;
	int i;
	for (i = 0; ptr[i] != '\0'; ++i)
		if (ptr[i] != ch)
			ptr[index++] = ptr[i];
	ptr[index] = '\0';
}

/**
 * @brief
 *	get_resc_type - for a named resource, look it up in the batch_status
 *	returned by pbs_statrsc().
 *
 * @return int
 * @retval 0	If the resource is not found, or if the type is not available,
 *
 */
int
get_resc_type(char *rname, struct batch_status *pbs)
{
	struct attrl *pat;

	while (pbs) {
		if (strcmp(rname, pbs->name) == 0) {
			pat = pbs->attribs;
			while (pat) {
				if (strcmp("type", pat->name) == 0)
					return (atoi(pat->value));
				pat = pat->next;
			}
			return 0;
		}
		pbs = pbs->next;
	}
	return 0;
}

/**
 * @brief
 *	Determine if a given queue name belongs to a reservation
 *
 * @param[in] sd    - server to which queue belongs
 * @param[in] qname - queue name to check
 *
 * @return Error code
 * @retval 0 if queue is not a reservation queue
 * @retval 1 if queue is a reservation queue
 *
 */
static int
is_reservation_queue(int sd, char *qname)
{
	struct batch_status *bs = NULL;
	struct attrl *resv_queue = NULL;

	/* pasing "" as value because DIS expects a non NULL value */
	set_attr_error_exit(&resv_queue, ATTR_queue, "");
	if (resv_queue != NULL) {
		bs = pbs_statresv(sd, NULL, resv_queue, NULL);
		while (bs != NULL) {
			if (bs->attribs != NULL && bs->attribs->value != NULL) {
				if (strcmp(qname, bs->attribs->value) == 0)
					break;
			}
			bs = bs->next;
		}
		if (resv_queue->name != NULL)
			free(resv_queue->name);
		free(resv_queue);
	}
	if (bs == NULL)
		return 0;
	pbs_statfree(bs);
	return 1;
}

/**
 * @brief
 *	display - format and output the status information.
 *
 * @par Functionality:
 * 	prints out all the information in a batch_status struct in either
 *	readable form (one attribute per line) or formated for inputing back
 *	into qmgr.
 *
 * @param[in]	otype	Object type, MGR_OBJ_*
 * @param[in]	ptype	Parent Object type, MGR_OBJ_*
 * @param[in]	oname	Object name
 * @param[in]	status	Attribute list of the object in form of batch_status
 * @param[in]	format	True, not zero, if the output should be formatted
 *			to look like qmgr command input
 * @param[in]	 mysvr	pointer to current "server" structure on which to find
 *		     info about resources
 *
 * @return	void
 *
 * @par Side Effects: None
 *
 */
void
display(int otype, int ptype, char *oname, struct batch_status *status,
	int format, struct server *mysvr)
{
	struct attrl *attr;
	char *c, *e;
	char q;
	int l, comma, do_comma, first, indent_len;
	char dump_msg[HOOK_MSG_SIZE];
	char *hooktmp = NULL;
	int custom_resource = FALSE;
	ecl_attribute_def *attrdef_l = NULL;
	int attrdef_size = 0, i;
	static struct attropl exp_attribs[] = {
		{(struct attropl *) &exp_attribs[1],
		 CONTENT_TYPE_PARAM,
		 NULL,
		 HOOKSTR_CONTENT,
		 SET},
		{(struct attropl *) &exp_attribs[2],
		 CONTENT_ENCODING_PARAM,
		 NULL,
		 HOOKSTR_BASE64,
		 SET},
		{NULL,
		 OUTPUT_FILE_PARAM,
		 NULL,
		 NULL, /* has to be constant in some compilers like IRIX */
		 SET},
	};

	static struct attropl exp_attribs_config[] = {
		{(struct attropl *) &exp_attribs_config[1],
		 CONTENT_TYPE_PARAM,
		 NULL,
		 HOOKSTR_CONFIG,
		 SET},
		{(struct attropl *) &exp_attribs_config[2],
		 CONTENT_ENCODING_PARAM,
		 NULL,
		 HOOKSTR_BASE64,
		 SET},
		{NULL,
		 OUTPUT_FILE_PARAM,
		 NULL,
		 NULL, /* has to be constant in some compilers like IRIX */
		 SET},
	};

	/* the OUTPUT_FILE_PARAM entry */
	hooktmp = base(hook_tempfile);
	exp_attribs[2].value = hooktmp ? hooktmp : "";
	exp_attribs_config[2].value = hooktmp ? hooktmp : "";

	if (format) {
		if (otype == MGR_OBJ_SERVER)
			printf("#\n# Set server attributes.\n#\n");
		else if (otype == MGR_OBJ_QUEUE)
			printf("#\n# Create queues and set their attributes.\n#\n");
		else if (otype == MGR_OBJ_NODE)
			printf("#\n# Create nodes and set their properties.\n#\n");
		else if (otype == MGR_OBJ_SITE_HOOK)
			printf("#\n# Create hooks and set their properties.\n#\n");
		else if (otype == MGR_OBJ_PBS_HOOK)
			printf("#\n# Set PBS hooks properties.\n#\n");
	}

	if (otype == MGR_OBJ_SERVER) {
		attrdef_l = ecl_svr_attr_def;
		attrdef_size = ecl_svr_attr_size;
	} else if (otype == MGR_OBJ_SCHED) {
		attrdef_l = ecl_sched_attr_def;
		attrdef_size = ecl_sched_attr_size;
	} else if (otype == MGR_OBJ_QUEUE) {
		attrdef_l = ecl_que_attr_def;
		attrdef_size = ecl_que_attr_size;
	} else if (otype == MGR_OBJ_NODE) {
		attrdef_l = ecl_node_attr_def;
		attrdef_size = ecl_node_attr_size;
	}

	while (status != NULL) {
		if (otype == MGR_OBJ_SERVER) {
			if (!format)
				printf("Server %s\n", status->name);
		} else if (otype == MGR_OBJ_SCHED) {
			if ((oname != NULL) && *oname && strcmp(oname, status->name)) {
				status = status->next;
				continue;
			}

			if (format) {
				printf("#\n# Create and define scheduler %s\n#\n", status->name);
				printf("create sched %s\n", status->name);
			} else
				printf("Sched %s\n", status->name);

		} else if (otype == MGR_OBJ_QUEUE) {
			/* When printing server, skip display of reservation queue. This is done
			 * to prevent recreating the reservation queue upon migration of a server
			 * configuration.
			 */
			if ((ptype == MGR_OBJ_SERVER) && is_reservation_queue(mysvr->s_connect,
									      status->name)) {
				status = status->next;
				continue;
			}
			if (format) {
				printf("#\n# Create and define queue %s\n#\n", status->name);
				printf("create queue %s\n", status->name);
			} else
				printf("Queue %s\n", status->name);
		} else if (otype == MGR_OBJ_NODE) {
			if (format) {
				first = TRUE;
				printf("#\n# Create and define node %s\n#\n", status->name);
				printf("create node %s", status->name);
				if ((c = get_attr(status->attribs, ATTR_NODE_Host, NULL)) != NULL) {
					if (strcmp(c, status->name) != 0) {
						printf(" %s=%s", ATTR_NODE_Mom, c);
						first = 0;
					}
				} else if ((c = get_attr(status->attribs, ATTR_NODE_Mom, NULL)) != NULL) {
					if (strcmp(c, status->name) != 0) {
						if (format && (strchr(c, (int) ',') != NULL))
							printf(" %s=\"%s\"", ATTR_NODE_Mom, c); /* quote value */
						else
							printf(" %s=%s", ATTR_NODE_Mom, c);
						first = 0;
					}
				}
				if ((c = get_attr(status->attribs, ATTR_NODE_Port, NULL)) != NULL) {
					if (atoi(c) != PBS_MOM_SERVICE_PORT) {
						if (first)
							printf(" ");
						else
							printf(",");
						printf("%s=%s", ATTR_NODE_Port, c);
					}
				}
				printf("\n");
			} else
				printf("Node %s\n", status->name);
		} else if (otype == MGR_OBJ_SITE_HOOK) {
			if (format) {
				printf("#\n# Create and define hook %s\n#\n", show_nonprint_chars(status->name));
				printf("create hook %s\n", show_nonprint_chars(status->name));
			} else
				printf("Hook %s\n", show_nonprint_chars(status->name));
		} else if (otype == MGR_OBJ_PBS_HOOK) {
			if (format) {
				printf("#\n# Set pbshook %s\n#\n", show_nonprint_chars(status->name));
			} else
				printf("Hook %s\n", show_nonprint_chars(status->name));
		} else if (otype == MGR_OBJ_RSC) {
			if ((oname == NULL) || (strcmp(oname, "") == 0)) {
				if (strcmp(status->name, RESOURCE_UNKNOWN) == 0) {
					custom_resource = TRUE;
					status = status->next;
					if (status)
						printf("#\n# Create resources and set their properties.\n#\n");
					continue;
				}
				if (custom_resource == FALSE) {
					status = status->next;
					continue;
				}
			}
			if (format) {
				printf("#\n# Create and define resource %s\n#\n", status->name);
				printf("create resource %s\n", status->name);
			} else
				printf("Resource %s\n", status->name);
		}

		attr = status->attribs;

		while (attr != NULL) {
			if (format) {
				if ((otype == MGR_OBJ_SITE_HOOK) || (otype == MGR_OBJ_PBS_HOOK) ||
				    is_attr(otype, attr->name, TYPE_ATTR_PUBLIC)) {
					if ((otype != MGR_OBJ_SITE_HOOK) && (otype != MGR_OBJ_PBS_HOOK) &&
					    ((strcmp(attr->name, ATTR_NODE_Host) == 0) ||
					     (strcmp(attr->name, ATTR_NODE_Mom) == 0) ||
					     (strcmp(attr->name, ATTR_NODE_Port) == 0))) {
						/* skip Host, Mom and Port, already done on line with name */
						attr = attr->next;
						continue;
					}
					if ((otype != MGR_OBJ_SITE_HOOK) && (otype != MGR_OBJ_PBS_HOOK) &&
					    (strcmp(attr->name, ATTR_NODE_state) == 0) &&
					    ((strncmp(attr->value, ND_state_unknown, strlen(ND_state_unknown)) == 0) ||
					     (strcmp(attr->value, ND_down) == 0))) {
						/* don't record "Down" or "state-unknown" */
						attr = attr->next;
						continue;
					}
					if (otype == MGR_OBJ_RSC) {
						if ((attr != NULL) && (strcmp(attr->name, ATTR_RESC_TYPE) == 0)) {
							struct resc_type_map *rtm = find_resc_type_map_by_typev(atoi(attr->value));
							if (rtm) {
								printf("set resource %s type = %s\n", status->name, rtm->rtm_rname);
							}
							attr = attr->next;
							continue;
						}
						if ((attr != NULL) && (strcmp(attr->name, ATTR_RESC_FLAG) == 0)) {
							char *rfm = find_resc_flag_map(atoi(attr->value));
							if ((rfm != NULL) && (strcmp(rfm, "") != 0)) {
								printf("set resource %s flag = %s\n", status->name, rfm);
							}
							attr = attr->next;
							continue;
						}
					}
					if ((attr->resource != NULL) &&
					    (get_resc_type(attr->resource, mysvr->s_rsc) == ATR_TYPE_STR))
						do_comma = FALSE; /* single string, don't parse substrings on a comma */
					else
						do_comma = TRUE;
					first = TRUE;
					c = attr->value;
					e = c;
					while (*c) {
						printf("set ");
						if (otype == MGR_OBJ_SERVER) {
							printf("server ");
						} else if (otype == MGR_OBJ_SCHED) {
							if (strcmp(status->name, PBS_DFLT_SCHED_NAME) == 0)
								printf("sched ");
							else
								printf("sched %s ", status->name);
						} else if (otype == MGR_OBJ_QUEUE) {
							printf("queue %s ", status->name);
						} else if (otype == MGR_OBJ_NODE) {
							printf("node %s ", status->name);
						} else if (otype == MGR_OBJ_SITE_HOOK)
							printf("hook %s ", show_nonprint_chars(status->name));
						else if (otype == MGR_OBJ_PBS_HOOK)
							printf("pbshook %s ", show_nonprint_chars(status->name));

						if (attr->name != NULL)
							printf("%s", attr->name);
						if (attr->resource != NULL)
							printf(".%s", attr->resource);
						if (attr->value != NULL) {
							for (i = 0; i < attrdef_size; i++) {
								if (strcmp(attr->name, attrdef_l[i].at_name) == 0) {
									break;
								}
							}
							if ((attrdef_l != NULL) && (attrdef_l[i].at_type == ATR_TYPE_STR)) {
								if (strpbrk(c, "\"' ,") != NULL) {
									if (strchr(c, (int) '"'))
										q = '\'';
									else
										q = '"';
									printf(" = %c%s%c\n", q, show_nonprint_chars(c), q);
								} else
									printf(" = %s\n", show_nonprint_chars(c));
								break;
							} else {
								if (attr->op == INCR)
									printf(" += ");
								else if (first)
									printf(" = ");
								else
									printf(" += ");

								first = FALSE;

								while (*e) {
									if ((do_comma == TRUE) && (*e == ',')) {
										*e++ = '\0';
										break;
									}
									e++;
								}
								if (strpbrk(c, "\"' ,") != NULL) {
									/* need to quote string */
									if (strchr(c, (int) '"'))
										q = '\'';
									else
										q = '"';
									printf("%c%s%c", q, show_nonprint_chars(c), q);
								} else
									printf("%s", show_nonprint_chars(c)); /* no quoting */

								c = e;
							}
						}

						printf("\n");
					}
				}
			} else {
				indent_len = 4;
				if (otype == MGR_OBJ_RSC) {
					if ((attr != NULL) && (strcmp(attr->name, "type") == 0)) {
						struct resc_type_map *rtm = find_resc_type_map_by_typev(atoi(attr->value));
						if (rtm) {
							printf("%*s", indent_len, " ");
							printf("type = %s\n", rtm->rtm_rname);
						}
					} else if ((attr != NULL) && (strcmp(attr->name, "flag") == 0)) {
						char *rfm = find_resc_flag_map(atoi(attr->value));
						if ((rfm != NULL) && (strcmp(rfm, "") != 0)) {
							printf("%*s", indent_len, " ");
							printf("flag = %s\n", rfm);
						}
					}
					attr = attr->next;
					continue;
				}

				if (attr->name != NULL) {
					printf("%*s", indent_len, " ");
					printf("%s", attr->name);
				}

				if (attr->resource != NULL)
					printf(".%s", attr->resource);

				if (attr->value != NULL) {
					l = strlen(attr->name) + 8;

					if (attr->resource != NULL)
						l += strlen(attr->resource) + 1;

					l += 3; /* length of " = " */
					printf(" = ");
					c = attr->value;
					e = c;
					comma = TRUE;
					first = TRUE;
					while (comma) {
						while (*e != ',' && *e != '\0')
							e++;

						comma = (*e == ',');
						*e = '\0';
						l += strlen(c) + 1;

						if (!first && (l >= 80)) { /* line extension */
							printf("\n\t");
							while (White(*c))
								c++;
						}

						printf("%s", show_nonprint_chars(c));
						first = FALSE;

						if (comma) {
							printf(",");
							*e = ',';
						}

						e++;
						c = e;
					}
					printf("\n");
				}
			}
			attr = attr->next;
		}
		if (!format) {
			printf("\n");
		} else {
			if (otype == MGR_OBJ_SITE_HOOK) {
				if (exp_attribs[2].value[0] == '\0') {
					fprintf(stderr, "%s", hook_tempfile_errmsg);
					fprintf(stderr, "can't display hooks data - no hook_tempfile!\n");
				} else if (pbs_manager(mysvr->s_connect, MGR_CMD_EXPORT, otype,
						       status->name, exp_attribs, NULL) == 0) {
					printf(PRINT_HOOK_IMPORT_CALL, show_nonprint_chars(status->name));
					if (dump_file(hook_tempfile, NULL, HOOKSTR_BASE64,
						      dump_msg, sizeof(dump_msg)) != 0) {
						fprintf(stderr, "%s\n", dump_msg);
					}
					printf("\n");
				}
				if (exp_attribs_config[2].value[0] == '\0') {
					fprintf(stderr, "%s", hook_tempfile_errmsg);
					fprintf(stderr, "can't display hooks data - no hook_tempfile!\n");
				} else if (pbs_manager(mysvr->s_connect, MGR_CMD_EXPORT, otype,
						       status->name, exp_attribs_config, NULL) == 0) {
					printf(PRINT_HOOK_IMPORT_CONFIG, show_nonprint_chars(status->name));
					if (dump_file(hook_tempfile, NULL, HOOKSTR_BASE64,
						      dump_msg, sizeof(dump_msg)) != 0) {
						fprintf(stderr, "%s\n", dump_msg);
					}
					printf("\n");
				}
			} else if (otype == MGR_OBJ_PBS_HOOK) {
				if (exp_attribs_config[2].value[0] == '\0') {
					fprintf(stderr, "%s", hook_tempfile_errmsg);
					fprintf(stderr, "can't display pbs hooks data - no hook_tempfile!\n");
				} else if (pbs_manager(mysvr->s_connect, MGR_CMD_EXPORT, otype,
						       status->name, exp_attribs_config, NULL) == 0) {
					printf(PRINT_HOOK_IMPORT_CONFIG, show_nonprint_chars(status->name));
					if (dump_file(hook_tempfile, NULL, HOOKSTR_BASE64,
						      dump_msg, sizeof(dump_msg)) != 0) {
						fprintf(stderr, "%s\n", dump_msg);
					}
					printf("\n");
				}
			}
		}
		status = status->next;
	}
}

/**
 * @brief
 *	set_active - sets active objects
 *
 * @param[in] obj_type - the type of object - should be caller allocated space
 * @parm[in]  obj_names - names of objects to set active
 *
 * @return  Error code
 * @retval  0  on success
 * @retval  !0 on failure
 *
 */
int
set_active(int obj_type, struct objname *obj_names)
{
	struct objname *cur_obj = NULL;
	struct server *svr;
	int error = 0;

	if (obj_names != NULL) {
		switch (obj_type) {
			case MGR_OBJ_SERVER:
				cur_obj = obj_names;
				while (cur_obj != NULL && !error) {
					if (cur_obj->svr == NULL) {
						svr = find_server(cur_obj->obj_name);
						if (svr == NULL)
							error = connect_servers(cur_obj, 1);
						else {
							cur_obj->svr = svr;
							svr->ref++;
						}
					}

					cur_obj = cur_obj->next;
				}
				if (!error) {
					free_objname_list(active_servers);
					active_servers = obj_names;
				} else
					free_objname_list(obj_names);

				break;

			case MGR_OBJ_SCHED:
				cur_obj = obj_names;
				while (cur_obj != NULL && !error) {
					if (cur_obj->svr == NULL) {
						svr = find_server(cur_obj->obj_name);
						if (svr == NULL)
							error = connect_servers(cur_obj, 1);
						else {
							cur_obj->svr = svr;
							svr->ref++;
						}
					}

					cur_obj = cur_obj->next;
				}
				if (!error) {
					free_objname_list(active_scheds);
					active_scheds = obj_names;
				} else
					free_objname_list(obj_names);

				break;

			case MGR_OBJ_QUEUE:
				cur_obj = obj_names;

				while (cur_obj != NULL && !error) {
					if (cur_obj->svr_name != NULL) {
						if (cur_obj->svr == NULL)
							if (connect_servers(cur_obj, 1) == TRUE)
								error = 1;
					}

					if (!is_valid_object(cur_obj, MGR_OBJ_QUEUE)) {
						PSTDERR1("Queue does not exist: %s.\n", cur_obj->obj_name)
						error = 1;
					}

					cur_obj = cur_obj->next;
				}

				if (!error) {
					free_objname_list(active_queues);
					active_queues = obj_names;
				}
				break;

			case MGR_OBJ_NODE:
				cur_obj = obj_names;
				while (cur_obj != NULL && !error) {
					if (cur_obj->svr_name != NULL) {
						if (cur_obj->svr == NULL)
							if (connect_servers(cur_obj, 1) == TRUE)
								error = 1;
					}
					if (!is_valid_object(cur_obj, MGR_OBJ_NODE)) {
						PSTDERR1("Node does not exist: %s.\n", cur_obj->obj_name)
						error = 1;
					}

					cur_obj = cur_obj->next;
				}

				if (!error) {
					free_objname_list(active_nodes);
					active_nodes = obj_names;
				}
				break;

			default:
				error = 1;
		}
	} else {
		switch (obj_type) {
			case MGR_OBJ_SERVER:
				printf("Active servers:\n");
				cur_obj = active_servers;
				break;
			case MGR_OBJ_SCHED:
				printf("Active schedulers:\n");
				cur_obj = active_scheds;
				break;
			case MGR_OBJ_QUEUE:
				printf("Active queues:\n");
				cur_obj = active_queues;
				break;
			case MGR_OBJ_NODE:
				printf("Active nodes:\n");
				cur_obj = active_nodes;
				break;
		}
		while (cur_obj != NULL) {
			if (obj_type == MGR_OBJ_SERVER)
				printf("%s\n", Svrname(cur_obj->svr));
			else
				printf("%s@%s\n", cur_obj->obj_name, Svrname(cur_obj->svr));

			cur_obj = cur_obj->next;
		}
	}

	return error;
}

/**
 * @brief
 *	handle_formula - if we're setting the formula, we need to write the
 *			value into a root owned file, instead of sending it over
 *			the wire.  This	is because of the fact that we run it as root
 *
 * @param[in] attribs - the attribute we're setting
 *
 * @return Void
 *
 */
void
handle_formula(struct attropl *attribs)
{
	struct attropl *pattr;
	char pathbuf[MAXPATHLEN + 1];
	FILE *fp;

	for (pattr = attribs; pattr != NULL; pattr = pattr->next) {
		if (!strcmp(pattr->name, ATTR_job_sort_formula) && pattr->op == SET) {
			sprintf(pathbuf, "%s/%s", pbs_conf.pbs_home_path, FORMULA_ATTR_PATH);
			if ((fp = fopen(pathbuf, "w")) != NULL) {
				fprintf(fp, "%s\n", pattr->value);
				fclose(fp);
#ifdef WIN32
				/* Give file an Administrators permission so pbs server can read it */
				secure_file(pathbuf, "Administrators",
					    READS_MASK | WRITES_MASK | STANDARD_RIGHTS_REQUIRED);
#endif
			} else {
				PSTDERR1("qmgr: Failed to open %s for writing.\n", pathbuf)
				return;
			}
		}
	}
	return;
}

/**
 * @brief
 * 	execute - contact the server and execute the command
 *
 * @param[in] aopt      True, if the -a option was given.
 * @param[in] oper      The command, either create, delete, set, unset or list.
 * @param[in] type      The object type, either server or queue.
 * @param[in] names     The object name list.
 * @param[in] attribs   The attribute list with operators.
 *
 * @return int
 * @retval 0 for success
 * @retval non-zero for error
 *
 * @par
 * Uses the following library calls from libpbs:
 *          pbs_manager
 *          pbs_statserver
 *          pbs_statque
 *          pbs_statsched
 *          pbs_statfree
 *          pbs_geterrmsg
 *
 */
int
execute(int aopt, int oper, int type, char *names, struct attropl *attribs)
{
	int len; /* Used for length of an err msg*/
	int cerror;
	int error; /* Error value returned */
	int perr;  /* Value returned from pbs_manager */
	char *pmsg;
	char *errmsg;		      /* Error message from pbs_errmsg */
	char errnomsg[256];	      /* Error message with pbs_errno */
	struct objname *name;	      /* Pointer to a list of object names */
	struct objname *pname = NULL; /* Pointer to current object name */
	struct objname *sname = NULL; /* Pointer to current server name */
	struct objname *svrs;	      /* servers to loop through */
	struct attrl *sa;	      /* Argument needed for status routines */
	/* Argument used to request queue names */
	struct server *sp; /* Pointer to server structure */
	/* Return structure from a list or print request */
	struct batch_status *ss = NULL;
	struct attropl *attribs_tmp = NULL;
	struct attropl *attribs_file = NULL;
	char infile[MAXPATHLEN + 1];
	char outfile[MAXPATHLEN + 1];
	char dump_msg[HOOK_MSG_SIZE];
	char content_encoding[HOOK_BUF_SIZE];
	char content_type[HOOK_BUF_SIZE];
	error = 0;
	name = commalist2objname(names, type);

	if (oper == MGR_CMD_ACTIVE)
		return set_active(type, name);

	if (name == NULL) {
		switch (type) {
				/* There will always be an active server */
			case MGR_OBJ_SCHED:
			case MGR_OBJ_SERVER:
			case MGR_OBJ_SITE_HOOK:
			case MGR_OBJ_PBS_HOOK:
			case MGR_OBJ_RSC:
				pname = active_servers;
				break;
			case MGR_OBJ_QUEUE:
				if (active_queues != NULL)
					pname = active_queues;
				else
					pstderr("No Active Queues, nothing done.\n");
				break;
			case MGR_OBJ_NODE:
				if (active_nodes != NULL)
					pname = active_nodes;
				else
					pstderr("No Active Nodes, nothing done.\n");
				break;
		}
	} else
		pname = name;

	for (; pname != NULL; pname = pname->next) {
		if (pname->svr_name != NULL)
			svrs = temp_objname(NULL, pname->svr_name, pname->svr);
		else
			svrs = active_servers;

		for (sname = svrs; sname != NULL; sname = sname->next) {
			if (sname->svr == NULL) {
				cerror = connect_servers(sname, 1);
				/* if connect_servers() returned an error   */
				/* update "error", otherwise leave it alone */
				/* so that any prior error is retained      */
				if (cerror) {
					error = cerror;
					continue;
				}
			}

			sp = sname->svr;
			if (oper == MGR_CMD_LIST) {
				sa = attropl2attrl(attribs);
				switch (type) {
					case MGR_OBJ_SERVER:
						ss = pbs_statserver(sp->s_connect, sa, NULL);
						break;
					case MGR_OBJ_QUEUE:
						ss = pbs_statque(sp->s_connect, pname->obj_name, sa, NULL);
						break;
					case MGR_OBJ_NODE:
						ss = pbs_statvnode(sp->s_connect, pname->obj_name, sa, NULL);
						break;
					case MGR_OBJ_SCHED:
						ss = pbs_statsched(sp->s_connect, sa, NULL);
						break;
					case MGR_OBJ_SITE_HOOK:
						ss = pbs_stathook(sp->s_connect, pname->obj_name, sa, SITE_HOOK);
						break;
					case MGR_OBJ_PBS_HOOK:
						ss = pbs_stathook(sp->s_connect, pname->obj_name, sa, PBS_HOOK);
						break;
					case MGR_OBJ_RSC:
						ss = pbs_statrsc(sp->s_connect, pname->obj_name, sa, "p");
						break;
				}
				free_attrl_list(sa);
				perr = (ss == NULL);
				if (!perr)
					display(type, type, pname->obj_name, ss, FALSE, sp);

				/* For 'list hook' command of all available */
				/* hooks, if none are found in the system, */
				/* then force a return success value.   */
				if ((perr != 0) &&
				    ((type == MGR_OBJ_SITE_HOOK) ||
				     (type == MGR_OBJ_PBS_HOOK)) &&
				    ((pname->obj_name == NULL) ||
				     (pname->obj_name[0] == '\0'))) {
					/* not an error */
					perr = 0;
				}

				pbs_statfree(ss);
			} else if (oper == MGR_CMD_PRINT) {

				sa = attropl2attrl(attribs);
				switch (type) {
					case MGR_OBJ_SERVER:
						if (sa == NULL) {
							sp->s_rsc = pbs_statrsc(sp->s_connect, NULL, NULL, "p");
							if (sp->s_rsc != NULL) {
								display(MGR_OBJ_RSC, MGR_OBJ_SERVER, NULL, sp->s_rsc, TRUE, sp);
							} else if (pbs_errno != PBSE_NONE) {
								break;
							}
							ss = pbs_statque(sp->s_connect, NULL, NULL, NULL);
							if (ss != NULL) {
								display(MGR_OBJ_QUEUE, MGR_OBJ_SERVER, NULL, ss, TRUE, sp);
							} else if (pbs_errno != PBSE_NONE) {
								break;
							}
						}
						ss = pbs_statserver(sp->s_connect, sa, NULL);
						break;
					case MGR_OBJ_QUEUE:
						ss = pbs_statque(sp->s_connect, pname->obj_name, sa, NULL);
						break;
					case MGR_OBJ_NODE:
						ss = pbs_statvnode(sp->s_connect, pname->obj_name, sa, NULL);
						break;
					case MGR_OBJ_SCHED:
						ss = pbs_statsched(sp->s_connect, sa, NULL);
						break;
					case MGR_OBJ_SITE_HOOK:
						ss = pbs_stathook(sp->s_connect, pname->obj_name, sa, SITE_HOOK);
						break;
					case MGR_OBJ_RSC:
						ss = pbs_statrsc(sp->s_connect, pname->obj_name, sa, "p");
						break;
				}

				free_attrl_list(sa);
				perr = (ss == NULL);
				if (!perr) {
					display(type, type, pname->obj_name, ss, TRUE, sp);
				}
				pbs_statfree(ss);
			} else {
				if (oper == MGR_CMD_IMPORT) {
					infile[0] = '\0';
					content_encoding[0] = '\0';
					content_type[0] = '\0';
					attribs_tmp = attribs;
					attribs_file = NULL;
					while (attribs_tmp) {
						if (strcmp(attribs_tmp->name, INPUT_FILE_PARAM) == 0) {
							pbs_strncpy(infile, attribs_tmp->value, sizeof(infile));
							attribs_file = attribs_tmp;
						} else if (strcmp(attribs_tmp->name, CONTENT_ENCODING_PARAM) == 0) {
							pbs_strncpy(content_encoding, attribs_tmp->value, sizeof(content_encoding));
						} else if (strcmp(attribs_tmp->name, CONTENT_TYPE_PARAM) == 0) {
							pbs_strncpy(content_type, attribs_tmp->value, sizeof(content_type));
						}
						attribs_tmp = attribs_tmp->next;
					}
					if (infile[0] == '\0') {
						fprintf(stderr,
							"hook import command has no <input-file> argument\n");
						error = 1;
						continue;
					}
					if (content_encoding[0] == '\0') {
						fprintf(stderr,
							"hook import command has no <content-encoding> argument\n");
						error = 1;
						continue;
					}
					if (content_type[0] == '\0') {
						fprintf(stderr,
							"hook import command has no <content-type> argument\n");
						error = 1;
						continue;
					}

					if (strcmp(infile, "-") == 0) {
						infile[0] = '\0';
					}

					if (strcmp(content_type, HOOKSTR_CONFIG) == 0) {
						char *p;
						int totlen;
						p = strrchr(infile, '.');
						/* need to pass the suffix */
						/* to the server which will */
						/* validate the file based */
						/* on type */
						if (p != NULL) {
							totlen = strlen(p) + strlen(hook_tempfile);

							if (totlen < sizeof(hook_tempfile))
								strcat(hook_tempfile, p);
						}
					}

					/* hook_tempfile could be set to empty if generating this filename */
					/* by mktemp() was not successful */
					if ((hook_tempfile[0] == '\0') ||
					    dump_file(infile, hook_tempfile, content_encoding,
						      dump_msg, sizeof(dump_msg)) != 0) {
						struct stat sbuf;

						error = 1; /* set error indicator */

						if (hook_tempfile_errmsg[0] != '\0')
							fprintf(stderr, "%s\n", hook_tempfile_errmsg);

							/* Detect failed to access hooks working directory */

#ifdef WIN32
						if ((lstat(hook_tempdir, &sbuf) == -1) && (GetLastError() == ERROR_ACCESS_DENIED))
#else
						if ((stat(hook_tempdir, &sbuf) == -1) && (errno == EACCES))
#endif
						{
							fprintf(stderr, "%s@%s is unauthorized to access hooks data "
									"from server %s\n",
								cur_user, cur_host,
								(sname->svr_name[0] == '\0') ? pbs_conf.pbs_server_name : sname->svr_name);
						} else {
							fprintf(stderr, "%s\n", dump_msg);
						}
						continue;
					}

					dyn_strcpy(&attribs_file->value, base(hook_tempfile));

				} else if (oper == MGR_CMD_EXPORT) {
					char *hooktmp = NULL;

					if (hook_tempfile[0] == '\0') {

						struct stat sbuf;

						error = 1;

						if (hook_tempfile_errmsg[0] != '\0')
							fprintf(stderr, "%s\n", hook_tempfile_errmsg);

							/* Detect failed to access hooks working directory */
#ifdef WIN32
						if ((lstat(hook_tempdir, &sbuf) == -1) && (GetLastError() == ERROR_ACCESS_DENIED))
#else
						if ((stat(hook_tempdir, &sbuf) == -1) && (errno == EACCES))
#endif
						{
							fprintf(stderr, "%s@%s is unauthorized to access hooks data "
									"from server %s\n",
								cur_user, cur_host,
								(sname->svr_name[0] == '\0') ? conf_full_server_name : sname->svr_name);
						} else {
							fprintf(stderr, "can't export hooks data. no hook_tempfile!\n");
						}
						continue;
					}
					outfile[0] = '\0';
					content_encoding[0] = '\0';
					attribs_tmp = attribs;
					attribs_file = NULL;
					while (attribs_tmp) {
						if (strcmp(attribs_tmp->name, OUTPUT_FILE_PARAM) == 0) {
							pbs_strncpy(outfile, attribs_tmp->value, sizeof(outfile));
							attribs_file = attribs_tmp;
						} else if (strcmp(attribs_tmp->name,
								  CONTENT_ENCODING_PARAM) == 0) {
							pbs_strncpy(content_encoding, attribs_tmp->value, sizeof(content_encoding));
						}
						attribs_tmp = attribs_tmp->next;
					}
					hooktmp = base(hook_tempfile);
					/* dyn_strcpy does not like a NULL second argument. */
					dyn_strcpy(&attribs_file->value, (hooktmp ? hooktmp : ""));
				}
				handle_formula(attribs);
				if (type == MGR_OBJ_PBS_HOOK) {
					struct attropl *popl;
					perr = pbs_manager(sp->s_connect, oper, type, pname->obj_name, attribs, PBS_HOOK);

					popl = attribs;
					if (perr == 0) {
						while (popl != NULL) {

							if (strcmp(popl->name, "enabled") != 0) {
								popl = popl->next;
								continue;
							}
							if ((strcasecmp(popl->value, HOOKSTR_FALSE) == 0) ||
							    (strcasecmp(popl->value, "f") == 0) ||
							    (strcasecmp(popl->value, "n") == 0) ||
							    (strcmp(popl->value, "0") == 0)) {
								fprintf(stderr, "WARNING: Disabling a PBS hook "
										"results in an unsupported configuration!\n");
							}
							popl = popl->next;
						}
					}
				} else {
					if ((strlen(pname->obj_name) == 0) && type == MGR_OBJ_SCHED && oper != MGR_CMD_DELETE) {
						perr = pbs_manager(sp->s_connect, oper, type, PBS_DFLT_SCHED_NAME, attribs, NULL);
					} else
						perr = pbs_manager(sp->s_connect, oper, type, pname->obj_name, attribs, NULL);
				}
			}

			errmsg = pbs_geterrmsg(sp->s_connect);
			if (perr) {
				/*
				 ** IF
				 **	stdin is a tty			OR
				 **	the command is not SET		OR
				 **	the object type is not NODE	OR
				 **	the error is not "attempt to set READ ONLY attribute"
				 ** THEN print error messages
				 ** ELSE don't print error messages
				 **
				 ** This is to deal with bug 4941 where errors are generated
				 ** from running qmgr with input from a file which was generated
				 ** by 'qmgr -c "p n @default" > /tmp/nodes_out'.
				 */
				if (isatty(0) ||
				    (oper != MGR_CMD_SET) || (type != MGR_OBJ_NODE) ||
				    (pbs_errno != PBSE_ATTRRO)) {
					if (errmsg != NULL) {
						len = strlen(errmsg) + strlen(pname->obj_name) + strlen(Svrname(sp)) + 20;
						if (len < 256) {
							sprintf(errnomsg, "qmgr obj=%s svr=%s: %s\n",
								pname->obj_name, Svrname(sp), errmsg);
							pstderr(errnomsg);
						} else {
							/*obviously, this is to cover a highly unlikely case*/

							pstderr_big(Svrname(sp), pname->obj_name, errmsg);
						}
					}

					if (pbs_errno == PBSE_PROTOCOL) {
						if ((check_time - start_time) >= QMGR_TIMEOUT) {
							pstderr("qmgr: Server disconnected due to idle connection timeout\n");
						} else {
							pstderr("qmgr: Protocol error, server disconnected\n");
						}
						exit(1);
					} else if (pbs_errno == PBSE_HOOKERROR) {
						pstderr("qmgr: hook error returned from server\n");
					} else if (pbs_errno != 0) /* 0 happens with hooks if no hooks found */
						PSTDERR1("qmgr: Error (%d) returned from server\n", pbs_errno)
				}

				if (aopt)
					return perr;
				error = perr;
			} else if (errmsg != NULL) {
				/* batch reply code is 0 but a text message is also being returned */

				if ((pmsg = malloc(strlen(errmsg) + 2)) != NULL) {
					strcpy(pmsg, errmsg);
					strcat(pmsg, "\n");
					pstderr(pmsg);
					free(pmsg);
				}
			} else {

				if (oper == MGR_CMD_EXPORT) {
					if (dump_file(hook_tempfile, outfile, content_encoding,
						      dump_msg, sizeof(dump_msg)) != 0) {
						fprintf(stderr, "%s\n", dump_msg);
						error = 1;
					}
				}
			}

			temp_objname(NULL, NULL, NULL); /* clears reference count */
		}
	}
	if (name != NULL)
		free_objname_list(name);
	return error;
}

/**
 * @brief
 *	frees the attribute list
 *
 * @param[in] attr   Pointer to the linked list of attropls to clean up.
 *
 * @return Void
 *
 */
void
freeattropl(struct attropl *attr)
{
	struct attropl *ap;

	while (attr != NULL) {
		if (attr->name != NULL)
			free(attr->name);
		if (attr->resource != NULL)
			free(attr->resource);
		if (attr->value != NULL)
			free(attr->value);
		ap = attr->next;
		free(attr);
		attr = ap;
	}
}

/**
 * @brief
 *	commalist2objname - convert a comma seperated list of strings to a
 *			    linked list of objname structs
 *
 * @param[in] names - comma seperated list of strings
 * @param[in] type - the type of the objects
 *
 * @return  structure
 * @retval  linked list of objname structs
 *
 */
struct objname *
commalist2objname(char *names, int type)
{
	char *foreptr, *backptr;	 /* front and back of words */
	struct objname *objs = NULL;	 /* the front of the name object list */
	struct objname *cur_obj;	 /* the current name object */
	struct objname *prev_obj = NULL; /* the previous name object */
	int len;			 /* length of segment of string */
	char error = 0;			 /* error flag */

	if (names != NULL) {
		foreptr = backptr = names;
		while (!EOL(*foreptr) && !error) {
			while (White(*foreptr))
				foreptr++;

			backptr = foreptr;

			while (*foreptr != ',' && *foreptr != '@' && !EOL(*foreptr))
				foreptr++;

			cur_obj = new_objname();
			cur_obj->obj_type = type;
			if (*foreptr == '@') {
				len = foreptr - backptr;
				Mstring(cur_obj->obj_name, len + 1);
				pbs_strncpy(cur_obj->obj_name, backptr, len + 1);
				foreptr++;
				backptr = foreptr;
				while (*foreptr != ',' && !EOL(*foreptr))
					foreptr++;

				len = foreptr - backptr;
				if (strncmp(backptr, DEFAULT_SERVER, len) == 0) {
					Mstring(cur_obj->svr_name, 1);
					cur_obj->svr_name[0] = '\0';
				} else if (strncmp(backptr, ACTIVE_SERVER, len) == 0)
					cur_obj->svr_name = NULL;
				else {
					Mstring(cur_obj->svr_name, len + 1);
					pbs_strncpy(cur_obj->svr_name, backptr, len + 1);
				}

				if (!EOL(*foreptr))
					foreptr++;
			} else {
				len = foreptr - backptr;

				if ((type == MGR_OBJ_SERVER || type == MGR_OBJ_SITE_HOOK || type == MGR_OBJ_PBS_HOOK) && !strcmp(backptr, DEFAULT_SERVER)) {
					Mstring(cur_obj->obj_name, 1);
					cur_obj->obj_name[0] = '\0';
				} else {
					Mstring(cur_obj->obj_name, len + 1);
					pbs_strncpy(cur_obj->obj_name, backptr, len + 1);
				}

				if (type == MGR_OBJ_SERVER)
					cur_obj->svr_name = cur_obj->obj_name;

				if (!EOL(*foreptr))
					foreptr++;
			}

			if ((cur_obj->svr = find_server(cur_obj->svr_name)) != NULL)
				cur_obj->svr->ref++;

			if (objs == NULL)
				objs = cur_obj;

			if (prev_obj == NULL)
				prev_obj = cur_obj;
			else if (cur_obj != NULL) {
				prev_obj->next = cur_obj;
				prev_obj = cur_obj;
			}
		}
	}

	if (error) {
		free_objname_list(objs);
		return NULL;
	}

	return objs;
}

/**
 * @brief
 *	get_request - get a qmgr request from the standard input
 *
 * @param[out] request      The buffer for the qmgr request
 *
 * @return Error code
 * @retval 0     Success
 * @retval EOF   Failure
 *
 * NOTE:
 *      This routine has a static buffer it keeps lines of input in.
 * Since commands can be separated by semicolons, a line may contain
 * more than one command.  In this case, the command is copied to
 * request and the rest of the line is moved up to overwrite the previous
 * command.  Another line is retrieved from stdin only if the buffer is
 * empty
 *
 */
int
get_request(char **request)
{
	static char *line = NULL; /* Stdin line */
	static int empty = TRUE;  /* Line has nothing in it */
	int eol;		  /* End of line */
	int ll;			  /* Length of line */
	int i = 0;		  /* Index into line */
	char *rp;		  /* Pointer into request */
	char *lp;		  /* Pointer into line */
	int eoc;		  /* End of command */
	char quote;		  /* Either ' or " */
	char *cur_line = NULL;	  /* Pointer to the current line */
	int line_len = 0;	  /* Length of the line buffer */

#ifdef QMGR_HAVE_HIST
	if (qmgr_hist_enabled == 1) {
		if (empty) {
			if (line != NULL) {
				free(line);
				line = NULL;
			}

			if (get_request_hist(&cur_line) == EOF)
				return EOF;
		}
	}
#endif

	/* Make sure something is in the stdin line */
	if (empty) {
		eol = FALSE;
		lp = line;
		ll = 0;
		while (!eol) {
			/* The following code block (enclosed within if() {}) is executed only for the special case of
 			 * qmgr Commands being supplied from a file or within delimiters e.g. $qmgr < cmd_file.txt, where
			 * cmd_file.txt contains Commands ... or
			 * $qmgr <<EOF
 			 * p q workq
 			 * EOF <--- EOF is a delimiter.
 			 * This code block is not needed for the cases where qmgr receives input Interactively
 			 * or from the Command Line, since these checks already get done in get_request_hist().
 			 */
			if (qmgr_hist_enabled == 0) {
				if (isatty(0) && isatty(1)) {
					if (lp == line)
						printf("%s", prompt);
					else
						printf("%s", contin);
				}

				start_time = time(0);
				ll = 0;
				if ((cur_line = pbs_fgets(&cur_line, &ll, stdin)) == NULL) {
					if (line != NULL) {
						free(line);
						line = NULL;
					}
					return EOF;
				}
				ll = strlen(cur_line);
				if (cur_line[ll - 1] == '\n') {
					/* remove newline */
					cur_line[ll - 1] = '\0';
					--ll;
				}
				lp = cur_line;

				while (White(*lp))
					lp++;

				if (strlen(lp) == 0) {
					if (cur_line != NULL) {
						free(cur_line);
						cur_line = NULL;
						lp = line;
					}
					continue;
				}
			} else {
				ll = strlen(cur_line);
				lp = cur_line;
			}

			if (cur_line[ll - 1] == '\\') {
				cur_line[ll - 1] = ' ';
			} else if (*lp != '#')
				eol = TRUE;

			if (*lp != '#') {
				if (line != NULL) {
					line_len = strlen(line);
				} else {
					line_len = 0;
				}
				/*
				 * Append the contents of cur_line to the earlier line buffer
				 * pbs_strcat takes care of increasing the size of the destination
				 * buffer if required.
				 */
				if ((pbs_strcat(&line, &line_len, cur_line)) == NULL) {
					fprintf(stderr, "malloc failure (errno %d)\n", errno);
					exit(1);
				}
			}
			if (cur_line != NULL) {
				free(cur_line);
			}
		} /* End while(). */
	}	  /* End if(empty). */

	/* Move a command from line to request */
	ll = strlen(line);
	*request = (char *) malloc(ll + 1);
	if (*request == NULL) {
		fprintf(stderr, "malloc failure (errno %d)\n", errno);
		exit(1);
	}
	(*request)[ll] = '\0';
	rp = *request;
	lp = line;
	eoc = FALSE;
	while (!eoc) {
		switch (*lp) {
				/* End of command */
			case ';':
			case '\0':
				eoc = TRUE;
				break;

				/* Quoted string */
			case '"':
			case '\'':
				quote = *lp;
				*rp = *lp;
				rp++;
				lp++;
				while (*lp != quote && !EOL(*lp)) {
					*rp = *lp;
					rp++;
					lp++;
				}
				*rp = *lp;
				if (!EOL(*lp)) {
					rp++;
					lp++;
				}
				break;

			case '#':
				if ((lp == line) || isspace(*(lp - 1))) {
					/* comment */
					eoc = TRUE;
					break;
				} /* not comment, fall into default case */
				  /* Move the character */
			default:
				*rp = *lp;
				rp++;
				lp++;
				break;
		}
	}
	*rp = '\0';

	/* Is there any thing left in the line? */
	switch (*lp) {
		case '\0':
		case '#':
			i = 0;
			empty = TRUE;
			break;

		case ';':
			rp = line;
			lp++;
			while (White(*lp))
				lp++;
			if (!EOL(*lp)) {
				i = strlen(lp);
				memmove(rp, lp, (size_t) i); /* By using memmove() we avoid strcpy's overlapping buffer issue. */
				empty = FALSE;		     /* Note: memmove() doesn't Null terminate; so we take care of this by */
			}				     /* nullifying 'line', at the end of this function, by setting line[i] to '\0'. */
			else {
				i = 0;
				empty = TRUE;
			}
			break;
	}

	line[i] = '\0'; /* Nullify the 'line' buffer at position 'i'. The un-processed command(s) got copied */
			/* to the start of the 'line' buffer by memmove() above. These command(s) are now */
			/* Null terminated appropriately. */

	return 0;
}

/**
 * @brief
 *	show_help - show help for qmgr
 *
 * @param[in] str - possible sub topic to show help on
 *
 * @return Void
 *
 */
void
show_help(char *str)
{
	if (str != NULL) {
		while (White(*str))
			str++;
	}

	if ((str == NULL) || (*str == '\0')) {
		printf(HELP_DEFAULT);
	} else if (strncmp(str, "active", 6) == 0)
		printf(HELP_ACTIVE);
	else if (strncmp(str, "create", 6) == 0)
		printf(HELP_CREATE);
	else if (strncmp(str, "delete", 6) == 0)
		printf(HELP_DELETE);
	else if (strncmp(str, "set", 3) == 0)
		printf(HELP_SET);
	else if (strncmp(str, "unset", 5) == 0)
		printf(HELP_UNSET);
	else if (strncmp(str, "list", 4) == 0)
		printf(HELP_LIST);
	else if (strncmp(str, "print", 5) == 0)
		printf(HELP_PRINT);
	else if (strncmp(str, "import", 6) == 0)
		printf(HELP_IMPORT);
	else if (strncmp(str, "export", 6) == 0)
		printf(HELP_EXPORT);
	else if (strncmp(str, "quit", 4) == 0)
		printf(HELP_QUIT0);
	else if (strncmp(str, "exit", 4) == 0)
		printf(HELP_EXIT);
	else if (strncmp(str, "operator", 8) == 0)
		printf(HELP_OPERATOR);
	else if (strncmp(str, "value", 5) == 0)
		printf(HELP_VALUE);
	else if (strncmp(str, "name", 4) == 0)
		printf(HELP_NAME);
	else if (strncmp(str, "attribute", 9) == 0)
		printf(HELP_ATTRIBUTE);
	else if (strncmp(str, "serverpublic", 12) == 0)
		printf(HELP_SERVERPUBLIC);
	else if (strncmp(str, "serverro", 8) == 0)
		printf(HELP_SERVERRO);
	else if (strncmp(str, "queuepublic", 11) == 0)
		printf(HELP_QUEUEPUBLIC);
	else if (strncmp(str, "queueexec", 9) == 0)
		printf(HELP_QUEUEEXEC);
	else if (strncmp(str, "queueroute", 10) == 0)
		printf(HELP_QUEUEROUTE);
	else if (strncmp(str, "queuero", 7) == 0)
		printf(HELP_QUEUERO);
	else if (strncmp(str, "nodeattr", 8) == 0)
		printf(HELP_NODEATTR);
	else
		printf("No help available on: %s\nCheck the PBS Reference Guide for more help.\n", str);

	printf("\n");
}

/**
 * @brief
 *	parse - parse the qmgr request
 *
 * @param[in]  request      The text of a single qmgr command.
 * @param[out] oper    Indicates either create, delete, set, unset, or list
 * @param[out] type    Indicates either server or queue.
 * @param[out] names   The names of the objects.
 * @param[out] attr    The attribute list with operators.
 *
 * @return Error code
 * @retval       0  Success
 * @retval       !0 Failure
 *
 * Note:
 *  The syntax of a qmgr directive is:
 *
 *      operation type [namelist] [attributelist]
 *
 *  where
 *      operation       create, delete, set, unset, list or print
 *      type            server, queue, node, or resource
 *      namelist        comma delimit list of names with no white space,
 *                      can only be defaulted if the type is server
 *      attributelist   comma delimit list of name or name-value pairs
 *
 *  If the operation part is quit or exit, then the code will be stopped
 *  now.
 *
 */
int
parse(char *request, int *oper, int *type, char **names, struct attropl **attr)
{
	int error;
	int lp;	 /* Length of current string */
	int len; /* ammount parsed by parse_request */
	char **req = NULL;
	int names_len = 0;
	char *p;

	/* jump over whitespace atleast in the LHS */
	p = request;
	while (White(*p))
		p++;
	if (*p == '\0')
		return -1;
	request = p;

	/* request was all right, if history enabled, add to history */
#ifdef QMGR_HAVE_HIST
	if (qmgr_hist_enabled == 1)
		qmgr_add_history(p);
#endif

	/* parse the request into parts */
	len = parse_request(request, &req);

	if (len != 0) { /* error in parse_request */
		lp = strlen(req[IND_CMD]);

		if (strncmp(req[0], "create", lp) == 0)
			*oper = MGR_CMD_CREATE;
		else if (strncmp(req[0], "delete", lp) == 0)
			*oper = MGR_CMD_DELETE;
		else if (strncmp(req[0], "set", lp) == 0)
			*oper = MGR_CMD_SET;
		else if (strncmp(req[0], "unset", lp) == 0)
			*oper = MGR_CMD_UNSET;
		else if (strncmp(req[0], "list", lp) == 0)
			*oper = MGR_CMD_LIST;
		else if (strncmp(req[0], "print", lp) == 0)
			*oper = MGR_CMD_PRINT;
		else if (strncmp(req[0], "active", lp) == 0)
			*oper = MGR_CMD_ACTIVE;
		else if (strncmp(req[0], "import", lp) == 0)
			*oper = MGR_CMD_IMPORT;
		else if (strncmp(req[0], "export", lp) == 0)
			*oper = MGR_CMD_EXPORT;
		else if (strncmp(req[0], "help", lp) == 0) {
			show_help(req[1]);
			CLEAN_UP_REQ(req)
			return -1;
		} else if (strncmp(req[0], "?", lp) == 0) {
			show_help(req[1]);
			CLEAN_UP_REQ(req)
			return -1;
		} else if (strncmp(req[0], "quit", lp) == 0) {
			CLEAN_UP_REQ(req)
			clean_up_and_exit(0);
		} else if (strncmp(req[0], "exit", lp) == 0) {
			CLEAN_UP_REQ(req)
			clean_up_and_exit(0);
		}
#ifdef QMGR_HAVE_HIST
		else if (strncmp(req[0], "history", lp) == 0) {
			qmgr_list_history(req[1] ? atol(req[1]) : QMGR_HIST_SIZE);
			free(request);
			return -1;
		}
#endif
		else {
			PSTDERR1("qmgr: Illegal operation: %s\n"
				 "Try 'help' if you are having trouble.\n",
				 req[IND_CMD])
			CLEAN_UP_REQ(req)
			return 1;
		}

		if (EOL(req[IND_OBJ])) {
			pstderr("qmgr: No object type given\n");
			CLEAN_UP_REQ(req)
			return 2;
		}

		lp = strlen(req[IND_OBJ]);
		if (strncmp(req[1], "server", lp) == 0)
			*type = MGR_OBJ_SERVER;
		else if ((strncmp(req[1], "queue", lp) == 0) ||
			 (strncmp(req[1], "queues", lp) == 0))
			*type = MGR_OBJ_QUEUE;
		else if ((strncmp(req[1], "node", lp) == 0) ||
			 (strncmp(req[1], "nodes", lp) == 0))
			*type = MGR_OBJ_NODE;
		else if (strncmp(req[1], "resource", lp) == 0)
			*type = MGR_OBJ_RSC;
		else if (strncmp(req[1], "sched", lp) == 0)
			*type = MGR_OBJ_SCHED;
		else if (strncmp(req[1], SITE_HOOK, lp) == 0)
			*type = MGR_OBJ_SITE_HOOK;
		else if (strncmp(req[1], PBS_HOOK, lp) == 0)
			*type = MGR_OBJ_PBS_HOOK;
		else {
			PSTDERR1("qmgr: Illegal object type: %s.\n", req[IND_OBJ])
			CLEAN_UP_REQ(req)
			return 2;
		}

		if (!EOL(req[IND_NAME])) {
			if ((*type != MGR_OBJ_SITE_HOOK) && (*type != MGR_OBJ_PBS_HOOK) && (*type != MGR_OBJ_RSC) &&
			    is_attr(*type, req[IND_NAME], TYPE_ATTR_ALL)) {
				len -= strlen(req[IND_NAME]);
				req[IND_NAME][0] = '\0';
			} else if ((error = check_list(req[IND_NAME], *type))) {
				pstderr(syntaxerr);
				CaretErr(request, len - (int) strlen(req[IND_NAME]) + error - 1);
				CLEAN_UP_REQ(req)
				return 3;
			} else {
				names_len = strlen(req[IND_NAME]);
				*names = (char *) malloc(names_len + 1);
				if (*names == NULL) {
					fprintf(stderr, "malloc failure (errno %d)\n", errno);
					exit(1);
				}
				pbs_strncpy(*names, req[IND_NAME], names_len + 1);
			}
		}

		/* Get attribute list; remaining part of the request */
		if ((*oper != MGR_CMD_IMPORT) && (*oper != MGR_CMD_EXPORT) &&
		    ((error = attributes(request + len, attr, *oper)) != 0)) {
			pstderr(syntaxerr);
			CaretErr(request, len + error);
			CLEAN_UP_REQ(req)
			return 4;
		} else if ((*oper == MGR_CMD_IMPORT) &&
			   ((error = params_import(request + len, attr, *oper)) != 0)) {
			pstderr(syntaxerr);
			CaretErr(request, len + error);
			CLEAN_UP_REQ(req)
			return 4;
		} else if ((*oper == MGR_CMD_EXPORT) &&
			   ((error = params_export(request + len, attr, *oper)) != 0)) {
			pstderr(syntaxerr);
			CaretErr(request, len + error);
			CLEAN_UP_REQ(req)
			return 4;
		} else if ((*oper == MGR_CMD_SET || *oper == MGR_CMD_UNSET) && *attr == NULL) {
			pstderr(syntaxerr);
			CaretErr(request, len + error);
			CLEAN_UP_REQ(req)
			return 4;
		} else if (*oper == MGR_CMD_ACTIVE && *attr != NULL) {
			pstderr(syntaxerr);
			CaretErr(request, len);
			CLEAN_UP_REQ(req)
			return 4;
		}
	} else {
		pstderr(syntaxerr);
		CaretErr(request, len);
		CLEAN_UP_REQ(req)
		return 4;
	}
	CLEAN_UP_REQ(req)
	return 0;
}

/**
 * @brief
 *	pstderr - prints error message to standard error.  It will not be
 *		  printed if the "-z" option was given on the command line
 *
 * @param[in] string       The error message to print.
 *
 * @return Void
 * 	Global Variable: zopt
 *
 */
void
pstderr(const char *string)
{
	if (!zopt)
		fprintf(stderr, "%s", string);
}

/**
 * @brief
 *	pstderr_big - prints error message to standard error.  It handles
 *                    the highly unusual case where the error message
 *                    that's to be generated is too big to be placed in
 *                    the buffer that was allocated.  In this case the
 *                    message is put out in pieces to stderr.  Kind of
 *                    ugly, but one doesn't really expect this code to be
 *                    called except in the oddest of cases.
 *
 * @param[in]   svrname       name of the server
 * @param[in]	objname       name of the object
 * @param[in]	errmesg       actual error message
 *
 * @return Void
 * 	Global Variable: zopt
 *
 */
void
pstderr_big(char *svrname, char *objname, char *errmesg)
{
	pstderr("qmgr obj=");
	pstderr(objname);
	pstderr(" svr=");
	pstderr(svrname);
	pstderr(": ");
	pstderr(errmesg);
	pstderr("\n");
}

/**
 * @brief
 *	free_objname_list - frees an objname list
 *
 *@param[in]  list - objname list to free
 *
 * @return Void
 *
 */
void
free_objname_list(struct objname *list)
{
	struct objname *cur, *tmp;

	cur = list;

	while (cur != NULL) {
		tmp = cur->next;
		free_objname(cur);
		cur = tmp;
	}
}

/**
 * @brief
 *	find_server - find a server in the server list
 *
 * @param[in] name - the name of the server
 *
 * @return pointer to structure
 * @retval return a pointer to the specified server struct or NULL if not found
 *
 */
struct server *
find_server(char *name)
{
	struct server *s = NULL;

	if (name != NULL) {
		s = servers;

		while (s != NULL && strcmp(s->s_name, name))
			s = s->next;
	}

	return s;
}

/**
 * @brief
 *	new_server - allocate new server objcet and initialize it
 *
 * @return structure
 * @retval new server object
 *
 */
struct server *
new_server()
{
	struct server *new;

	Mstruct(new, struct server);
	new->s_connect = -1;
	new->s_name = NULL;
	new->ref = 0;
	new->s_rsc = NULL;
	new->next = NULL;
	return new;
}

/**
 * @brief
 *	free_server - remove server from servers list and free it up
 *
 * @param[in] svr - the server to free
 *
 * @return Void
 *
 */
void
free_server(struct server *svr)
{
	struct server *cur_svr, *prev_svr = NULL;

	/* remove server from servers list */
	cur_svr = servers;
	while (cur_svr != svr && cur_svr != NULL) {
		prev_svr = cur_svr;
		cur_svr = cur_svr->next;
	}

	if (cur_svr != NULL) {
		if (prev_svr == NULL)
			servers = servers->next;
		else
			prev_svr->next = cur_svr->next;

		if (svr->s_name != NULL)
			free(svr->s_name);

		if (svr->s_rsc != NULL)
			pbs_statfree(svr->s_rsc);

		svr->s_name = NULL;
		svr->s_connect = -1;
		svr->next = NULL;
		free(svr);
	}
}

/**
 * @brief
 *	new_objname - allocate new object and initialize it
 *
 * @return structure
 * @retval newly allocated object
 *
 */
struct objname *
new_objname()
{
	struct objname *new;
	Mstruct(new, struct objname);
	new->obj_type = MGR_OBJ_NONE;
	new->obj_name = NULL;
	new->svr_name = NULL;
	new->svr = NULL;
	new->next = NULL;

	return new;
}

/**
 * @brief
 *	free_objname - frees space used by an objname
 *
 * @param[in] obj - objname to free
 *
 * @return Void
 *
 */
void
free_objname(struct objname *obj)
{
	if (obj->obj_name != NULL)
		free(obj->obj_name);

	if (obj->obj_type != MGR_OBJ_SERVER && obj->svr_name != NULL &&
	    obj->obj_name != obj->svr_name)
		free(obj->svr_name);

	if (obj->svr != NULL)
		obj->svr->ref--;

	obj->svr = NULL;
	obj->obj_name = NULL;
	obj->svr_name = NULL;
	obj->next = NULL;
	free(obj);
}

/**
 * @brief
 *	strings2objname - convert an array of strings to a list of objnames
 *
 * @param[in]  str - array of strings
 * @param[in]  num - number of strings
 * @param[in]  type - type of objects
 *
 * @return structure
 * @retval newly allocated list of objnames
 *
 */
struct objname *
strings2objname(char **str, int num, int type)
{
	struct objname *objs = NULL;	 /* head of objname list */
	struct objname *cur_obj;	 /* current object in objname list */
	struct objname *prev_obj = NULL; /* previous object in objname list */
	int i;
	int len;

	if (str != NULL) {
		for (i = 0; i < num; i++) {
			cur_obj = new_objname();

			len = strlen(str[i]);
			Mstring(cur_obj->obj_name, len + 1);
			strcpy(cur_obj->obj_name, str[i]);
			cur_obj->obj_type = type;
			if (type == MGR_OBJ_SERVER || type == MGR_OBJ_SCHED || type == MGR_OBJ_SITE_HOOK || type == MGR_OBJ_PBS_HOOK)
				cur_obj->svr_name = cur_obj->obj_name;

			if (prev_obj != NULL)
				prev_obj->next = cur_obj;

			if (objs == NULL)
				objs = cur_obj;

			prev_obj = cur_obj;
		}
	}
	return objs;
}

/**
 * @brief
 *	is_valid_object - connects to the server to check if the object exists
 *			  on the server its connected.
 *
 * @param[in] obj - object to check
 * @param[in] type - type of object
 *
 * @returns Error code
 * @retval  1  Success  valid
 * @retval  0  Failure  not valid
 *
 */
int
is_valid_object(struct objname *obj, int type)
{
	struct batch_status *batch_obj = NULL;
	/* we need something to make the pbs_stat* call.
	 * Even if we only want the object name
	 */
	static struct attrl attrq = {NULL, ATTR_qtype, "", ""};
	static struct attrl attrn = {NULL, ATTR_NODE_state, "", ""};
	int valid = 1;
	char *errmsg;

	if (obj != NULL && obj->svr != NULL) {
		switch (type) {
			case MGR_OBJ_QUEUE:
				batch_obj = pbs_statque(obj->svr->s_connect, obj->obj_name, &attrq, NULL);
				break;

			case MGR_OBJ_NODE:
				batch_obj = pbs_statvnode(obj->svr->s_connect, obj->obj_name, &attrn, NULL);
				break;

			default:
				valid = 0;
		}

		if (batch_obj == NULL) {
			errmsg = pbs_geterrmsg(obj->svr->s_connect);
			PSTDERR1("qmgr: %s.\n", errmsg)
			valid = 0;
		} else {
			/* if pbs_stat*() returned something, then the object exists */
			valid = 1;
			pbs_statfree(batch_obj);
		}
	} else
		valid = 1; /* NULL server means all active servers */

	return valid;
}

/**
 * @brief
 *	default_server_name - create an objname struct for the default server
 *
 * @return   structure
 * @retval   newly allocated objname with the default server assigned
 *
 */
struct objname *
default_server_name()
{
	struct objname *obj;

	obj = new_objname();
	/* default server name is the NULL string */
	Mstring(obj->obj_name, 1);
	obj->obj_name[0] = '\0';
	obj->svr_name = obj->obj_name;
	obj->obj_type = MGR_OBJ_SERVER;

	return obj;
}

/**
 * @brief
 *	temp_objname - set up a temporary objname struct.  This is meant for
 *		       a one time use.  The memory is static.
 *
 * @param[in]  obj_name - name for temp struct
 * @param[in]  svr_name - name of the server for the temp struct
 * @param[in]  svr  - server for temp struct
 *
 * @returns structure
 * @retval  temporary objname
 *
 */
struct objname *
temp_objname(char *obj_name, char *svr_name, struct server *svr)
{
	static struct objname temp = {0, NULL, NULL, NULL, NULL};

	if (temp.svr != NULL)
		temp.svr->ref--;

	temp.obj_name = NULL;
	temp.svr_name = NULL;
	temp.svr = NULL;

	temp.obj_name = obj_name;
	temp.svr_name = svr_name;
	temp.svr = svr;

	if (temp.svr != NULL)
		temp.svr->ref++;

	return &temp;
}

/**
 * @brief
 *	close_non_ref_servers - close all nonreferenced servers
 *
 * @returns Void
 *
 */
void
close_non_ref_servers()
{
	struct server *svr, *tmp_svr;

	svr = servers;

	while (svr != NULL) {
		tmp_svr = svr->next;

		if (svr->ref == 0)
			disconnect_from_server(svr);

		svr = tmp_svr;
	}
}

/**
 * @brief
 *	parse_request - parse out the command, object, and possible name
 *
 * @remarks
 *	FULL: command object name ...
 *	      command object ...
 *	NOTE: there does not need to be whitespace around the operator
 *
 * @param[in]  request - the request to be processed
 * @param[out] req - array to return data in
 *	       indicies:
 *	       IND_CMD   : command
 *	       IND_OBJ   : object
 *	       IND_NAME  : name
 *
 * if any field is not there, it is left blank.
 * returns The number of characters parsed.  Note: 0 chars parsed is error
 *		Data is passed back via the req variable.
 * @return int
 * @retval 0  Failure
 * @retval The number of characters parsed  Success
 *
 */
int
parse_request(char *request, char ***req)
{
	char *foreptr, *backptr;
	int len;
	int i = 0;
	int chars_parsed = 0;
	int error = 0;

	foreptr = request;
	*req = (char **) malloc(MAX_REQ_WORDS * sizeof(char *));
	if (*req == NULL) {
		fprintf(stderr, "malloc failure (errno %d)\n", errno);
		exit(1);
	}
	for (i = IND_FIRST; i <= IND_LAST; i++)
		(*req)[i] = NULL;

	for (i = 0; !EOL(*foreptr) && i < MAX_REQ_WORDS && error == 0;) {
		while (White(*foreptr))
			foreptr++;

		backptr = foreptr;
		while (!White(*foreptr) && !Oper(foreptr) && !EOL(*foreptr))
			foreptr++;

		len = foreptr - backptr;

		if (len > strlen(request)) {
			error = 1;
			chars_parsed = (int) (foreptr - request);
			pstderr("qmgr: max word length exceeded\n");
			CaretErr(request, chars_parsed);
		}
		(*req)[i] = (char *) malloc(len + 1);
		if ((*req)[i] == NULL) {
			fprintf(stderr, "malloc failure (errno %d)\n", errno);
			exit(1);
		}
		((*req)[i])[len] = '\0';
		if (len > 0)
			pbs_strncpy((*req)[i], backptr, len + 1);
		i++;
	}
	chars_parsed = foreptr - request;

	return error ? 0 : chars_parsed;
}
