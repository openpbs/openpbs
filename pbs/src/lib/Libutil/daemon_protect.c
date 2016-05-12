#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#ifdef WIN32
#define pid_t int
#endif
#include "server_limits.h"

#ifndef MAXPATHLEN
#define MAXPATHLEN 1024
#endif

/**
 * @brief
 *	Where possible enable protection for the daemon from the OS.
 *
 * @par	Linux
 *	Protect from OOM (Out of Memory) killer
 *
 * @param[in] pid_t pid - pid of process to protect, if 0 then myself.
 * @param[in] enum PBS_Daemon_Protect action - turn on/off proection:
 *	PBS_DAEMON_PROTECT_ON/OFF
 */

void
daemon_protect(pid_t pid, enum PBS_Daemon_Protect action)
{

#ifdef linux
	int  fd;
	char fname[MAXPATHLEN+1];
	struct oom_protect {
		char *oom_value[2];	/* value to write: unprotect/protect */
		char *oom_path;		/* path to which to write */
	};
	static struct oom_protect oom_protect_old = {
		{
			"0\n",		/* unprotect value */
			"-17\n" 	/* protect value   */
		},
		"/proc/%ld/oom_adj"
	};
	static struct oom_protect oom_protect_new = {
		{
			"0\n",		/* unprotect value */
			"-1000\n"	/* protect value   */
		},
		"/proc/%ld/oom_score_adj"
	};

	if (pid == 0)
		pid = getpid();	/* use my pid */

	/**
	 *	for Linux:  Need to protect daemons from the Out of Memory killer.
	 *
	 *	First try to set /proc/<pid>/oom_score_adj to -1000 to protect
	 *	or 0 to unprotect.
	 *	If oom_score_adj is does not exist, try setting /proc/<pid>oom_adj
	 *	which is older to -17 to protect or 0 to unprotect.
	 */
	snprintf(fname, MAXPATHLEN, oom_protect_new.oom_path, pid);
	if ((fd = open(fname, O_WRONLY)) != -1) {
		write(fd, oom_protect_new.oom_value[(int)action], sizeof(oom_protect_new.oom_value[(int)action])-1);

	} else {

		/* failed to open "oom_score_adj", now try "oom_adj" */
		/* found in older Linux kernels			     */
		snprintf(fname, MAXPATHLEN, oom_protect_old.oom_path, pid);
		if ((fd = open(fname, O_WRONLY)) != -1) {
			write(fd, oom_protect_old.oom_value[(int)action], sizeof(oom_protect_old.oom_value[(int)action])-1);
		}
	}
	if (fd != -1)
		close(fd);
#endif	/* linux */

	/**
	 *	For any other OS, we don't do anything currently.
	 */
	return;
}
