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



/*
 **	Header file defineing the datatypes and library visiable
 **	variables for paralell awareness.
 */

#ifndef _TM__H
#define _TM__H

#include	<sys/types.h>

typedef int		tm_host_id;	/* physical node index  */
typedef int		tm_node_id;	/* job-relative node id */
#define TM_ERROR_NODE	((tm_node_id)-1)

typedef int		tm_event_t;	/* event handle, > 0 for real events */
#define TM_NULL_EVENT	((tm_event_t)0)
#define TM_ERROR_EVENT	((tm_event_t)-1)

typedef unsigned int	tm_task_id;
#define TM_NULL_TASK	(tm_task_id)0
#define TM_INIT_TASK	(tm_task_id)1

/*
 **	Protocol message type defines
 */
#define	TM_INIT		100	/* tm_init request	*/
#define TM_TASKS	101	/* tm_taskinfo request	*/
#define	TM_SPAWN	102	/* tm_spawn request	*/
#define	TM_SIGNAL	103	/* tm_signal request	*/
#define	TM_OBIT		104	/* tm_obit request	*/
#define TM_RESOURCES	105	/* tm_rescinfo request	*/
#define TM_POSTINFO	106	/* tm_publish request	*/
#define TM_GETINFO	107	/* tm_subscribe request	*/
#define	TM_GETTID	108	/* tm_gettasks request */
#define	TM_REGISTER	109	/* tm_register request	*/
#define	TM_RECONFIG	110	/* tm_register deferred reply */
#define	TM_ACK		111	/* tm_register event acknowledge */
#define TM_FINALIZE	112	/* tm_finalize request, there is no reply */
#define TM_ATTACH	113	/* tm_attach request */
#define TM_SPAWN_MULTI	114	/* tm_spawn_multi request */
#define TM_OKAY		  0


#define	TM_ERROR	999

/*
 **	Error numbers returned from library
 */
#define TM_SUCCESS		0
#define	TM_ESYSTEM		17000
#define	TM_ENOEVENT		17001
#define	TM_ENOTCONNECTED	17002
#define	TM_EUNKNOWNCMD		17003
#define	TM_ENOTIMPLEMENTED	17004
#define	TM_EBADENVIRONMENT	17005
#define	TM_ENOTFOUND		17006
#define	TM_BADINIT		17007
#define	TM_ESESSION		17008
#define	TM_EUSER		17009
#define	TM_EOWNER		17010
#define	TM_ENOPROC		17011
#define	TM_EHOOK		17012

#define	TM_TODO_NOP	5000	/* Do nothing (the nodes value may be new) */
#define	TM_TODO_CKPT	5001	/* Checkpoint <what> and continue it */
#define	TM_TODO_MOVE	5002	/* Move <what> to <where> */
#define	TM_TODO_QUIT	5003	/* Terminate <what> */
#define	TM_TODO_STOP	5004	/* Suspend execution of <what> */

#endif	/* _TM__H */
