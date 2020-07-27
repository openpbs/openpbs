
#include <pbs_config.h>

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pwd.h>

#include "pbs_ifl.h"
#include "cmds.h"
#include "qmgr.h"

#include "histedit.h"

#ifdef QMGR_HAVE_HIST

EditLine *el;
HistEvent ev;
History *qmgrhist;

extern char prompt[];
extern char contin[];
extern char *cur_prompt ;
extern const char hist_init_err[];
extern const char histfile_access_err[];
extern int qmgr_hist_enabled; /* history is enabled by default */
extern char qmgr_hist_file[MAXPATHLEN + 1];  /* history file for this user */


/**
 * @brief
 *	To print out the prompt you need to use a function.  This could be
 *	made to do something special, but I opt to just have a static prompt.
 *
 * @param[in] e - prompt printing function
 *
 * @return string
 * @retval string containing prompt
 *
 */
static char *
el_prompt(EditLine *e)
{
	return cur_prompt;
}

/**
 * @brief
 *	To handle SIGQUIT signal when Ctrl-D is pressed.
 *
 * @param[in] Editline pointer
 * @param[in] int - key which caused the invocation
 *
 * @return EOF
 *
 * @par Side Effects: None
 *
 */
static unsigned char
EOF_handler(EditLine *e, int ch)
{
	return CC_EOF;
}

/**
 * @brief
 *	List the commands stored in qmgr history
 *
 * @param[in] len - Length of history from recent to list
 *
 * @par Side Effects: None
 *
 */
void
qmgr_list_history(int len)
{
	int i = 0;
	int tot;

	if (len <= 0){
	  if (len!=0)
	    printf("Invalid option\n");
	  return;
        }

	if (history(qmgrhist, &ev, H_GETSIZE) == -1)
		return;
	tot = ev.num;

	if (history(qmgrhist, &ev, H_LAST) == -1)
		return;

	while (1) {
		i++;
		if ((ev.str != NULL) && ((i + len) > tot))
			printf("%d\t%s\n", ev.num, ev.str);

		if (history(qmgrhist, &ev, H_PREV) == -1)
			return;
	}
}

/**
 * @brief
 *	Get the num-th event from the history
 *
 * @param[in] num - the num-th element to get
 * @param[out] request - return history in newly allocated address
 *
 * @par Side Effects: None
 *
 * @return      Error code
 * @retval  0 - success
 * @retval -1 - Failure
 */
static int
qmgr_get_history(int num, char **request)
{
	if (history(qmgrhist, &ev, H_LAST) == -1)
		return -1;

	while (1) {
		if (ev.num == num) {
			if (ev.str == NULL || (*request = strdup(ev.str)) == NULL)
				return -1;
			return 0;
		}
		if (history(qmgrhist, &ev, H_PREV) == -1)
			return -1;
	}
	return -1;
}

/**
 * @brief
 *	Initialize the qmgr history capability
 *
 * @param[in]	prog - Name of the program (qmgr) so that
 * editline can use editrc for any custom settings.
 *
 * @return      Error code
 * @retval  0 - Success
 * @retval -1 - Failure
 *
 * @par Side Effects: None
 *
 */
int
init_qmgr_hist(char *prog)
{
	struct passwd *pw;
	int rc;

	el = el_init(prog, stdin, stdout, stderr);
	el_set(el, EL_PROMPT, &el_prompt);
	el_set(el, EL_EDITOR, "emacs");
	el_set(el, EL_ADDFN, "EOF_handler", "EOF_handler", &EOF_handler);
	el_set(el, EL_BIND, "^D", "EOF_handler", NULL);

	/* Initialize the history */
	qmgrhist = history_init();
	if (qmgrhist == NULL) {
		fprintf(stderr, "%s", hist_init_err);
		return -1;
	}

	/* Set the size of the history */
	if (history(qmgrhist, &ev, H_SETSIZE, QMGR_HIST_SIZE) == -1) {
		fprintf(stderr, "%s", hist_init_err);
		return -1;
	}

	/* set adjacent unique */
	if (history(qmgrhist, &ev, H_SETUNIQUE, 1) == -1) {
		fprintf(stderr, "%s", hist_init_err);
		return -1;
	}

	/* This sets up the call back functions for history functionality */
	el_set(el, EL_HIST, history, qmgrhist);

	qmgr_hist_file[0] = '\0';
	rc = 1;
	if ((pw = getpwuid(getuid()))) {
		snprintf(qmgr_hist_file, MAXPATHLEN, "%s/.pbs_qmgr_history", pw->pw_dir);
		history(qmgrhist, &ev, H_LOAD, qmgr_hist_file);
		if (history(qmgrhist, &ev, H_SAVE, qmgr_hist_file) == -1)
			history(qmgrhist, &ev, H_CLEAR);
		else
			rc = 0;

		if (rc == 1) {
			snprintf(qmgr_hist_file, MAXPATHLEN, "%s/spool/.pbs_qmgr_history_%s",
				pbs_conf.pbs_home_path, pw->pw_name);
			history(qmgrhist, &ev, H_LOAD, qmgr_hist_file);
			if (history(qmgrhist, &ev, H_SAVE, qmgr_hist_file) == -1)
				history(qmgrhist, &ev, H_CLEAR);
			else
				rc = 0;
		}
	}

	if (rc == 1) {
		fprintf(stderr, histfile_access_err, qmgr_hist_file);
		qmgr_hist_file[0] = '\0';
	}

	return 0;
}

/**
 * @brief
 * Add a line to history
 *
 * @param[in] req - line to be added to history
 *
 * @return - Error code
 * @retval -1 Failure
 * @retval  0 Success
 */
int
qmgr_add_history(char *req)
{
	if (history(qmgrhist, &ev, H_ENTER, req) == -1) {
		fprintf(stderr, "Failed to set history\n");
		return -1;
	} else if (qmgr_hist_file[0] != '\0') {
		if (history(qmgrhist, &ev, H_SAVE, qmgr_hist_file) == -1) {
			fprintf(stderr, "Failed to save history\n");
			return -1;
		}
	}
	return 0;
}

/**
 * @brief
 *	Get a request from the command prompt with the support for history
 *
 * @par Functionality:
 *	Gets a line of input from the user. The user can use up and down arrows
 *	(emacs style) to recall history.
 *
 * @param[out]	request - The buffer to which user-input is returned into
 *
 * @return	   int
 * @retval 0 - Success
 * @retval 1 - Failure
 *
 * @par Side Effects: None
 *
 */

int
get_request_hist(char **request)
{
	int count;
	char *line;
	char *p;
	char *req;
	int req_size;
	int cont_char;

	*request = NULL;
	req = NULL;

	/* loop till we get some data */
	while (1) {
		cur_prompt = prompt;
		cont_char = 1;

		while (cont_char) {
			/* count is the number of characters read.
			 line is a const char* of our command line with the tailing \n */
			if ((line = (char *) el_gets(el, &count)) == NULL) {
				return EOF;
			}

			count--; /* don't count the last \n */
			if (count <= 0) {
				cont_char = 0;
				continue;
			}

			line[count] = '\0'; /* remove the trailing \n */

			p = line;
			/* gloss over initial white space */
			while (White(*p))
				p++;

			if (*p == '#')
				continue; /* ignore comments */

			count = strlen(p);
			if (count <= 0) {
				cont_char = 0;
				continue;
			}

			if (p[count - 1] == '\\') {
				p[count - 1] = ' ';
			} else
				cont_char = 0;

			if (*request == NULL) {
				*request = strdup(p);
				if (*request == NULL)
					return 1;
			} else {
				req_size = strlen(*request) + count + 1;
				*request = realloc(*request, req_size);
				if (*request == NULL)
					return 1;
				strcat(*request, p);
			}
			cur_prompt = contin;
		}

		if (*request == NULL)
			continue; /* we did not get a good input, continue */

		req = *request;

		/* immediately check if this was a recall of a command from history */
		if (req[0] == '!') {
			p = &req[1];
			if (qmgr_get_history(atol(p), request) != 0) {
				fprintf(stderr, "No item %s in history\n", p);
				free(req);
				*request = NULL;
				req = NULL;
				continue;
			}
			free(req); /* free the old one */
		}
		return 0;
	}
	return 1;
}

#endif