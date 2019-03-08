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

/**
 * @file	misc_utils.c
 * @brief
 *  Utility functions to condense and unroll a sequence of execvnodes that are
 *  returned by the scheduler for standing reservations.
 *  The objective is to condense in a human-readable format the execvnodes
 *  of each occurrence of a standing reservation, and be able to retrieve each
 *  such occurrence easily.
 *
 *  Example usage (also refer to the debug function int test_execvnode_seq
 *  for a code snippet):
 *
 *  Assume str points to some string.
 *  char *condensed_str;
 *  char **unrolled_str;
 *  char **tofree;
 *
 *  condensed_str = condense_execvnode_seq(str);
 *  unrolled_str = unroll_execvnode_seq(condensed_str, &tofree);
 *  ...access an arbitrary, say 2nd occurrence, index via unrolled_str[2]
 *  free_execvnode_seq(tofree);
 */

#include <pbs_config.h>   /* the master config generated by configure */

#include <math.h>
#include <libutil.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <libpbs.h>
#include <limits.h>
#include <pbs_ifl.h>
#include <pbs_internal.h>
#include <pbs_sched.h>
#include <pbs_share.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <pwd.h>
#ifndef WIN32
#include <dlfcn.h>
#include <grp.h>
#endif
#include "pbs_error.h"

#ifdef HAVE_MALLOC_INFO
#include <malloc.h>
#endif

#define ISESCAPED(ch) (ch == '\'' || ch == '\"' || ch == ',')

/** @brief conversion array for vnode sharing attribute between str and enum */
struct {
	char *vn_str;
	enum vnode_sharing vns;
} str2vns[] = {
	{ND_Default_Shared,   VNS_DFLT_SHARED   },
	{ND_Ignore_Excl,      VNS_IGNORE_EXCL   },
	{ND_Ignore_Excl,      VNS_FORCE_SHARED  },
	{ND_Default_Excl,     VNS_DFLT_EXCL     },
	{ND_Force_Excl,       VNS_FORCE_EXCL    },
	{ND_Default_Exclhost, VNS_DFLT_EXCLHOST },
	{ND_Force_Exclhost,   VNS_FORCE_EXCLHOST}
};

/**
 * @brief
 * 	char_in_set - is the char c in the tokenset
 *
 * @param[in] c - the char
 * @param[in] tokset - string tokenset
 *
 * @return	int
 * @retval	1 	if c is in tokset
 * @retval	0 	if c is not in tokset
 */
int
char_in_set(char c, const char *tokset)
{

	int i;

	for (i = 0; tokset[i] != '\0'; i++)
		if (c == tokset[i])
			return 1;

	return 0;
}

/**
 * @brief
 * 	string_token - strtok() without an an internal state pointer
 *
 * @param[in]      str - the string to tokenize
 * @param[in] 	   tokset - the tokenset to look for
 * @param[in/out]  ret_str - the char ptr where we left off after the tokens
 *		             ** ret_str is opaque to the caller
 *
 * @par	call: 
 *	string_token( string, tokenset, &tokptr)
 *	2nd call: string_token( NULL, tokenset2, &tokptr)
 *
 * @par	tokenset can differ between the two calls (as per strtok())
 *	tokptr is an opaque ptr, just keep passing &tokptr into all calls
 *	to string_token()
 *
 * @return	char pointer
 * @retval	returns ptr to front of string segment (as per strtok())
 *
 */
char *
string_token(char *str, const char *tokset, char **ret_str)
{
	char *tok;
	char *search_string;

	if (str != NULL)
		search_string = str;
	else if (ret_str != NULL && *ret_str != NULL)
		search_string = *ret_str;
	else
		return NULL;

	tok = strstr(search_string, tokset);

	if (tok != NULL) {
		while (char_in_set(*tok, tokset) && *tok != '\0') {
			*tok = '\0';
			tok++;
		}

		if (ret_str != NULL)
			*ret_str = tok;
	}
	else
		*ret_str = NULL;

	return search_string;
}


/**
 *	@brief convert vnode sharing enum into string form

 * 	@par Note:
 * 		Do not free the return value - it's a statically allocated
 *		string.
 *
 *	@param[in] vns - vnode sharing value
 *
 *	@retval string form of sharing value
 *	@retval NULL on error
 */
char *
vnode_sharing_to_str(enum vnode_sharing vns)
{
	int i;
	int size = sizeof(str2vns)/sizeof(str2vns[0]);

	for (i = 0; i < size && str2vns[i].vns != vns; i++)
		;

	if (i == size)
		return NULL;

	return str2vns[i].vn_str;
}

/**
 *	@brief convert string form of vnode sharing to enum
 *
 *	@param[in] vn_str - vnode sharing  string
 *
 *	@return	enum
 *	@retval vnode sharing value
 *	@retval VNS_UNSET if not found
 */
enum vnode_sharing str_to_vnode_sharing(char *vn_str)
{
	int i;
	int size = sizeof(str2vns)/sizeof(str2vns[0]);

	if (vn_str == NULL)
		return VNS_UNSET;

	for (i = 0; i < size && strcmp(vn_str, str2vns[i].vn_str) != 0; i++)
		;

	if (i == size)
		return VNS_UNSET;

	return str2vns[i].vns;
}

/**
 *
 * @brief concatenate two strings by expanding target string as needed.
 * 	  Operation: strbuf += str
 *
 *	@param[in, out] strbuf - string that will expand to accommodate the
 *			        concatenation of 'str'
 *	@param[in, out] ssize - allocated size of strbuf
 *	@param[in]      str   - string to concatenate to 'strbuf'
 *
 *	@return char *
 *	@retval pointer to the resulting string on success (*strbuf)
 *	@retval NULL on failure
 */
char *
pbs_strcat(char **strbuf, int *ssize, char *str)
{
	int len;
	int rbuf_len;
	char *tmp;
	char *rbuf;
	int size;

	if (strbuf == NULL || ssize == NULL)
		return NULL;

	if (str == NULL)
		return *strbuf;

	rbuf = *strbuf;
	size = *ssize;

	len = strlen(str);
	rbuf_len = rbuf == NULL ? 0 : strlen(rbuf);

	if (rbuf_len + len >= size) {
		if (len > size)
			size = len * 2;
		else
			size *= 2;

		tmp = realloc(rbuf, size + 1);
		if (tmp == NULL)
			return NULL;
		*ssize = size;
		*strbuf = tmp;
		rbuf = tmp;
		/* first allocate */
		if (rbuf_len == 0)
			rbuf[0] = '\0';
	}

	return strcat(rbuf, str);
}

/**
 * @brief 
 *	get a line from a file of any length.  Extend string via realloc
 *	if necessary
 *
 * @param fp[in] - open file
 * @param pbuf[in,out] - pointer to buffer to fill (may change ala realloc)
 * @param pbuf_size[in,out] - size of buf (may increase ala realloc)
 *
 * @return char *
 * @retval pointer to *pbuf(the string pbuf points at) on successful read
 * @retval NULL on EOF or error
 */
#define PBS_FGETS_LINE_LEN 8192
char *
pbs_fgets(char **pbuf, int *pbuf_size, FILE *fp)
{
	char fbuf[PBS_FGETS_LINE_LEN];
	char *buf;
	char *p;

	if (fp == NULL || pbuf == NULL || pbuf_size == NULL)
		return NULL;

	if (*pbuf_size == 0) {
		if ((*pbuf = malloc(PBS_FGETS_LINE_LEN)) == NULL)
			return NULL;
		*pbuf_size = PBS_FGETS_LINE_LEN;
	}
	buf = *pbuf;

	buf[0] = '\0';
	while ((p = fgets(fbuf, PBS_FGETS_LINE_LEN, fp)) != NULL) {
		buf = pbs_strcat(pbuf, pbuf_size, fbuf);
		if (buf == NULL)
			return NULL;

		if (buf[strlen(buf) - 1] == '\n') /* we've reached the end of the line */
			break;
	}
	if (p == NULL && buf[0] == '\0')
		return NULL;

	return *pbuf;
}

/**
 * @brief get a line from a file pointed at by fp.  The line can be extended
 *	  onto the next line if it ends in a backslash (\).  If the string is
 *	  extended, the lines will be combined and the backslash will be
 *        stripped.
 *
 * @param[in] fp pointer to file to read from
 * @param[in, out] pbuf_size - pointer to size of buffer
 * @param[in, out] pbuf - pointer to buffer
 *
 * @return char *
 * @retval string read from file
 * @retval NULL - EOF or error
 * @par MT-Safe: no
 */
char *
pbs_fgets_extend(char **pbuf, int *pbuf_size, FILE *fp)
{
	static char *locbuf = NULL;
	static int locbuf_size = 0;
	char *buf;
	char *p;
	int len;

	if (pbuf == NULL || pbuf_size == NULL || fp == NULL)
		return NULL;

	if (locbuf == NULL) {
		if ((locbuf = malloc(PBS_FGETS_LINE_LEN)) == NULL)
			return NULL;
		locbuf_size = PBS_FGETS_LINE_LEN;
	}

	if (*pbuf_size == 0 || *pbuf == NULL) {
		if ((*pbuf = malloc(PBS_FGETS_LINE_LEN)) == NULL)
			return NULL;
		*pbuf_size = PBS_FGETS_LINE_LEN;
	}

	buf = *pbuf;
	locbuf[0] = '\0';
	buf[0] = '\0';

	while ((p = pbs_fgets(&locbuf, &locbuf_size, fp)) != NULL) {
		if (pbs_strcat(pbuf, pbuf_size, locbuf) == NULL)
			return NULL;

		buf = *pbuf;
		len = strlen(buf);

		/* we have two options:
		 * 1) We extend: string ends in a '\' and 0 or more whitespace
		 * 2) we do not extend: Not #1
		 * In the case of #1, we want the string to end just before the '\'
		 * In the case of #2 we want to leave the string alone.
		 */
		while (len > 0 && isspace(buf[len-1]))
			len--;

		if (len > 0) {
			if (buf[len - 1] != '\\') {
				break;
			}
			else {
				buf[len - 1] = '\0'; /* remove the backslash (\) */
			}
		}
	}

	/* if we read just EOF */
	if (p == NULL && buf[0] == '\0')
		return NULL;

	return buf;
}

/**
 * @brief
 *	Internal asprintf() implementation for use on all platforms
 *
 * @param[in, out] dest - character pointer that will point to allocated
 *			  space ** must be freed by caller **
 * @param[in] fmt - format for printed string
 * @param[in] ... - arguments to format string
 *
 * @return int
 * @retval -1 - Error
 * @retval >=0 - Length of new string, not including terminator
 */
int
pbs_asprintf(char **dest, const char *fmt, ...)
{
	va_list args;
	int len, rc = -1;
	char *buf = NULL;

	if (!dest)
		return -1;
	*dest = NULL;
	if (!fmt)
		return -1;
	va_start(args, fmt);
#ifdef WIN32
	len = _vscprintf(fmt, args);
#else
	{
		va_list dupargs;
		char c;

		va_copy(dupargs, args);
		len = vsnprintf(&c, 0, fmt, dupargs);
		va_end(dupargs);
	}
#endif
	if (len < 0)
		goto pbs_asprintf_exit;
	buf = malloc(len + 1);
	if (!buf)
		goto pbs_asprintf_exit;
	rc = vsnprintf(buf, len + 1, fmt, args);
	if (rc != len) {
		rc = -1;
		goto pbs_asprintf_exit;
	}
	*dest = buf;
pbs_asprintf_exit:
	va_end(args);
	if (rc < 0) {
		char *tmp;

		tmp = realloc(buf, 1);
		if (tmp)
			buf = tmp;
		if (buf) {
			*buf = '\0';
			*dest = buf;
		}
	}
	return rc;
}

/**

 * @brief
 *	Copies 'src' file  to 'dst' file.
 *
 * @param[in] src - file1
 * @param[in] dst - file2
 *
 * @return int
 * @retval 0	- success
 * @retval COPY_FILE_BAD_INPUT	- dst or src is NULL.
 * @retval COPY_FILE_BAD_SOURCE	- failed to open 'src' file.
 * @retval COPY_FILE_BAD_DEST - failed to open 'dst' file.
 * @retval COPY_FILE_BAD_WRITE	- incomplete write
 */
int
copy_file_internal(char *src, char *dst)
{
	FILE	*fp_orig = NULL;
	FILE	*fp_copy = NULL;
	char	in_data[BUFSIZ+1];

	if ((src == NULL) || (dst == NULL)) {
		return (COPY_FILE_BAD_INPUT);
	}

	fp_orig = fopen(src, "r");

	if (fp_orig == NULL) {
		return (COPY_FILE_BAD_SOURCE);
	}

	fp_copy = fopen(dst, "w");

	if (fp_copy == NULL) {
		fclose(fp_orig);
		return (COPY_FILE_BAD_DEST);
	}

	while (fgets(in_data, sizeof(in_data),
		fp_orig) != NULL) {
		if (fputs(in_data, fp_copy) < 0) {
			fclose(fp_orig);
			fclose(fp_copy);
			(void)unlink(dst);
			return (COPY_FILE_BAD_WRITE);
		}
	}

	fclose(fp_orig);
	if (fclose(fp_copy) != 0) {
		return (COPY_FILE_BAD_WRITE);
	}

	return (0);
}

/**
 * @brief
 * 	Puts an advisory lock of type 'op' to the file whose stream
 *	is 'fp'.
 *
 * @param[in]	fp - descriptor of file being locked.
 * @param[in]	op - type of lock: F_WRLCK, F_RDLCK, F_UNLCK
 * @param[in]	filename -  corresonding name to 'fp' for logging purposes.
 * @param[in]	lock_retry - number of attempts to retry lock if there's a
 *			     failure to lock.
 * @param[out]	err_msg - filled with the error message string if there's a
 *			  failure to lock. (can be NULL if error message need
 *			  not be saved).
 * @param[in]	err_msg_len - size of the err_msg buffer.
 *
 * @return 	int
 * @retval 	0	for success
 * @reval	1	for failure to lock
 *
 */

int
lock_file(FILE *fp, int op, char *filename, int lock_retry,
	char *err_msg, size_t err_msg_len)
{
	int		i;
#ifdef WIN32
	struct stat  	sbuf;
	long		nbytes = 0;
#else
	struct flock 	flock;
#endif

	if (fp == NULL)
		return 0; /* nothing to lock */

#ifdef WIN32

	if (stat(filename, &sbuf) == -1) {
		if (err_msg != NULL)
			snprintf(err_msg, err_msg_len,
				"can't stat file %s", filename);
		return 1;
	}
	nbytes = 1L;
	if (sbuf.st_size > 0) {
		nbytes = sbuf.st_size;
	}
	(void)fseek(fp, 0, SEEK_SET);
	for (i = 0; i < lock_retry; i++) {
		if ((_locking(fileno(fp), op, nbytes) == -1) &&
			(GetLastError() == ERROR_LOCK_VIOLATION)) {
			if (err_msg != NULL)
				snprintf(err_msg, err_msg_len,
					"Failed to lock file %s, retrying", filename);
		} else {
			return 0;	/* locked */
		}
		sleep(2);
	}
#else

	(void)lseek(fileno(fp), (off_t)0, SEEK_SET);
	flock.l_type   = op;
	flock.l_whence = SEEK_SET;
	flock.l_start  = 0;
	flock.l_len    = 0;

	for (i = 0; i < lock_retry; i++) {
		if ((fcntl(fileno(fp), F_SETLK, &flock) == -1) &&
			((errno == EACCES) || (errno == EAGAIN))) {
			if (err_msg != NULL)
				snprintf(err_msg, err_msg_len,
					"Failed to lock file %s, retrying", filename);
		} else {
			return 0 ; /* locked */
		}
		sleep(2);
	}
#endif
	if (err_msg != NULL)
		snprintf(err_msg, err_msg_len,
			"Failed to lock file %s, giving up", filename);
	return 1;
}

/**
 * @brief 
 *	calculate the number of digits to the right of the decimal point in
 *	a floating point number.  This can be used in conjunction with
 *	printf() to not print trailing zeros.
 *
 * @param[in] fl - the float point number
 * @param[in] digits - the max number of digits to check.  Can be -1 for max
 *            number of digits for 32/64 bit numbers.
 *
 * @par	Use: int x = float_digits(fl, 8);
 * 	printf("%0.*f\n", x, fl);
 *
 * @note It may be unwise to use use a large value for digits (or -1) due to
 * that the precision of a double will decrease after the first handful of
 * digits.
 *
 * @return int
 * @retval number of digits to the right of the decimal point in fl.
 *         in the range of 0..digits
 *
 * @par MT-Safe: Yes
 */

#define FLOAT_DIGITS_ERROR_FACTOR 1000.0
/* To be more generic, we should use a signed integer type.
 * This is fine for our current use and gives us 1 more digit.
 */
#define TRUNCATE(x) (((x) > (double)ULONG_MAX) ? ULONG_MAX : (unsigned long)(x))

int
float_digits(double fl, int digits)
{
	unsigned long num;
	int i;

	/* 2^64 = 18446744073709551616 (18 useful)
	 * 2^32 = 4294967296 (9 useful)
	 */
	if (digits == -1)
		digits = (sizeof(unsigned long) >= 8) ? 18 : 9;

	fl = ((fl < 0) ? -fl : fl);

	/* The main part of the algorithm: Floating point numbers are not very exact.
	 * We need to do something to determine how close we are to the right number
	 * We multiply our floating point value by an error factor.  If we see a
	 * string of 9's or 0's in a row, we stop.  For example, if the error factor
	 * is 1000, if we see 3 9's or 0's we stop.  Every time through the loop we
	 * multiply by 10 to shift over one digit and repeat.
	 */
	for (i = 0; i < digits; i++) {
		num = TRUNCATE((fl - TRUNCATE(fl)) * FLOAT_DIGITS_ERROR_FACTOR);
		if ((num < 1) || (num >= (long)(FLOAT_DIGITS_ERROR_FACTOR-1.0)))
			break;
		fl *= 10.0;
	}
	return i;
}

/**
 *
 * @brief
 *	Returns 1 for path is a full path; otherwise, 0 if
 * 	relative path.
 *
 * @param[in]	path	- the filename path being checked.
 *
 * @return int
 * @retval	1	if 'path' is a full path.
 * @retval	0	if 'path' is  relative path
 */
int
is_full_path(char *path)
{
	char *cp = path;

	if (*cp == '"')
		++cp;

#ifdef WIN32
	if ((cp[0] == '/') || (cp[0] == '\\') ||
		(strlen(cp) >= 3 &&
		isalpha(cp[0]) && cp[1] == ':' &&
		((cp[2] == '\\') || (cp[2] == '/'))))
		/* matches c:\ or c:/ */
#else
		if (cp[0] == '/')
#endif
			return (1);
		return (0);
	}

/**
 * @brief
 *	Replace sub with repl in str.
 *
 * @par Note
 *	same as replace_space except the matching character to replace
 *      is not necessarily a space but the supplied 'sub' string, plus leaving
 *      alone existing 'repl' sub strings and no quoting if 'repl' is ""
 *
 * @param[in]	str  - input buffer having patter sub
 * @param[in]	sub  - pattern to be replaced
 * @param[in]   repl - pattern to be replaced with
 * @param[out]  retstr : string replaced with given pattern.
 *
 */

void
replace(char *str, char	*sub, char *repl, char	*retstr)
{
	char	rstr[MAXPATHLEN+1];
	int	i, j;
	int	repl_len;
	int	has_match = 0;
	int	sub_len;

	if (str == NULL || repl == NULL || sub == NULL)
		return;

	if (*str == '\0') {
		retstr[0] = '\0';
		return;
	}

	if (*sub == '\0') {
		strcpy(retstr, str);
		return;
	}

	repl_len = strlen(repl);
	sub_len = strlen(sub);

	i = 0;
	while (*str != '\0') {
		if( strncmp(str, sub, sub_len) == 0 && \
						repl_len > 0 ) {
			for (j=0; (j< repl_len && i <= MAXPATHLEN); j++, i++) {
				rstr[i] = repl[j];
			}
			has_match = 1;
		} else if (strncmp(str, sub, sub_len) == 0) {
			for (j=0; (j < sub_len && i <= MAXPATHLEN); j++, i++) {
				rstr[i] = sub[j];
			}
			has_match = 1;
		} else {
			rstr[i] = *str;
			i++;
			has_match = 0;
		}

		if (i > MAXPATHLEN) {
			retstr[0] = '\0';
			return;
		}

		if (has_match) {
			str += sub_len;
		} else {
			str++;
		}
	}
	rstr[i] = '\0';

	strncpy(retstr, rstr, i + 1);
}


/**
 * @brief
 *	Escape every occurrence of 'delim' in 'str' with 'esc'
 *
 * @param[in]	str     - input string
 * @param[in]	delim   - delimiter to be searched in str
 * @param[in]	esc     - escape character to be added if delim found in str
 *
 * @return	string
 * @retval	NULL	- memory allocation failed or str is NULL
 * @retval	retstr	- output string, with every occurrence of delim escaped with 'esc'
 *
 * @note
 * 	The string returned should be freed by the caller.
 */

char *
escape_delimiter(char *str, char *delim, char esc)
{
	int     i = 0;
	int     j = 0;
	int     delim_len = 0;
	int     retstrlen = 0;
	char    *retstr = NULL;
	char    *temp = NULL;

	if (str == NULL)
		return NULL;

	if (*str == '\0' || (delim == NULL || *delim == '\0') || esc == '\0') {
		return strdup((char *)str);
	}
	delim_len = strlen(delim);
	retstr = (char *) malloc(MAXBUFLEN);
	if (retstr == NULL)
		return NULL;
	retstrlen = MAXBUFLEN;

	while (*str != '\0') {
		/* We dont want to use strncmp function if delimiter is a character. */
		if ((*str == esc && !ISESCAPED(*(str+1))) || (delim_len == 1
				&& *str == *delim)) {
			retstr[i++] = esc;
			retstr[i++] = *str++;
		} else if (strncmp(str, delim, delim_len) == 0 && ((i + 1 + delim_len)
				< retstrlen)) {
			retstr[i++] = esc;
			for (j = 0; j < delim_len; j++, i++)
				retstr[i] = *str++;
		} else if ((i + 1 + delim_len) < retstrlen)
			retstr[i++] = *str++;

		if (i >= (retstrlen - (1 + delim_len))) {
			retstrlen *= BUFFER_GROWTH_RATE;
			temp = (char *) realloc(retstr, retstrlen);
			if (temp == NULL) {
				free(retstr);
				return NULL;
			}
			retstr = temp;
		}
	}
	retstr[i] = '\0';
	return retstr;
}


/**
 *
 * @brief
 * 	file_exists: returns 1 if file exists; 0 otherwise.
 *
 * @param[in]	path - file pathname being checked.
 *
 * @return 	int
 * @retval	1	if 'path' exists.
 * @retval	0	if 'path'does not exist.
 */
int
file_exists(char *path)
{
	struct stat sbuf;

#ifdef WIN32
	if (lstat(path, &sbuf) == -1) {
		int ret = GetLastError();
		if (ret == ERROR_FILE_NOT_FOUND || \
			ret == ERROR_PATH_NOT_FOUND) {
			return 0;
		}
	}
#else
	if( (stat(path, &sbuf) == -1) && \
                                        (errno == ENOENT) )
		return (0);
#endif
	return (1);
}

/**
 * @brief
 *	Given the two hostnames, compare their short names and full names to make sure if those
 *      point to same host.
 *
 * @param[in]	        host1 - first host
 * @param[in]           host2 - second host
 *
 * @return              int
 * @retval	        0 - hostnames point to different hosts
 * @retval	        1 - hostnames point to same host
 *
 */
int
is_same_host(char *host1, char *host2)
{
	char host1_full[PBS_MAXHOSTNAME + 1] = {'\0'};
	char host2_full[PBS_MAXHOSTNAME + 1] = {'\0'};
	if (host1 == NULL || host2 == NULL)
		return 0;
	if (strcasecmp(host1, host2) == 0)
		return 1;
	if ((get_fullhostname(host1, host1_full, (sizeof(host1_full) - 1)) != 0)
		|| (get_fullhostname(host2, host2_full, (sizeof(host2_full) - 1)) != 0))
		return 0;
	if (strcasecmp(host1_full, host2_full) == 0)
		return 1;
	return 0;
}

/**
 * @brief Determine if place_def is in place_str
 * @see place_sharing_type and getplacesharing
 *
 * @param[in] place_str - The string representation of the place directive
 * @param[in] place_def - The type of place to check
 *
 * @return Whether the place directive contains the type of exclusivity
 * queried for.
 * @retval 1 If the place directive is of the type queried
 * @retval 0 If the place directive is not of the type queried
 *
 *@par MT-Safe: No
 */
int
place_sharing_check(char *place_str, char *place_def)
{
	char *buf;
	char *p;
	char *psave;

	if ((place_str == NULL) || (*place_str == '\0'))
		return 0;

	if ((place_def == NULL) || (*place_def == '\0'))
		return 0;

	buf = strdup(place_str);
	if (buf == NULL)
		return 0;

	for (p = buf; (p = strtok_r(p, ":", &psave)) != NULL; p = NULL) {
		if (strcmp(p, place_def) == 0) {
			free(buf);
			return 1;
		}
	}
	free(buf);
	return 0;
}


/**
 *
 * @brief
 * 	Determines if 'str' is found in 'sep'-separated 'string_list'.
 *
 * @param[in]	str	- the substring to look for.
 * @param[in]	sep	- the separator character in 'string_list'
 * @param[in]	string_list - the list of characters to check for a 'str'
 *				match.
 * @return int
 * @retval	1	- if 'str' is found in 'string_list'.
 * @retval	0	- if 'str' not found.
 *
 * @note
 *	In the absence of a 'sep' value (i.e. empty string ''), then
 *	a white space is the default delimiter.
 *	If there's a 'sep' value, the white space character is also treated
 *	as an additional delimeter, matching only the strings that don't
 *	contain leading/trailing 'sep' char and white space character.
 */
int
in_string_list(char *str, char sep, char *string_list)
{
	char	*p = NULL;
	char	*p2 = NULL;
	char	*p_end = NULL;
	char	*ptoken = NULL;
	int	found_match = 0;

	if ((str == NULL) || (str[0] == '\0') || (string_list == NULL)) {
		return (0);
	}

	p2 = strdup(string_list);
	if (p2 == NULL) {
		return (0);
	}

	p = p2;
	p_end = p+strlen(string_list);

	while (p < p_end) {

		/* skip past [<sep> ] characters */
		while ((*p != '\0') &&  ((*p == sep) || (*p == ' '))) {
			p++;
		}

		if (*p == '\0')
			break;

		ptoken = p;	/* start of token */

		/* skip past not in [<sep> ] characters  */
		while ((*p != '\0') &&  ((*p != sep) && (*p != ' '))) {
			p++;
		}
		*p = '\0';	/* delimeter value is nulled */
		if (strcmp(str, ptoken)  == 0) {
			found_match = 1;
			break;
		}
		p++;
	}

	if (p2) {
		(void)free(p2);
	}
	return (found_match);
}

/**
 * @brief
 *		Helper function to get the authentication data in case external (non-resv-port)
 *		authentication. This is a generic wrapper for all "external" authentication methods.
 *
 *		This function is used as a callback from other libraries (currently only TPP)
 *		to get the authentication data to be sent to a peer doing connection initiation.
 *
 * @param[in] auth_type - The auth_type configured
 * @param[out] data_len - Length of the encoded authentication data
 * @param[in/out] ebuf	- Error message is updated here
 * @param[in] ebufsz	- size of the error message buffer
 *
 * @return - Encoded authentication data
 * @retval - NULL - Failure
 * @retval - !NULL - Success
 *
 */
void *
get_ext_auth_data(int auth_type, int *data_len, char *ebuf, int ebufsz)
{
	char *adata = NULL;

	*data_len = 0;

#ifndef WIN32
	/* right now, we only know about munge authentication */
	adata = pbs_get_munge_auth_data(1, ebuf, ebufsz);
	if (adata)
		*data_len = strlen(adata);
#else
	snprintf(ebuf, ebufsz, "Authentication method not supported");
#endif

	return adata;
}

/**
 * @brief
 *		Helper function to validate authentication data in case external (non-resv-port)
 *		authentication. This is a generic wrapper for all "external" authentication methods.
 *
 *		This function is used as a callback from other libraries (currently only TPP)
 *		to validate the authentication	data received from a peer doing connection initiation.
 *
 * @param[in] auth_type - The auth_type configured
 * @param[in] data      - The received authentication data to be verified
 * @param[in] data_len  - Length of the encoded authentication data
 * @param[in/out] ebuf	- Error message is updated here
 * @param[in] ebufsz	- size of the error message buffer
 *
 * @return  Error code
 * @retval  -1 - Authentication failed
 * @retval   0 - Authentication succeeded
 *
 */
int
validate_ext_auth_data(int auth_type, void *data, int data_len, char *ebuf, int ebufsz)
{
	int fromsvr = 0;
	int rc = -1;

#ifndef WIN32
	/* right now, we only know about munge authentication */
	rc = pbs_munge_validate(data, &fromsvr, ebuf, ebufsz);
	if (rc == 0 && fromsvr == 1)
		return 0;
#else
	snprintf(ebuf, ebufsz, "Authentication method not supported");
#endif

	return -1;
}

/**
 *
 *	@brief break apart a delimited string into an array of strings
 *
 *	@param[in] strlist - the delimited string
 *	@param[in] sep - the separator character
 *
 *	@return char **
 *
 *	@note
 *		The returned array of strings has to be freed by the caller.
 */
char **
break_delimited_str(char *strlist, char delim)
{
	char sep[2] = {0};
	int num_words = 1; /* number of words delimited by commas*/
	char **arr = NULL; /* the array of words */
	char *list;
	char *tok; /* used with strtok() */
	char *end;
	int i;

	sep[0] = delim;

	if (strlist == NULL) {
		pbs_errno = PBSE_BADATVAL;
		return NULL;
	}

	list = strdup(strlist);

	if (list != NULL) {
		char *saveptr = NULL;

		for (i = 0; list[i] != '\0'; i++)
			if (list[i] == delim)
				num_words++;

		if ((arr = (char **) malloc(sizeof(char *) * (num_words + 1))) == NULL) {
			pbs_errno = PBSE_SYSTEM;
			free(list);
			return NULL;
		}

		tok = strtok_r(list, sep, &saveptr);

		for (i = 0; tok != NULL; i++) {
			while (isspace((int) *tok))
				tok++;

			end = &tok[strlen(tok) - 1];

			while (isspace((int) *end)) {
				*end = '\0';
				end--;
			}

			arr[i] = strdup(tok);
			if (arr[i] == NULL) {
				pbs_errno = PBSE_SYSTEM;
				free(list);
				free_string_array(arr);
				return NULL;
			}
			tok = strtok_r(NULL, sep, &saveptr);
		}
		arr[i] = NULL;
	}
	if (list != NULL)
		free(list);

	return arr;
}

/**
 *
 *	@brief break apart a comma delimited string into an array of strings
 *
 *	@param[in] strlist - the comma delimited string
 *
 *	@return char **
 *
 */
char **
break_comma_list(char *strlist)
{
	return (break_delimited_str(strlist, ','));
}

/**
 * @brief
 *		Does a string exist in the given array?
 *
 * @param[in]	strarr	-	the string array to search, should be NULL terminated
 * @param[in]	str	-	the string to find
 *
 * @return	int
 * @retval	1	: if the string is found
 * @retval	0	: the string is not found or on error
 *
 */
int
is_string_in_arr(char **strarr, char *str)
{
	int ind;

	ind = find_string_idx(strarr, str);

	if (ind >= 0)
		return 1;

	return 0;
}

/**
 * @brief
 * 		find index of str in strarr
 *
 * @param[in]	strarr	-	the string array to search
 * @param[in]	str	-	the string to find
 *
 * @return	int
 * @retval	index of string
 * @retval	-1	: if not found
 */
int
find_string_idx(char **strarr, char *str)
{
	int i;
	if (strarr == NULL || str == NULL)
		return -1;

	for (i = 0; strarr[i] != NULL && strcmp(strarr[i], str); i++)
		;
	if (strarr[i] == NULL)
		return -1;

	return i;
}

/**
 * @brief
 *		free_string_array - free an array of strings with a NULL as a sentinel
 *
 * @param[in,out]	arr	-	the array to free
 *
 * @return	nothing
 *
 */
void
free_string_array(char **arr)
{
	int i;

	if (arr != NULL) {
		for (i = 0; arr[i] != NULL; i++)
			free(arr[i]);

		free(arr);
	}
}


/**
 * @brief
 * 		Convert a duration to HH:MM:SS format string
 *
 * @param[in]	duration	-	the duration
 * @param[out]	buf	-	the buffer to be filled
 * @param[in]	bufsize	-	size of the buffer
 *
 * @return	void
 */
void
convert_duration_to_str(time_t duration, char* buf, int bufsize)
{
	long 	hour, min, sec;
	if (buf == NULL || bufsize == 0)
		return;
	hour = duration / 3600;
	duration = duration % 3600;
	min = duration / 60;
	duration = duration % 60;
	sec = duration;
	snprintf(buf, bufsize, "%02ld:%02ld:%02ld", hour, min, sec);
}

/**
 * @brief
 *	Determines if 'str' ends with three consecutive double quotes,
 *	before a newline (if it exists).
 *
 * @param[in]	str - input string
 * @param[in]	strip_quotes - if set to 1, then modify 'str' so that
 *				the triple quotes are not part of the string.
 *
 * @return int
 * @retval 1 - if string ends with triple quotes.
 * @retval 0 - if string does not end with triple quotes.
 *
 */
int
ends_with_triple_quotes(char *str, int strip_quotes)
{
	int	ct;
	char	*p = NULL;
	int	ll = 0;

	if (str == NULL)
		return (0);

	ll = strlen(str);
	if (ll < 3) {
		return (0);
	}

	p = str + (ll-1);

	if (*p == '\n') {
		p--;
#ifdef WIN32
		if (*p  == '\r') {
			p--;
		}
#endif
	}

	ct = 0;
	while ((p >= str) && (*p == '"')) {
		ct++;
		p--;
		if (ct == 3)
			break;
	}
	if (ct == 3) {
		if (strip_quotes == 1) {
			/* null terminate the first double quote */
			*(p+1) = '\0';
		}
		return (1);
	}
	return (0);
}

/**
 * @brief
 *	Determines if 'str' begins with three consecutive double quotes.
 *
 * @param[in]	str - input string
 *
 * @return int
 * @retval 1 - if string starts with triple quotes.
 * @retval 0 - if string does not start with triple quotes.
 *
 */
int
starts_with_triple_quotes(char *str)
{
	char *p;
	int  ct;

	if (str == NULL)
		return (0);

	p = str;
	ct = 0;
	while ((*p != '\0') && (*p == '"')) {
		ct++;
		p++;
		if (ct == 3)
			break;
	}
	if (ct == 3) {
		return (1);
	}
	return (0);
}

/*
 * @brief
 *	Gets malloc_info and returns as a string
 *
 * @return char *
 * @retval NULL - Error
 * @note
 * The buffer has to be freed by the caller.
 *
 */
#ifndef WIN32
#ifdef HAVE_MALLOC_INFO
char *
get_mem_info(void) {
	FILE *stream;
	char *buf;
	size_t len;
	int err = 0;

	stream = open_memstream(&buf, &len);
	if (stream == NULL)
		return NULL;
	err = malloc_info(0, stream);
	fclose(stream);
	if (err == -1) {
		free(buf);
		return NULL;
	}
	return buf;
}
#endif /* malloc_info */
#endif /* WIN32 */

/**
 * @brief
 *	Return a copy of 'str' where non-printing characters
 *	(except the ones listed in the local variable 'special_char') are
 *	shown in ^<translated_char> notation.
 *
 * @param[in]	str - input string
 *
 * @return char *
 *
 * @note
 * 	Do not free the return value - it's in a fixed memory area that
 *	will get overwritten the next time the function is called.
 *      So best to use the result immediately or strdup() it.
 *
 *	This will return the original (non-translated) 'str' value if 
 *	an error was encounted, like a realloc() error.
 */
char *
show_nonprint_chars(char *str)
{
#ifndef WIN32
	static char	*locbuf = NULL;
	static size_t	locbuf_size = 0;
	char		*buf, *buf2;
	size_t		nsize;
	int		ch;
	char		special_char[] = "\n\t";

	if ((str == NULL) || (str[0] == '\0'))
		return str;

	nsize = (strlen(str) * 2) + 1;
	if (nsize > locbuf_size) {
		char *tmpbuf;
		if ((tmpbuf = realloc(locbuf, nsize)) == NULL)
			return str;
		locbuf = tmpbuf;
		locbuf_size = nsize;
	}

	locbuf[0] = '\0';
	buf = str;
	buf2 = locbuf;
	while ((ch = *buf++) != '\0') {
		if ((ch < 32) && !char_in_set(ch, special_char)) {
			*buf2++ = '^';
			*buf2++ = ch + 64;
		} else {
			*buf2++ = ch;
		}
	}
	*buf2 = '\0';
	return (locbuf);
#else
	return (str);
#endif
}

/**
 * @brief
 *  get_preemption_order - deduce the preemption ordering to be used for a job
 *
 *  @param[in]	porder - static value of preempt order from the sched object
 *  						this array is assumed to be of size PREEMPT_ORDER_MAX
 *  @param[in]	req - amount of requested time for the job
 *  @param[in]	used - amount of used time by the job
 *
 *  @return	struct preempt_ordering *
 *  @retval	preempt ordering for the job
 *  @retval	NULL if error
 */
struct preempt_ordering *
get_preemption_order(struct preempt_ordering *porder, int req, int used)
{
	int i;
	int percent_left = 0;
	struct preempt_ordering *po = NULL;

	if (porder == NULL)
		return NULL;

	po = &porder[0];
	if (req < 0 || used < 0)
		return po;

	/* check if we have more then one range... no need to choose if not */
	if (porder[1].high_range != 0) {
		percent_left = 100 - (used / req) * 100;
		if (percent_left < 0)
			percent_left = 1;

		for (i = 0; i < PREEMPT_ORDER_MAX; i++) {
			if (percent_left <= porder[i].high_range
					&& percent_left >= porder[i].low_range) {
				po = &porder[i];
				break;
			}
		}
	}

	return po;
}
