/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */
#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include "pbs_ifl.h"
#include <windows.h>
#include "log.h"
#include "win.h"
/**
 * @file	getopt.c
 */
char	*optarg;
int 	optind = 1;
int	opterr = 1;
int	optopt = 0;

int
getopt(int argc,
	char **argv,
	const char *__shortopts)/* valid option list */
{
	static	int	nextchar = 1;
	char		*nextopt;
	int		curr_opt;
	int		i, j, n;

	if (optind == 0) {	/* means to rewind! */
		optind = 1;
		nextchar = 1;
	}

	for (i=nextchar; i < argc; i++) {
		if( (strcmp(argv[i], "-") != 0) && \
		    	(strcmp(argv[i], "--") != 0) && \
					argv[i][0] == '-' ) {

			/* match an option in valid option list */
			if ((nextopt=strchr(__shortopts, argv[i][1])) != NULL) { /* a valid option */
				curr_opt = *nextopt;
				if (*(nextopt+1) == ':') { /* option requires  arg */
					optarg = &(argv[i][2]);
					if (strlen(optarg) == 0) {
						optarg = argv[++i];
						if (optarg == NULL) {
							if (opterr) {
								fprintf(stderr,
									"Option requires an argument -- %c\n",
									curr_opt);
								optopt = curr_opt;
							}
							optind = i;
							nextchar = optind;
							return ':';
						}
					}
					optind = i+1;
					nextchar = optind;
				} else {	/* option requires no argument */
					n = strlen(argv[i]);
					if (n == 2) {
						optind = i+1;
						nextchar = optind;
					} else { /* we have a combined option as in -Bf */
						for (j=1; j < n; j++)
							argv[i][j] = argv[i][j+1];
						argv[i][j] = '\0';
					}
				}
				return (curr_opt);
			} else {
				if (opterr) {
					fprintf(stderr, "Unknown option %c!\n",
						argv[i][1]);
					optopt = argv[i][1];
				}
				optind = ++i;
				nextchar = optind;
				return '?';
			}

		} else { /* no more option characters */
			char *s = argv[i];
			if (((s != NULL) && (s[0] == '-') && (s[1] == '-') &&
				(s[2] == '\0'))) {
				/*
				 * In non-MS platforms, if getopt finds '--',
				 * then it increments optind. So increment
				 * optind, if it finds '--' command-line option.
				 */
				optind = i + 1;
			} else
				optind = i;

			nextchar = optind;
			return (-1);
		}
	}

	/* rewind */
	return (-1);
}

/**
 * @brief
 * 	Given a string, converts instances of '\' to '/'.
 *
 * @param[in] str - input string
 *
 */
void
back2forward_slash(char *str)
{
	if (str == NULL)
		return;

	while (*str != '\0') {
		if (*str == '\\') {
			if (*(str+1) == '\0' || *(str+1) != ',')
				*str = '/';
		}
		str++;
	}
}

/**
 * @brief
 * 	Like back2forward_slash except "\ " or "\," (escapes a space or comma) is left alone.
 *
 * @param[in] str - input string
 */
void
back2forward_slash2(char *str)
{
	char *pc;

	if (str == NULL)
		return;

	for (pc = str; *pc != '\0'; pc++) {
		if (*pc == '\\' && (*(pc+1) != '\0' && *(pc+1) != '\\' &&
			*(pc+1) != ',') && ((pc == str) || (*(pc-1) != '\\')))
			*pc = '/';
	}
}

/**
 * @brief
 *	Given a string, converts instances of '/' to '\'.
 *
 * @param[in] str - input string
 */
void
forward2back_slash(char *str)
{
	if (str == NULL)
		return;

	while (*str != '\0') {
		if (*str == '/')
			*str = '\\';
		str++;
	}
}

/**
 * @brief
 *	Given a path string, returns the best possible equivalent short pathname
 *	(8.3 aliasing. The returned value is a ptr to a static area
 *
 * @param[in] str - input string
 */

char *
lpath2short(char *str)
{
	static char	spath[MAXPATHLEN+1];
	char		sdpath[MAXPATHLEN+1];
	char		sfpath[MAXPATHLEN+1];
	char		dirs[MAXPATHLEN+1];
	char		fn[MAXPATHLEN+1];
	char		*p;

	if (GetShortPathName(str, spath, MAXPATHLEN+1) != 0) { /* error */
		return (spath);
	}

	if (p=strrchr(str, '/')) {
		*p = '\0';
		strcpy(dirs, str);
		strcat(dirs, "/");
		*p = '/';
		strcpy(fn, p+1);
	} else if (p=strrchr(str, '\\')) {
		*p = '\0';
		strcpy(dirs, str);
		strcat(dirs, "\\");
		*p = '\\';
		strcpy(fn, p+1);
	} else {
		dirs[0] = '\0';
		strcpy(fn, str);
	}


	if (GetShortPathName(dirs, sdpath, MAXPATHLEN+1) == 0) { /* error */
		strcpy(sdpath, dirs);
	}

	if (GetShortPathName(fn, sfpath, MAXPATHLEN+1) == 0) { /* error */
		strcpy(sfpath, fn);
	}

	sprintf(spath, "%s%s", sdpath, sfpath);
	return (spath);
}

/**
 * @brief
 *	Like lpath2short() except the passed string itself is modified to reflect
 *	the short name.
 *
 * @param[in] str - input string
 */
void
lpath2short_B(char *str)
{
	char	path[MAXPATHLEN+1];

	strcpy(path, lpath2short(str));
	strcpy(str, path);
}

/**
 * @brief
 *	Given a string str, converts instances of ' ' (space) with the repl string.
 *	Also, if the first character in repl string appears in str, then that is
 *	replaced with '%<hex_num>' where <hex_num> is the ascii hex represetation of
 *	that character.
 *
 *	This returns a statically allocated area.
 *	For example, the function call
 *	"replace_space("ap%ple banana", "%20")
 *	results in ap%25ple%20banana
 *	for %25 = %, and %20 = <space>.
 *
 *	Special Case: if rep string is given as "", then the returned string will
 *	be quoted if a space character is found.
 */
char *
replace_space(char *str, char *repl)
{
	static char rstr[512];
	static char rstr2[512];
	int	i, j;
	int	repl_len;
	char	spec_chars[4];
	char	spec_len;
	int	has_space = 0;

	if (str == NULL || repl == NULL)
		return NULL;

	repl_len = strlen(repl);

	sprintf(spec_chars, "%%%02d", toascii(repl[0]));
	spec_len = strlen(spec_chars);

	i = 0;
	while (*str != '\0') {
		if (*str == repl[0]) {
			for (j=0; j< spec_len; j++, i++) {
				rstr[i] = spec_chars[j];
			}
		} else if (*str == ' ' && repl_len > 0) {
			for (j=0; j< repl_len; j++, i++) {
				rstr[i] = repl[j];
			}
		} else {
			rstr[i] = *str;
			i++;
		}
		if (*str == ' ')
			has_space = 1;

		str++;
	}
	rstr[i] = '\0';

	if (repl_len == 0 && has_space) {
		sprintf(rstr2, "\"%s\"", rstr);
		return (rstr2);
	}

	return (rstr);
}

/**
 * @brief
 *	shorten_and_cleanup_path: Takes a filename path, removes any trailing
 *	unprintable character on the name, and then returns the windows shortname
 *	equivalent.
 *
 * @param[in] - path - filename path
 *
 * @return	string
 * @retval	malloc-ed string	success
 * @retval	NULL			error
 *
 */
char *
shorten_and_cleanup_path(char *path)
{
	char *conf_filename2;
	char *conf_filename;
	int  i;

	conf_filename2 = (char *)malloc(strlen(path)+1);
	if (conf_filename2 == NULL)
		return NULL;

	strcpy(conf_filename2, path);
	i = strlen(conf_filename2);

	while (i > 0 && !isgraph(conf_filename2[i-1])) {
		conf_filename2[i-1] = '\0';
		i--;
	}

	if ((conf_filename = strdup(lpath2short(conf_filename2))) == NULL) {
		(void)free(conf_filename2);
		return NULL;
	}
	back2forward_slash(conf_filename);

	(void)free(conf_filename2);
	return (conf_filename);
}
