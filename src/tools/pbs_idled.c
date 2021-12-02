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
 * @file	pbs_idled.c
 *
 * @brief
 * 		pbs_idled.c	- This file functions related to making the pbs idle.
 *
 * Functions included are:
 * 	main()
 * 	event_setup()
 * 	pointer_query()
 * 	update_utime()
 * 	X_handler()
 */
#include <pbs_config.h>
#include <pbs_ifl.h>
#include "cmds.h"
#include "pbs_version.h"

#include <X11/X.h>
#include <X11/Xlib.h>
#include <time.h>
#include <X11/Intrinsic.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <utime.h>
#include <errno.h>

#define EVER 1

/* used to pass back pointer locations from pointer_query() */
struct xy {
	int x;
	int y;
};

/* prototypes */
int event_setup(Window w, Display *dsp);
int pointer_query(Display *dsp, Window w, struct xy *p);
void update_utime(char *filename);
int X_handler(Display *dsp);

/* globals */
char **argv_save;
char **env_save;
/**
 * @brief
 * 		main - the entry point in pbs_config_add_win.c
 *
 * @param[in]	argc	-	argument count
 * @param[in]	argv	-	argument variables.
 * @param[in]	envp	-	environment values.
 *
 * @return	int
 * @retval	1	-	Function failed to perform the requested operation.
 * @retval	0	-	Function succeeded in the requested operation
 */
int
main(int argc, char *argv[], char *envp[])
{
	Window w;
	char *env_dsp = NULL;
	Display *dsp = NULL;
	XEvent event;
	int delay = 5;
	int reconnect_delay = 180;
	int do_update = 0;
	int is_daemon = 0;
	time_t create_time = 0;
	char *filename = NULL;
	char filename_buf[MAXPATHLEN];
	char *username;
	struct xy cur_xy, prev_xy;
	struct stat st;
	char errbuf[BUFSIZ]; /* BUFSIZ is sufficient to hold buffer msg */
	int fd;
	int c;

	/*the real deal or output pbs_version and exit?*/
	PRINT_VERSION_AND_EXIT(argc, argv);

	pbs_loadconf(0);

	while ((c = getopt(argc, argv, "D:w:f:r:t:-:")) != -1)
		switch (c) {
			case 'w':
				delay = atoi(optarg);
				break;
			case 'r':
				reconnect_delay = atoi(optarg);
				break;
			case 'f':
				filename = optarg;
				break;
			case 'D':
				env_dsp = optarg;
				break;
			case 't':
				if (!strcmp(optarg, "daemon"))
					is_daemon = 1;
				break;
			default:
				/* show usage and exit */
				fprintf(stderr, "USAGE: %s [-w wait between X queries] [-f idle_file] [-D Display] [-r reconnct_delay]\n", argv[0]);
				fprintf(stderr, "       %s --version\n", argv[0]);
				exit(1);
		}

	prev_xy.x = -1;
	prev_xy.y = -1;

	if (filename == NULL) {
		username = getlogin();
		if (username == NULL)
			username = getenv("USER");
		if (username == NULL)
			username = "UNKNOWN";
		sprintf(filename_buf, "%s/%s/%s", pbs_conf.pbs_home_path, "spool/idledir", username);
		filename = filename_buf;
	}

	if (stat(filename, &st) == -1) {
		if (errno == ENOENT) { /* file doesn't exist... lets create it */
			if ((fd = creat(filename, S_IRUSR | S_IWUSR)) == -1) {
				sprintf(errbuf, "Can not open %s", filename);
				perror(errbuf);
				exit(1);
			}
			close(fd);
		} else {
			perror("File Error");
			exit(1);
		}
	}

	argv_save = argv;
	env_save = envp;

	if (env_dsp == NULL)
		env_dsp = getenv("DISPLAY");

	if (env_dsp == NULL)
		env_dsp = ":0";

	while (dsp == NULL) {
		dsp = XOpenDisplay(env_dsp);

		if (dsp == NULL) {
#ifdef DEBUG
			printf("Could not open display %s\n", env_dsp == NULL ? "(null)" : env_dsp);
#endif
			sleep(reconnect_delay);
		}
	}

	/* only set the io error handler to ignore X connection closes IF
	 * we're running as a daemon.  If we are run out of Xsession, and
	 * ignore the close of the X connection, we'll stick around forever... not
	 * good.
	 */
	if (is_daemon)
		XSetIOErrorHandler(X_handler);

	w = RootWindow(dsp, XDefaultScreen(dsp));

	event_setup(w, dsp);

	for (; EVER;) {
		sleep(delay);

		while (XCheckMaskEvent(dsp, KeyPressMask | KeyReleaseMask | SubstructureNotifyMask, &event)) {
			switch (event.type) {
				case KeyPress:
				case KeyRelease:
					do_update = 1;
					break;
				case CreateNotify:
					create_time = time(NULL) + 30;
					break;
			}
		}

		if (create_time != 0) {
			if (time(NULL) >= create_time) {
				event_setup(w, dsp);
				create_time = 0;
			}
		}

		if (pointer_query(dsp, w, &cur_xy))
			if (cur_xy.x != prev_xy.x || cur_xy.y != prev_xy.y) {
				do_update = 1;
				prev_xy = cur_xy;
			}

		if (do_update) {
			update_utime(filename);
			do_update = 0;
		}
	}
}

/**
 * @brief
 * 		setup the event on an event in an X server.
 *
 * @param[in]	w	-	Specifies the connection to the X server.
 * @param[in]	dsp	-	Specifies the window whose events you are interested in.
 *
 * @return	int
 * @retval	0	: XQueryTree has failed
 * @retval	1	: successfully completed.
 */
int
event_setup(Window w, Display *dsp)
{
	Window root, parent, *kids;
	unsigned int nkids;
	unsigned int mask;
	int i;

	if (!XQueryTree(dsp, w, &root, &parent, &kids, &nkids))
		return 0;

	mask = (KeyPressMask | KeyReleaseMask | SubstructureNotifyMask);

	XSelectInput(dsp, w, mask);

	if (kids) {
		for (i = 0; i < nkids; i++)
			event_setup(kids[i], dsp);
	}
	if (kids != NULL)
		XFree(kids);

	return 1;
}
/**
 * @brief
 * 		It returns the root window the pointer is logically on and the pointer
 * 		coordinates relative to the root window's origin.
 *
 * @param[in]	dsp	-	Specifies the window whose events you are interested in.
 * @param[in]	w	-	Specifies the connection to the X server.
 * @param[out]	p	-	X,Y coordinate
 *
 * @return	int
 * @retval	0	: p is NULL
 * @retval	1	: successfully completed.
 */
int
pointer_query(Display *dsp, Window w, struct xy *p)
{
	Window root_return;
	Window child_return;
	int root_x;
	int root_y;
	int win_x;
	int win_y;
	unsigned int mask;

	if (p == NULL)
		return 0;

	if (XQueryPointer(dsp, w,
			  &root_return, &child_return, &root_x, &root_y, &win_x, &win_y, &mask)) {
		p->x = root_x;
		p->y = root_y;
	} else
		printf("XQueryPointer failed\n");

	return 1;
}
/**
 * @brief
 * 		set access time and modify time to current time
 *
 * @param[in]	filename	-	file for which access time needs to be updated.
 */
void
update_utime(char *filename)
{
	utime(filename, NULL);

#ifdef DEBUG
	printf("Updating utime\n");
#endif
}

/**
 * @brief
 * 		we lost our X display... let's just reexec ourself
 *
 * @param[in]	dsp	-	pointer to display ( not used here)
 *
 * @return	int
 * @retval	0	: success
 */
int
X_handler(Display *dsp)
{

#ifdef DEBUG
	printf("Lost X connection, restarting!\n");
#endif

	execve(argv_save[0], argv_save, env_save);

	return 0;
}
