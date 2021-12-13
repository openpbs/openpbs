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
 **	Common resource names for dependent code.  All machines
 **	supported by the resource monitor should include at least
 **	these resources.
 */

static char *cput(struct rm_attribute *attrib);
#ifndef WIN32
static char *mem(struct rm_attribute *attrib);
static char *sessions(struct rm_attribute *attrib);
static char *pids(struct rm_attribute *attrib);
static char *nsessions(struct rm_attribute *attrib);
static char *nusers(struct rm_attribute *attrib);
#endif
static char *size(struct rm_attribute *attrib);
extern char *idletime(struct rm_attribute *attrib);

extern char *nullproc(struct rm_attribute *attrib);

struct config standard_config[] = {
	{"cput", {cput}},
#ifndef WIN32
	{"mem", {mem}},
	{"sessions", {sessions}},
	{"pids", {pids}},
	{"nsessions", {nsessions}},
	{"nusers", {nusers}},
#endif
	{"size", {size}},
	{"idletime", {idletime}},
	{NULL, {nullproc}},
};
