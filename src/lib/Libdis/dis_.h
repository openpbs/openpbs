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

#include <limits.h>
#include <stddef.h>

#include <dis.h>

#define DIS_BUFSIZ (CHAR_BIT * sizeof(ULONG_MAX))
/* define a limit for the number of times DIS will recurse when      */
/* processing a sequence of character counts;  prvent stack overflow */
#define DIS_RECURSIVE_LIMIT 30

char *discui_(char *cp, unsigned value, unsigned *ndigs);
char *discul_(char *cp, unsigned long value, unsigned *ndigs);
char *discull_(char *cp, u_Long value, unsigned *ndigs);
void disi10d_();
void disi10l_();
void disiui_(void);
void dis_init_tables(void); /* called once per process to init dis tables */
void init_ulmax(void);
double disp10d_(int expon);
dis_long_double_t disp10l_(int expon);
int
disrl_(int stream, dis_long_double_t *ldval, unsigned *ndigs,
       unsigned *nskips, unsigned sigd, unsigned count, int recursv);
int disrsi_(int stream, int *negate, unsigned *value, unsigned count, int rescuvr);
int
disrsl_(int stream, int *negate, unsigned long *value,
	unsigned long count, int recursv);
int disrsll_(int stream, int *negate, u_Long *value, unsigned long count, int recursv);
int diswui_(int stream, unsigned value);

extern unsigned dis_dmx10;
extern double *dis_dp10;
extern double *dis_dn10;

extern unsigned dis_lmx10;
extern dis_long_double_t *dis_lp10;
extern dis_long_double_t *dis_ln10;

extern char *__dis_buffer_location(void);
#define dis_buffer (__dis_buffer_location())

extern char *dis_umax;
extern unsigned dis_umaxd;
