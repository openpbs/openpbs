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
 *  @file    pbs_ds_monitor.c
 *
 *  @brief
 *		pbs_ds_monitor - This file contains functions related to database and serialization.
 *
 * Functions included are:
 * 	clear_stop_db_file()
 * 	check_and_stop_db()
 * 	get_pid()
 * 	lock_out()
 * 	acquire_lock()
 * 	win_db_monitor()
 * 	clear_tmp_files()
 * 	checkpid()
 * 	win_db_monitor_child()
 * 	acquire_lock()
 * 	unix_db_monitor()
 * 	main()
 */
#include <pbs_config.h>
#include <pbs_version.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <errno.h>
#include "server_limits.h"
#include <pbs_internal.h>
#include "pbs_db.h"
#include "pbs_ifl.h"

#define MAX_LOCK_ATTEMPTS 5
#define MAX_DBPID_ATTEMPTS 20
#define TEMP_BUF_SIZE 100
#define RES_BUF_SIZE 4096

char thishost[PBS_MAXHOSTNAME + 1];

/**
 * @brief
 * 		clear_stop_db_file - Function to clear the db stop file
 *
 * @return	void
 *
 * @par MT-safe: Yes
 */
void
clear_stop_db_file(void)
{
	char closefile[MAXPATHLEN + 1];
	snprintf(closefile, MAXPATHLEN, "%s/datastore/pbs_dbclose", pbs_conf.pbs_home_path);
	unlink(closefile);
}

/**
 * @brief
 * 		check_and_stop_db - Function to check for db stop file and stop the database
 *          if such a file exists
 *
 * @param[in]	dbpid	-	Pid of the database process (unused for now)
 *
 * @return	void
 *
 * @par MT-safe: Yes
 */
void
check_and_stop_db(int dbpid)
{
	char closefile[MAXPATHLEN + 1];

	snprintf(closefile, MAXPATHLEN, "%s/datastore/pbs_dbclose", pbs_conf.pbs_home_path);

	if (access(closefile, R_OK) == 0) {
		/* file present, somebody is asking us to quit the database */
		/* first clear the file */
		unlink(closefile);
		/* now stop the database */
		pbs_stop_db(thishost, pbs_conf.pbs_data_service_port);
	}
}

/**
 * @brief
 * 		Get the pid of the database from the postmaster.pid
 *			file located inside directory pointed by dbstore
 *
 * @param[in]	dbstore	-	The path to the database data directory
 *
 * @retval	0	-	Function failed
 * @retval	>0	-	Pid of the postmaster master process
 *
 * @par MT-safe:	Yes
 */
static pid_t
get_pid()
{
	char pidfile[MAXPATHLEN + 1];
	FILE *fp;
	char buf[TEMP_BUF_SIZE + 1];
	pid_t pid = 0;

	snprintf(pidfile, MAXPATHLEN, "%s/datastore/postmaster.pid", pbs_conf.pbs_home_path);
	if (access(pidfile, R_OK) != 0)
		return 0;

	if ((fp = fopen(pidfile, "r")) == NULL)
		return 0;

	memset(buf, 0, TEMP_BUF_SIZE + 1);
	fgets(buf, TEMP_BUF_SIZE, fp);
	buf[TEMP_BUF_SIZE] = '\0';

	fclose(fp);

	if (strlen(buf) == 0)
		return 0;

	pid = atol(buf);
	if (pid == 0)
		return 0;

	if (kill(pid, 0) != 0)
		return 0;
	return pid;
}

/**
 * @brief
 * 		lock_out - Function to lock/unlock a file.
 *
 *		For Unix, this uses fcntl lock (not inheritable).
 *		If the operand is F_WRLCK, then this also writes
 *		the pid of this process to the lockfile.
 *
 * @param[in]	fds	-	The descriptor of the file to be locked
 * @param[in]	op	- 	Operation to perform
 *						F_WRLCK - To obtain a "write lock"
 *						F_UNLCK	- To release a previous lock
 * 						These contants are defined in win.h.
 *
 * @retval	0	-	Function succeeded for the given operation
 * @retval	1	-	Failed (eg to lock the file).
 *
 * @par MT-safe:	Yes
 */
static int
lock_out(int fds, int op)
{
	struct flock flock;
	char buf[PBS_MAXHOSTNAME + 10];

	(void) lseek(fds, (off_t) 0, SEEK_SET);
	flock.l_type = op;
	flock.l_whence = SEEK_SET;
	flock.l_start = 0;
	flock.l_len = 0;

	if (fcntl(fds, F_SETLK, &flock) != -1) {
		if (op == F_WRLCK) {
			/* if write-lock, record hostname and pid in file */
			(void) ftruncate(fds, (off_t) 0);
			(void) sprintf(buf, "%s:%d\n", thishost, getpid());
			(void) write(fds, buf, strlen(buf));
		}
		return 0;
	}
	return 1;
}

/**
 * @brief
 * 		This is the Unix counterpart of acquire_lock
 * @par
 *  	This function creates/opens the lock file, and locks the file.
 *  	In case of a failover environment, the whole operation is retried
 *  	several times in a loop.
 *
 * @param[in]  lockfile         - Path of db_lock file.
 * @param[out] reason           - Reason for failure, if not able to accquire lock
 * @param[in]  reasonlen        - reason buffer legnth.
 * @param[out] is_lock_hld_by_thishost  - This flag is set if the lock is held by the host
 *                                         requesting accquire_lock in check_mode.
 *
 * @return	File descriptor of the open and locked file
 * @retval	-1	: Function failed to acquire lock
 * @retval	!=-1	: Function succeeded (file descriptor returned)
 *
 * @par MT-safe:	Yes
 */
int
acquire_lock(char *lockfile, char *reason, int reasonlen, int *is_lock_hld_by_thishost)
{
	int fd;
	struct stat st;
	int i, j;
	time_t lasttime = 0;
	int rc;
	char who[PBS_MAXHOSTNAME + 10];
	char *p;

	if (reasonlen > 0)
		reason[0] = '\0';

	if (pbs_conf.pbs_secondary == NULL)
		j = 1; /* not fail over, try lock one time */
	else
		j = MAX_LOCK_ATTEMPTS; /* fail over, try X times */

#ifndef O_RSYNC
#define O_RSYNC 0
#endif

again:
	if ((fd = open(lockfile, O_RDWR | O_CREAT | O_RSYNC, 0600)) == -1) {
		snprintf(reason, reasonlen, "Could not access lockfile, errno=%d", errno);
		return -1;
	}

	/* check time stamp of lock file */
	if (fstat(fd, &st) == -1) {
		snprintf(reason, reasonlen, "Failed to stat lockfile, errno=%d", errno);
		close(fd);
		return -1;
	}

	/* record the last modified timestamp */
	lasttime = st.st_mtime;

	for (i = 0; i < j; i++) { /* try X times where X is MAX_LOCK_ATTEMPTS */
		if (i > 0)
			sleep(1);
		/* attempt to lock the datastore directory */
		if (lock_out(fd, F_WRLCK) == 0)
			return fd;
	}

	/* do this only if failover is configured */
	if (pbs_conf.pbs_secondary != NULL) {
		/*
		 * Came here, means we could not lock even after j attempts.
		 *
		 * 2 levels of check will be performed (based on the last modified timestamp):
		 *
		 * 1) Check the lock file's modified timestamp and compare with "lasttime" to see if the file was modified
		 *    in between. If the file was modified, then the other side up and so we give up.
		 *
		 * 2) We know that the modified timestamp is not updating however we need to make
		 *    sure that the other side is really gone. Therefore we check the difference of last
		 *    updated timestamp from now (current system time). If the difference > (4*j) seconds,
		 *    then the other side has vanished at the OS level itself, and NFS cannot unlock it.
		 *    So delete the lockfile and start afresh. For this to work, make sure that the
		 *    time on primary, secondary and the pbs_home server (NFS server) are synced.
		 */

		/* Re-check time stamp of lock file */
		if (fstat(fd, &st) == -1) {
			snprintf(reason, reasonlen, "Failed to stat lockfile, errno=%d", errno);
			close(fd);
			return -1;
		}

		/* Check if time stamp of lock file has updated at all */
		if (st.st_mtime == lasttime) {
			/* Modified times stamp did not update in the given window. Re-check how long it has been stale */
			if (time(0) - lasttime >= (MAX_LOCK_ATTEMPTS * 4)) {
				/* other side is long dead, clear up stuff */
				close(fd);
				unlink(lockfile);
				fd = -1;
				lasttime = 0;
				goto again;
			}
		}
	}

	/* all attempts to lock failed, try to see who has it locked */
	(void) lseek(fd, (off_t) 0, SEEK_SET);
	if ((rc = read(fd, who, sizeof(who) - 1)) > 0) {
		who[rc - 1] = '\0';
		p = strchr(who, ':');
		if (p) {
			*p = '\0';
			snprintf(reason, reasonlen,
				 "Lock seems to be held by pid: %s running on host: %s",
				 (p + 1), who);
		} else {
			snprintf(reason, reasonlen, "Lock seems to be held by %s", who);
		}
		if (is_lock_hld_by_thishost != NULL) {
			if (strcmp(thishost, who) == 0)
				*is_lock_hld_by_thishost = 1;
			else
				*is_lock_hld_by_thishost = 0;
		}
	}

	close(fd);
	fd = -1;

	return fd;
}

/**
 * @brief	This is the Unix couterpart of the monitoring
 *			code.
 * @par
 *		This function does the following:
 *		a) Creates a pipe, forks itself, parent waits to read on pipe.
 *		b) Child creates/opens a file $PBS_HOME/datastore/pbs_dblock.
 *		c) Attempts to lock the file. If locking
 *			succeeds, unlocks the file and writes 0 (success) to the write
 *			end of the pipe. If locking fails, writes 1 (failure) to pipe.
 *			Parent reads from pipe and exits with the code read from pipe.
 *		d) If mode is "check" then child quits.
 *		e) If mode is "monitor", continues in the background, checking
 *			the database pid in a loop forever. If database pid goes
 *			down, then it unlocks the file and exits.
 *
 * @param[in]	mode	-	"check" - to just check if lockfile can be locked
 *		     				"monitor" - to launch a monitoring child process that
 *							holds onto the file lock.
 *
 * @retval	1	-	Function failed to acquire lock
 * @retval	0	-	Function succeded in the requested operation
 * @par
 * 		The return values are not used by the caller (parent process) since
 * 		in the success case this function does not return. Instead, the parent
 * 		waits on the read end of the pipe to read a status from the monitoring
 * 		child process.
 *
 * @par MT-safe: Yes
 */
int
unix_db_monitor(char *mode)
{
	int fd;
	int rc;
	int i;
	pid_t dbpid;
	char lockfile[MAXPATHLEN + 1];
	int pipefd[2];
	int res;
	int is_lock_local = 0;
	char reason[RES_BUF_SIZE];

	reason[0] = '\0';

	if (pipe(pipefd) != 0) {
		fprintf(stderr, "Unable to create pipe, errno = %d\n", errno);
		return 1;
	}

	snprintf(lockfile, MAXPATHLEN, "%s/datastore/pbs_dblock", pbs_conf.pbs_home_path);

	/* first fork off */
	rc = fork();
	if (rc == -1) {
		fprintf(stderr, "Unable to create process, errno = %d\n", errno);
		return 1;
	}

	if (rc > 0) {
		close(pipefd[1]);
		/*
		 * child can continue to execute in case of "monitor",
		 * so dont wait for child to exit, rather read code
		 * from pipe that child will write to
		 */
		if (read(pipefd[0], &res, sizeof(int)) != sizeof(int))
			return 1;

		if (res != 0) {
			read(pipefd[0], &reason, sizeof(reason));
			fprintf(stderr, "Failed to acquire lock on %s. %s\n", lockfile, reason);
		}

		return (res); /* return parent with success */
	}

	close(pipefd[0]);

	/* child */
	if (setsid() == -1) {
		close(pipefd[1]);
		return 1;
	}

	(void) fclose(stdin);
	(void) fclose(stdout);
	(void) fclose(stderr);

	/* Protect from being killed by kernel */
	daemon_protect(0, PBS_DAEMON_PROTECT_ON);

	if ((fd = acquire_lock(lockfile, reason, sizeof(reason), &is_lock_local)) == -1) {
		if (is_lock_local && strcmp(mode, "check") == 0) {
			/* write success to parent since lock is already held by the localhost */
			res = 0;
			write(pipefd[1], &res, sizeof(int));
			close(pipefd[1]);
			return 0;
		}
		res = 1;
		write(pipefd[1], &res, sizeof(int));
		write(pipefd[1], reason, sizeof(reason));
		close(pipefd[1]);
		return 1;
	}

	/* unlock before writing success to parent, to avoid race */
	if (strcmp(mode, "check") == 0) {
		lock_out(fd, F_UNLCK);
		close(fd);
		unlink(lockfile);
	}

	/* write success to parent since we acquired the lock */
	res = 0;
	write(pipefd[1], &res, sizeof(int));
	close(pipefd[1]);

	if (strcmp(mode, "check") == 0)
		return 0;

	/* clear any residual stop db file before starting monitoring */
	clear_stop_db_file();

	/*
	 * first find out the pid of the postgres process from dbstore/postmaster.pid
	 * wait for a while till it is found
	 * if not found within MAX_DBPID_ATTEMPTS then break with error
	 * if found, start monitoring the pid
	 *
	 */
	dbpid = 0;
	for (i = 0; i < MAX_DBPID_ATTEMPTS; i++) {
		if ((dbpid = get_pid()) > 0)
			break;
		(void) utimes(lockfile, NULL);
		sleep(1);
	}

	if (dbpid == 0) {
		/* database did not come up, so quit after unlocking file */
		lock_out(fd, F_UNLCK);
		close(fd);
		unlink(lockfile);
		return 0;
	}

	while (1) {
		(void) utimes(lockfile, NULL);

		if (kill(dbpid, 0) != 0)
			break;
		if (!((dbpid = get_pid()) > 0))
			break;

		/* check if stop db file exists */
		check_and_stop_db(dbpid);

		sleep(1);
	}

	lock_out(fd, F_UNLCK);
	close(fd);
	unlink(lockfile);

	return 0;
}

/**
 * @brief
 * 		main - the entry point in pbs_config_add_win.c
 *
 * @param[in]	argc	-	argument count
 * @param[in]	argv	-	argument variables.
 *
 * @return	int
 * @retval	1	-	Function failed to perform the requested operation.
 * @retval	0	-	Function succeeded in the requested operation
 */
int
main(int argc, char *argv[])
{
	char *mode;

	if (argc < 2) {
		fprintf(stderr, "Usage: %s check|monitor\n", argv[0]);
		return 1;
	}
	mode = argv[1];

	if (pbs_loadconf(0) == 0) {
		fprintf(stderr, "Failed to load PBS conf file\n");
		return 1;
	}

	if (gethostname(thishost, (sizeof(thishost) - 1)) == -1) {
		fprintf(stderr, "Failed to detect hostname\n");
		return -1;
	}

	return unix_db_monitor(mode);
}
