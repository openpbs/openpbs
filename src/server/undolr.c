#include <signal.h>
#include <string.h>
#include <unistd.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>
#include "log.h"
#include "undolr.h"


int sigusr1_flag = 0;

static int recording = 0;
static char* save_filename;


/* TODO doxygen */
void readfilename() 
{
    /* TODO: read filename from pbs.conf */
    save_filename = strdup("/opt/recording.undo");
}

/* TODO doxygen */
void undolr()
{
	int e = 0;
	undolr_error_t  err;
	undolr_recording_context_t lr_ctx; /*TODO can assaign NULL ?*/

    readfilename();

	if (!recording)
	{
        sprintf(log_buffer,
				"recording turning on");
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);

		e = undolr_start(&err);
		if (e)
		{
			sprintf(log_buffer,
             "undolr_recording_start() failed: error=%i errno=%i\n", e, errno);
            log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
		}

		e = undolr_save_on_termination(save_filename);
		if (e)
		{
			sprintf(log_buffer,
                "undolr_save_on_termination() failed: error=%i errno=%i\n", e, errno);
            log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
		}

		recording = 1;

	} else 
	{
        /* Stop an Undo Recording of our execution to this point. */

		sprintf ( log_buffer, "recording turnning off");
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);

        sprintf(log_buffer, "Saving Undo Recording to: %s\n", save_filename);
        log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
            LOG_DEBUG, msg_daemonname, log_buffer);
        e = undolr_stop (&lr_ctx);
        if (e)
        {
            sprintf(log_buffer, "undolr_stop() failed: errno=%i\n", errno);
            log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
                LOG_DEBUG, msg_daemonname, log_buffer);
        }
		recording = 0;
        e = undolr_save_async( lr_ctx, save_filename);
        if (e)
        {
            sprintf(log_buffer,
                "undolr_save_async() failed: errno=%i\n", errno);
            log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
        }
        sprintf(log_buffer, "Have created Undo Recording: %s\n", save_filename);
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
				LOG_DEBUG, msg_daemonname, log_buffer);
    }
    sigusr1_flag = 0;
}