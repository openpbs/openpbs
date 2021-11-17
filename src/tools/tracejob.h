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

#ifndef _TRACEJOB_H
#define _TRACEJOB_H
#ifdef __cplusplus
extern "C" {
#endif

/* Symbolic constants */

/* default number of columns on a terminal */
#ifndef DEFAULT_WRAP
#define DEFAULT_WRAP 80
#endif

/*
 * filter excessive log entires
 */
#ifndef FILTER_EXCESSIVE
#define FILTER_EXCESSIVE
#endif

/* if filter excessive if turned on and there are at least this many
 * log entires, its considered is considered excessive
 */
#ifndef EXCESSIVE_COUNT
#define EXCESSIVE_COUNT 15
#endif

/* number of entries to start */
#ifndef DEFAULT_LOG_LINES
#define DEFAULT_LOG_LINES 1024
#endif

#define SECONDS_IN_DAY 86400

/* indicies into the mid_path array */
enum index {
	IND_ACCT = 0,
	IND_SERVER = 1,
	IND_MOM = 2,
	IND_SCHED = 3
};

/* fields of a log entry */
enum field {
	FLD_DATE = 0,
	FLD_EVENT = 1,
	FLD_OBJ = 2,
	FLD_TYPE = 3,
	FLD_NAME = 4,
	FLD_MSG = 5
};

/* A PBS log entry */
struct log_entry {
	char *date;	       /* date of log entry */
	time_t date_time;      /* number of seconds from the epoch to date */
	long highres;	       /* high resolution portion of the log entry (number smaller than seconds) */
	char *event;	       /* event type */
	char *obj;	       /* what entity is writing the log */
	char *type;	       /* type of object Job/Svr/etc */
	char *name;	       /* name of object */
	char *msg;	       /* log message */
	char log_file;	       /* What log file */
	int lineno;	       /* what line in the file.  used to stabilize the sort */
	unsigned no_print : 1; /* whether or not to print the message */
			       /* A=accounting S=server M=Mom L=Scheduler */
};

/* prototypes */
int sort_by_date(const void *v1, const void *v2);
void parse_log(FILE *fp, char *job, int act);
char *strip_path(char *path);
void free_log_entry(struct log_entry *lg);
void line_wrap(char *line, int start, int end);
#ifdef NAS /* localmod 022 */
char *log_path(char *path, int index, int old, int month, int day, int year);
#else
char *log_path(char *path, int index, int month, int day, int year);
#endif /* localmod 022 */
void alloc_more_space();
void filter_excess(int threshold);
int sort_by_message(const void *v1, const void *v2);

/* Macros */
#define NO_HIGH_RES_TIMESTAMP -1

/* used by getopt(3) */
extern char *optarg;
extern int optind;
#ifdef __cplusplus
}
#endif
#endif /* _TRACEJOB_H */
