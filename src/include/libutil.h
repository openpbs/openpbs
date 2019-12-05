/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
#ifndef _HAVE_LIB_UTIL_H
#define _HAVE_LIB_UTIL_H
#ifdef  __cplusplus
extern "C" {
#endif


#include <time.h>
#include <stdio.h>

/* misc_utils specific */

/* replace - Replace sub-string  with new pattern in string */
void replace(char *, char *, char *, char *);

/* show_nonprint_chars - show non-printable characters in string */
char *show_nonprint_chars(char *);

/*	char_in_set - is the char c in the tokenset */
int char_in_set(char c, const char *tokset);

/* string_token - strtok() without an an internal state pointer */
char *string_token(char *str, const char *tokset, char **ret_str);
int in_string_list(char *str, char sep, char *string_list);

int copy_file_internal(char *src, char *dst);

int is_full_path(char *path);
int file_exists(char *path);
int is_same_host(char *, char *);

/* Determine if a placement directive is present in a placment string. */
int place_sharing_check(char *, char *);

/* execvnode_seq_util specific */
#define TOKEN_SEPARATOR "~"
#define MAX_INT_LENGTH 10

#define WORD_TOK "{"
#define MAP_TOK ","
#define WORD_MAP_TOK "}"
#define RANGE_TOK "-"
#define COUNT_TOK "#"

/* Memory Allocation Error Message */
#define MALLOC_ERR_MSG "No memory available"

/* Dictionary is a list of words */
typedef struct dict {
	struct word *first;
	struct word *last;
	int count;
	int length;
	int max_idx;
} dictionary;

/* Each word maps to an associated set (map) in the dictionary */
struct word {
	char *name;
	struct word *next;
	struct map *map;
	int count;
};

/* A map is the associated set of a word */
struct map {
	int val;
	struct map *next;
};

/* Compress a delimited string into a dictionary compressed representation */
char *condense_execvnode_seq(char *);

/* Decompress a compress string into an array of words (strings) indexed by
 * their associated indices */
char **unroll_execvnode_seq(char *, char ***);

/*
 * Get the total number of indices represented in the condensed string
 * which corresponds to the total number of occurrences in the execvnode string
 */
int get_execvnodes_count(char *);

/* Free the memory allocated to an unrolled string */
void free_execvnode_seq(char **ptr);


/* pbs_ical specific */

/* Define the location of ical zoneinfo directory
 * this will be relative to PBS_EXEC (see pbsd_init and pbs_sched) */
#define ICAL_ZONEINFO_DIR "/lib/ical/zoneinfo"

/* Returns the number of occurrences defined by a recurrence rule */
int get_num_occurrences(char *rrule, time_t dtstart, char *tz);

/* Get the occurrence as defined by the given recurrence rule,
 * start time, and index. This function assumes that the
 * time dtsart passed in is the one to start the occurrence from.
 */
time_t get_occurrence(char *, time_t, char *, int);

/*
 * Check if a recurrence rule is valid and consistent.
 * The recurrence rule is verified against a start date and checks
 * that the frequency of the recurrence matches the duration of the
 * submitted reservation. If the duration of a reservation exceeds the
 * granularity of the frequency then an error message is displayed.
 *
 * The recurrence rule is checked to contain a COUNT or an UNTIL.
 *
 * Note that the TZ environment variable HAS to be set for the occurrence's
 * dates to be correctly computed.
 */
int check_rrule(char *, time_t, time_t, char *, int *);

/*
 * Displays the occurrences in a two-column format:
 * the first column corresponds to the occurrence date and time
 * the second column corresponds to the reserved execvnode
 */
void display_occurrences(char *, time_t, char *, char *, int, int);

/*
 * Set the zoneinfo directory
 */
void set_ical_zoneinfo(char *path);

/*
 * values for the vnode 'sharing' attribute
 */
enum vnode_sharing
{
	VNS_UNSET,
	VNS_DFLT_SHARED,
	VNS_DFLT_EXCL,
	VNS_IGNORE_EXCL,
	VNS_FORCE_EXCL,
	VNS_DFLT_EXCLHOST,
	VNS_FORCE_EXCLHOST,
	VNS_FORCE_SHARED,
};

/*
 * convert vnode sharing enum into string form
 */
char *vnode_sharing_to_str(enum vnode_sharing vns);
/*
 * convert string form of vnode sharing to enum
 */
enum vnode_sharing str_to_vnode_sharing(char *vn_str);

/*
 * concatenate two strings by expanding target string as needed.
 * 	  Operation: strbuf += str
 */
char *pbs_strcat(char **strbuf, int *ssize, char *str);

char *pbs_fgets(char **pbuf, int *pbuf_size, FILE *fp);
char *pbs_fgets_extend(char **pbuf, int *pbuf_size, FILE *fp);

/*
 * Internal asprintf() implementation for use on all platforms
 */
int pbs_asprintf(char **dest, const char *fmt, ...);

/*
 * calculate the number of digits to the right of the decimal point in
 *        a floating point number.  This can be used in conjunction with
 *        printf() to not print trailing zeros.
 *
 * Use: int x = float_digits(fl, 8);
 * printf("%0.*f\n", x, fl);
 *
 */
int float_digits(double fl, int digits);

/* Various helper functions in hooks processing */
int starts_with_triple_quotes(char *str);
int ends_with_triple_quotes(char *str, int strip_quotes);

/* Special symbols for copy_file_internal() */

#define COPY_FILE_BAD_INPUT	1
#define COPY_FILE_BAD_SOURCE	2
#define COPY_FILE_BAD_DEST	3
#define	COPY_FILE_BAD_WRITE	4


#define LOCK_RETRY_DEFAULT	2
int
lock_file(FILE *fp, int op, char *filename, int lock_retry,
	char *err_msg, size_t err_msg_len);

/* RSHD/RCP related */
/* Size of the buffer used in communication with rshd deamon */
#define RCP_BUFFER_SIZE 65536


#define MAXBUFLEN 1024
#define BUFFER_GROWTH_RATE 2


/*
 *      break_comma_list - break apart a comma delimited string into an array
 *                         of strings
 */
char **break_comma_list(char *list);

/*
 *      break_delimited_str - break apart a delimited string into an array
 *                         of strings
 */
char **break_delimited_str(char *list, char delim);

/*
 * find index of str in strarr
 */
int find_string_idx(char **strarr, char *str);

/*
 *	is_string_in_arr - Does a string exist in the given array?
 */
int is_string_in_arr(char **strarr, char *str);

/*
 *      free_string_array - free an array of strings with NULL as sentinel
 */
void free_string_array(char **arr);

/*
 *      Escape every occurrence of 'delim' in 'str' with 'esc'
 */
char * escape_delimiter(char *str, char *delim, char esc);

#ifdef HAVE_MALLOC_INFO
char * get_mem_info(void);
#endif

/* Size of time buffer */
#define TIMEBUF_SIZE 128

/**
 *
 * 	convert_duration_to_str - Convert a duration to HH:MM:SS format string
 *
 */
void convert_duration_to_str(time_t duration, char* buf, int bufsize);

/**
 * deduce the preemption ordering to be used for a job
 */
struct preempt_ordering *
get_preemption_order(struct preempt_ordering *porder, int req, int used);

/**
 * Begin collecting performance stats (e.g. walltime)
 */
void
perf_stat_start(char *instance);

/**
 * Remove a performance stats entry.
 */
void
perf_stat_remove(char *instance);

/**
 * check delay in client commands
 */
void create_query_file(void);
void delay_query(void);

/**
 * End collecting performance stats (e.g. walltime)
 */
char *
perf_stat_stop(char *instance);

#ifdef  __cplusplus
}
#endif
#endif
