/* TODO: license header */
#include <signal.h>
#include <string.h>
#include <unistd.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>
#include <pbs_internal.h>
#include "log.h"
#include "undolr.h"


int sigusr1_flag = 0;
static int recording = 0;
static char recording_file [MAXPATHLEN + 1] = {0};

/**
 * @brief
 * 		catch_sigusr1() - the signal handler for  SIGUSR1.
 *		Set a flag for the main loop to know that a sigusr1 processes
 *
 * @param[in]	sig	- not used in fun.
 *
 * @return	void
 */
void
catch_sigusr1(int sig)
{
    sprintf(log_buffer, "%s caught signal %d", __func__, sig);
	log_event(PBSEVENT_SYSTEM | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
		LOG_NOTICE, msg_daemonname, log_buffer);

	//extern int sigusr1_flag;
	sigusr1_flag = 1;
}

/**
 * @brief
 * 	mk_recording_path - make the recording name and path used by deamons 
 *	based on the date and time: <deamon_name>_yyyymmddHHMM.undo
 *
 * @param[in] fpath - buffer to hold the live recording file path
 * @param[in] maxlen - max size of buffer
 *
 * @return  0 - Success
 *          1 - Failure
 *
 */
static int mk_recording_path(char * fpath, int maxlen) 
{

    if (pbs_loadconf(1) == 0) {
        /* TODO: print log message*/
        return (1); 
	}

    struct tm ltm;
    struct tm *ptm;
    time_t time_now;

    time_now = time(NULL);
    ptm = localtime_r(&time_now, &ltm);

    if (pbs_conf.pbs_lr_save_path)
        (void)snprintf(fpath, maxlen,
            "%s/%s_%04d%02d%02d%02d%02d.undo",
            pbs_conf.pbs_lr_save_path, msg_daemonname, ptm->tm_year+1900, ptm->tm_mon+1,
            ptm->tm_mday, ptm->tm_hour,ptm->tm_min);
    else /* default path */
        (void)snprintf(fpath, maxlen,
            "%s/%s/%s_%04d%02d%02d%02d%02d.undo",
            pbs_conf.pbs_home_path, "spool", msg_daemonname, ptm->tm_year+1900, ptm->tm_mon+1,
            ptm->tm_mday, ptm->tm_hour,ptm->tm_min);

    return (0);
}

/**
 *  TODO doxygen 
 * 
 */
void undolr()
{
    int e = 0;
    undolr_error_t  err = 0;
    undolr_recording_context_t lr_ctx;

	if (!recording)
	{
        if (mk_recording_path(recording_file, MAXPATHLEN) == 1) {
            return;
        }
        sprintf(log_buffer,
				"Undo live recording started, will save to %s", recording_file);
		log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, 
                    PBS_EVENTCLASS_SERVER, /* TODO: shoudl be based on deamon and  append function name*/
				LOG_DEBUG, msg_daemonname, log_buffer);

		e = undolr_start(&err);
		if (e)
		{
			sprintf(log_buffer,
             "undolr_recording_start() failed: error=%i errno=%i\n", e, errno);
            log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
            return;
		}

		e = undolr_save_on_termination(recording_file);
		if (e)
		{
			sprintf(log_buffer,
                "undolr_save_on_termination() failed: error=%i errno=%i\n", e, errno);
            log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
            return;
		}
		recording = 1;
	} else 
	{
        /* Stop an Undo Recording. */
        e = undolr_stop (&lr_ctx);
        if (e)
        {
            sprintf(log_buffer, "undolr_stop() failed: errno=%i\n", errno);
            log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
                LOG_DEBUG, msg_daemonname, log_buffer);
            return;
        }
		recording = 0;
		sprintf ( log_buffer, "Stopped Undo live recording");
		log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);

        e = undolr_save_async( lr_ctx, recording_file);
        if (e)
        {
            sprintf(log_buffer,
                "undolr_save_async() failed: errno=%i\n", errno);
            log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
            return;
        }
        sprintf(log_buffer, "Have created Undo live recording: %s\n", recording_file);
		log_event(PBSEVENT_ADMIN | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
    }
    sigusr1_flag = 0;
}