/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
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

#include <stddef.h>

int
sec_set_fdcon(int fd)
{
	return 0;
}

void *
sec_open_session(char *user)
{
	/* return value cannot be NULL as it denotes error */
	static int i;

	return &i;
}

void
sec_close_session(void *ctx)
{
	return;
}

int
sec_set_net_conn(void *ctx)
{
	return(0);
}

int
sec_get_net_conn(void *ctx)
{
	return(0);
}

int
sec_set_filecon(char *path, void *ucred)
{
	return 0;
}

void
sec_free_con(void *ctx)
{
	return;
}

int
sec_get_con(void *ctx)
{
	ctx = NULL;
	return 0;
}

int
sec_reset_fscon()
{
	return 0;
}

int
sec_set_exec_con(void *ctx)
{
	return 0;
}

void
sec_set_context(void **sec_con, char *attr)
{
	return;
}

int
sec_should_impersonate()
{
	return 0;
}

void
sec_revert_con(void *ctx)
{
	return;
}
