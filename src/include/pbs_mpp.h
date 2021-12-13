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

#ifndef _PBS_MPP_H
#define _PBS_MPP_H
#ifdef __cplusplus
extern "C" {
#endif

/*
 *	Header file for defining MPP CPU states and scheduling restrictions.
 */

#define MPP_MAX_CPUS_PER_NODE 16
#define MPP_MAX_APPS_PER_CPU 16

typedef enum {
	mpp_node_arch_none = 0,
	mpp_node_arch_Cray_XT3,
	mpp_node_arch_Cray_X1,
	mpp_node_arch_Cray_X2,
	mpp_node_arch_max
} mpp_node_arch_t;

static char *mpp_node_arch_name[] = {
	"NONE",
	"XT3",
	"X1",
	"X2",
	"UNKNOWN"};

typedef enum {
	mpp_node_state_none = 0,
	mpp_node_state_avail,
	mpp_node_state_unavail,
	mpp_node_state_down,
	mpp_node_state_max
} mpp_node_state_t;

static char *mpp_node_state_name[] = {
	"NONE",
	"AVAILABLE",
	"UNAVAILABLE",
	"DOWN",
	"UNKNOWN"};

typedef enum {
	mpp_cpu_type_none = 0,
	mpp_cpu_type_x86_64,
	mpp_cpu_type_Cray_X1,
	mpp_cpu_type_Cray_X2,
	mpp_cpu_type_max
} mpp_cpu_type_t;

static char *mpp_cpu_type_name[] = {
	"NONE",
	"x86_64",
	"craynv1",
	"Cray-BlackWidow",
	"UNKNOWN"};

typedef enum {
	mpp_cpu_state_none = 0,
	mpp_cpu_state_up,
	mpp_cpu_state_down,
	mpp_cpu_state_max
} mpp_cpu_state_t;

static char *mpp_cpu_state_name[] = {
	"NONE",
	"UP",
	"DOWN",
	"UNKNOWN"};

typedef enum {
	mpp_label_type_hard = 0,
	mpp_label_type_soft
} mpp_label_type_t;

#ifdef __cplusplus
}
#endif
#endif /* _PBS_MPP_H */
