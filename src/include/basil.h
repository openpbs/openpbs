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
 * This file is provided as a convenience to anyone wishing to utilize
 * the Batch and Application Scheduler Interface Layer (BASIL) for the
 * Application Level Placement Scheduler (ALPS). It contains macro and
 * structure definitions that identify the elements and attributes
 * found in BASIL.
 *
 * BASIL was originally designed and coded by Michael Karo (mek@cray.com).
 *
 * BASIL has been improved and updated by contributors including:
 *  - Jason Coverston (jcovers@cray.com)
 *  - Benjamin Landsteiner (ben@cray.com)
 *
 */
/* WARNING - this file has been modified by Altair from the original
 * file provided by Cray. Please merge this file with any new basil.h
 * copies that Cray may provide.
 */

// clang-format off

#ifndef _BASIL_H
#define _BASIL_H


#ifndef __GNUC__
#define __attribute__(x) /* nothing */
#endif

#define BASIL_STRING_SHORT (16)
#define BASIL_STRING_MEDIUM (32)
#define BASIL_STRING_LONG (64)
#define BASIL_ERROR_BUFFER_SIZE (256)

#define BASIL_STRSET_SHORT(dst, src) 	snprintf(dst, BASIL_STRING_SHORT, "%s", src)
#define BASIL_BZERO_SHORT(p)		memset(p, 0, BASIL_STRING_SHORT)
#define BASIL_STRSET_MEDIUM(dst, src)	snprintf(dst, BASIL_STRING_MEDIUM, "%s", src)
#define BASIL_BZERO_MEDIUM(p) 		memset(p, 0, BASIL_STRING_MEDIUM)
#define BASIL_STRSET_LONG(dst, src)	snprintf(dst, BASIL_STRING_LONG, "%s", src)
#define BASIL_BZERO_LONG(p)		memset(p, 0, BASIL_STRING_LONG)

/*
 *	Macro Name		Text			May Appear Within
 *	==========		====			=================
 */

/* XML element names */

#define BASIL_ELM_MESSAGE	"Message"		/* All elements */
#define BASIL_ELM_REQUEST	"BasilRequest"		/* Top level */
#define BASIL_ELM_RESVPARAMARRAY "ReserveParamArray"	/* BASIL_ELM_REQUEST */
#define BASIL_ELM_RESERVEPARAM	"ReserveParam"		/* BASIL_ELM_RESVPARAMARRAY */
#define BASIL_ELM_NODEPARMARRAY "NodeParamArray"	/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ELM_NODEPARAM	"NodeParam"		/* BASIL_ELM_NODEPARMARRAY */
#define BASIL_ELM_MEMPARAMARRAY "MemoryParamArray"	/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ELM_MEMPARAM	"MemoryParam"		/* BASIL_ELM_MEMPARAMARRAY */
#define BASIL_ELM_LABELPARAMARRAY "LabelParamArray"	/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ELM_LABELPARAM	"LabelParam"		/* BASIL_ELM_LABELPARAMARRAY */

#define BASIL_ELM_RESPONSE	"BasilResponse"		/* Top level */
#define BASIL_ELM_RESPONSEDATA	"ResponseData"		/* BASIL_ELM_RESPONSE */
#define BASIL_ELM_RESERVED	"Reserved"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_CONFIRMED	"Confirmed"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_RELEASED	"Released"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_ENGINE	"Engine"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_INVENTORY	"Inventory"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_NETWORK	"Network"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_TOPOLOGY	"Topology"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_FILTARRAY	"FilterArray"		/* BASIL_ELM_TOPOLOGY */
#define BASIL_ELM_FILTER	"Filter"		/* BASIL_ELM_FILTARRAY */
#define BASIL_ELM_NODEARRAY	"NodeArray"		/* BASIL_ELM_INVENTORY */
#define BASIL_ELM_NODE		"Node"			/* BASIL_ELM_NODEARRAY */
#define BASIL_ELM_ACCELPARAMARRAY "AccelParamArray"	/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ELM_ACCELPARAM	"AccelParam"		/* BASIL_ELM_ACCELPARAMARRAY */
#define BASIL_ELM_ACCELERATORARRAY "AcceleratorArray"	/* BASIL_ELM_NODE */
#define BASIL_ELM_ACCELERATOR	"Accelerator"		/* BASIL_ELM_ACCELERATORARRAY */
							/* BASIL_ELM_ACCELSUM */
#define BASIL_ELM_ACCELERATORALLOC "AcceleratorAllocation" /* BASIL_ELM_ACCELERATOR */
#define BASIL_ELM_SOCKETARRAY	"SocketArray"		/* BASIL_ELM_NODE */
#define BASIL_ELM_SOCKET	"Socket"		/* BASIL_ELM_SOCKETARRAY */
#define BASIL_ELM_SEGMENTARRAY	"SegmentArray"		/* BASIL_ELM_SOCKET */
#define BASIL_ELM_SEGMENT	"Segment"		/* BASIL_ELM_SEGMENTARRAY */
#define BASIL_ELM_CUARRAY	"ComputeUnitArray"	/* BASIL_ELM_SEGMENT */
#define BASIL_ELM_COMPUTEUNIT	"ComputeUnit"		/* BASIL_ELM_CUARRAY */
#define BASIL_ELM_PROCESSORARRAY "ProcessorArray"	/* BASIL_ELM_SEGMENT */
							/* BASIL_ELM_COMPUTEUNIT */
#define BASIL_ELM_PROCESSOR	"Processor"		/* BASIL_ELM_PROCESSORARRAY */
#define BASIL_ELM_PROCESSORALLOC "ProcessorAllocation"	/* BASIL_ELM_PROCESSOR */
#define BASIL_ELM_MEMORYARRAY	"MemoryArray"		/* BASIL_ELM_SEGMENT */
#define BASIL_ELM_MEMORY	"Memory"		/* BASIL_ELM_MEMORYARRAY */
#define BASIL_ELM_MEMORYALLOC	"MemoryAllocation"	/* BASIL_ELM_MEMORY */
#define BASIL_ELM_LABELARRAY	"LabelArray"		/* BASIL_ELM_SEGMENT */
#define BASIL_ELM_LABEL		"Label"			/* BASIL_ELM_LABELARRAY */
#define BASIL_ELM_RSVNARRAY	"ReservationArray"	/* BASIL_ELM_INVENTORY */
							/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_RESERVATION	"Reservation"		/* BASIL_ELM_RSVNARRAY */
#define BASIL_ELM_APPARRAY	"ApplicationArray"	/* BASIL_ELM_RESERVATION */
							/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_APPLICATION	"Application"		/* BASIL_ELM_APPARRAY */
#define BASIL_ELM_CMDARRAY	"CommandArray"		/* BASIL_ELM_APPLICATION */
#define BASIL_ELM_COMMAND	"Command"		/* BASIL_ELM_CMDARRAY */
#define BASIL_ELM_RSVD_NODEARRAY "ReservedNodeArray"	/* BASIL_ELM_RESERVED */
#define BASIL_ELM_RSVD_NODE	"ReservedNode"		/* BASIL_ELM_RSVD_NODEARRAY */
#define BASIL_ELM_RSVD_SGMTARRAY "ReservedSegmentArray" /* BASIL_ELM_RSVD_NODE */
#define BASIL_ELM_RSVD_SGMT	"ReservedSegment"	/* BASIL_ELM_RSVD_SGMTARRAY */
#define BASIL_ELM_RSVD_PROCARRAY "ReservedProcessorArray"/* BASIL_ELM_RSVD_SGMT */
#define BASIL_ELM_RSVD_PROCESSOR "ReservedProcessor"	/* BASIL_ELM_RSVD_PROCARRAY */
#define BASIL_ELM_RSVD_MEMARRAY "ReservedMemoryArray"	/* BASIL_ELM_RSVD_SGMT */
#define BASIL_ELM_RSVD_MEMORY	"ReservedMemory"	/* BASIL_ELM_RSVD_MEMARRAY */
#define BASIL_ELM_SUMMARY	"Summary"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_NODESUM	"NodeSummary"		/* BASIL_ELM_SUMMARY */
#define BASIL_ELM_ACCELSUM	"AccelSummary"		/* BASIL_ELM_SUMMARY */
#define BASIL_ELM_UP		"Up"			/* BASIL_ELM_NODESUM */
							/* BASIL_ELM_ACCELSUM */
#define BASIL_ELM_DOWN		"Down"			/* BASIL_ELM_NODESUM */
							/* BASIL_ELM_ACCELSUM */
/* XML attribute names */
#define BASIL_ATR_PROTOCOL	"protocol"		/* BASIL_ELM_REQUEST */
							/* BASIL_ELM_RESPONSE */
#define BASIL_ATR_METHOD	"method"		/* BASIL_ELM_REQUEST */
							/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ATR_STATUS	"status"		/* BASIL_ELM_RESPONSEDATA */
							/* BASIL_ELM_APPLICATION */
							/* BASIL_ELM_RESERVATION */
#define BASIL_ATR_ERROR_CLASS	"error_class"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ATR_ERROR_SOURCE	"error_source"		/* BASIL_ELM_RESPONSEDATA */
#define BASIL_ATR_SEVERITY	"severity"		/* BASIL_ELM_MSG */
#define BASIL_ATR_TYPE		"type"			/* BASIL_ELM_REQUEST:query */
							/* BASIL_ELM_MEMORY */
							/* BASIL_ELM_LABEL */
							/* BASIL_ELM_ACCELERATOR */
#define BASIL_ATR_USER_NAME	"user_name"		/* BASIL_ELM_RESERVEARRAY */
							/* BASIL_ELM_RESERVATION */
#define BASIL_ATR_ACCOUNT_NAME	"account_name"		/* BASIL_ELM_RESERVEARRAY */
							/* BASIL_ELM_RESERVATION */
#define BASIL_ATR_BATCH_ID	"batch_id"		/* BASIL_ELM_RESERVEARRAY */
							/* BASIL_ELM_RESERVATION */
#define BASIL_ATR_PAGG_ID	"pagg_id"		/* BASIL_ELM_RESERVATION */
							/* BASIL_ELM_REQUEST:confirm */
							/* BASIL_ELM_REQUEST:cancel */
#define BASIL_ATR_ADMIN_COOKIE	"admin_cookie"		/* synonymous with pagg_id */
#define BASIL_ATR_ALLOC_COOKIE	"alloc_cookie"		/* deprecated as of 1.1 */
#define BASIL_ATR_CHANGECOUNT	"changecount"		/* BASIL_ELM_NODEARRAY */
#define BASIL_ATR_SCHEDCOUNT	"schedchangecount"	/* BASIL_ELM_SUMMARY */
							/* BASIL_ELM_NODEARRAY */
#define BASIL_ATR_CLAIMS	"claims"		/* BASIL_ELM_RELEASED */
#define BASIL_ATR_RSVN_ID	"reservation_id"	/* BASIL_ELM_RESERVATION */
							/* BASIL_ELM_REQUEST:confirm */
							/* BASIL_ELM_REQUEST:release */
#define BASIL_ATR_JOB_NAME	"job_name"		/* BASIL_ELM_REQUEST:confirm */
#define BASIL_ATR_NODE_ID	"node_id"		/* BASIL_ELM_NODE */
#define BASIL_ATR_ROUTER_ID	"router_id"		/* BASIL_ELM_NODE */
#define BASIL_ATR_ARCH		"architecture"		/* BASIL_ELM_RESERVE */
							/* BASIL_ELM_NODEARRAY */
							/* BASIL_ELM_NODE */
							/* BASIL_ELM_PROCESSOR */
							/* BASIL_ELM_COMMAND */
#define BASIL_ATR_ROLE		"role"			/* BASIL_ELM_NODE */
							/* BASIL_ELM_NODES */
#define BASIL_ATR_WIDTH		"width"			/* BASIL_ELM_RESERVEPARAM */
							/* BASIL_ELM_COMMAND */
#define BASIL_ATR_DEPTH		"depth"			/* BASIL_ELM_RESERVEPARAM */
							/* BASIL_ELM_COMMAND */
#define BASIL_ATR_RSVN_MODE	"reservation_mode"	/* BASIL_ELM_RESERVEPARAM */
							/* BASIL_ELM_RESERVATION */
#define BASIL_ATR_GPC_MODE	"gpc_mode"		/* BASIL_ELM_RESERVEPARAM */
							/* BASIL_ELM_RESERVATION */
#define BASIL_ATR_OSCPN		"oscpn"			/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ATR_NPPN		"nppn"			/* BASIL_ELM_RESERVEPARAM */
							/* BASIL_ELM_COMMAND */
#define BASIL_ATR_NPPS		"npps"			/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ATR_NSPN		"nspn"			/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ATR_NPPCU		"nppcu"			/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ATR_SEGMENTS	"segments"		/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ATR_SIZE_MB	"size_mb"		/* BASIL_ELM_MEMORY */
#define BASIL_ATR_NAME		"name"			/* BASIL_ELM_LABEL */
							/* BASIL_ELM_NODE */
							/* BASIL_ELM_ENGINE */
							/* BASIL_ELM_FILTER */
#define BASIL_ATR_DISPOSITION	"disposition"		/* BASIL_ELM_LABEL */
#define BASIL_ATR_STATE		"state"			/* BASIL_ELM_NODE */
							/* BASIL_ELM_ACCELERATOR */
							/* BASIL_ELM_NODES */

#define BASIL_ATR_ORDINAL	"ordinal"		/* BASIL_ELM_NODE */
							/* BASIL_ELM_SOCKET */
							/* BASIL_ELM_SEGMENT */
							/* BASIL_ELM_PROCESSOR */
							/* BASIL_ELM_ACCELERATOR */
#define BASIL_ATR_CLOCK_MHZ	"clock_mhz"		/* BASIL_ELM_SOCKET */
							/* BASIL_ELM_PROCESSOR */
							/* BASIL_ELM_ACCELERATOR */
#define BASIL_ATR_PAGE_SIZE_KB	"page_size_kb"		/* BASIL_ELM_MEMORY */
							/* BASIL_ELM_NODES */
#define BASIL_ATR_PAGE_COUNT	"page_count"		/* BASIL_ELM_MEMORY */
							/* BASIL_ELM_MEMORYALLOC */
							/* BASIL_ELM_NODES */
#define BASIL_ATR_PAGES_RSVD	"pages_rsvd"		/* BASIL_ELM_MEMORY */
#define BASIL_ATR_VERSION	"version"		/* BASIL_ELM_ENGINE */
#define BASIL_ATR_SUPPORTED	"basil_support"		/* BASIL_ELM_ENGINE */
#define BASIL_ATR_MPPHOST	"mpp_host"		/* BASIL_ELM_INVENTORY */
#define BASIL_ATR_TIMESTAMP	"timestamp"		/* BASIL_ELM_INVENTORY */
#define BASIL_ATR_APPLICATION_ID "application_id"	/* BASIL_ELM_APPLICATION */
#define BASIL_ATR_USER_ID	"user_id"		/* BASIL_ELM_APPLICATION */
#define BASIL_ATR_GROUP_ID	"group_id"		/* BASIL_ELM_APPLICATION */
#define BASIL_ATR_TIME_STAMP	"time_stamp"		/* BASIL_ELM_APPLICATION */
#define BASIL_ATR_MEMORY	"memory"		/* BASIL_ELM_COMMAND */
#define BASIL_ATR_MEMORY_MB	"memory_mb"		/* BASIL_ELM_ACCELERATOR */
#define BASIL_ATR_NODE_COUNT	"node_count"		/* BASIL_ELM_COMMAND */
#define BASIL_ATR_COMMAND	"cmd"			/* BASIL_ELM_COMMAND */
#define BASIL_ATR_SEGMENT_ID	"segment_id"		/* BASIL_ELM_RSVD_SGMT */
#define BASIL_ATR_FAMILY	"family"		/* BASIL_ELM_ACCELERATOR */
#define BASIL_ATR_ACTION	"action"		/* BASIL_ELM_APPLICATION */
							/* BASIL_ELM_RESERVATION */
#define BASIL_ATR_PGOVERNOR	"p-governor"		/* BASIL_ELM_RESERVEPARAM */
#define BASIL_ATR_PSTATE	"p-state"		/* BASIL_ELM_RESERVEPARAM */

/* XML attribute values */

#define BASIL_VAL_VERSION_1_0	"1.0"			/* BASIL_ATR_PROTOCOL 1.0 */
#define BASIL_VAL_VERSION_1_1	"1.1"			/* BASIL_ATR_PROTOCOL 1.1 */
#define BASIL_VAL_VERSION_1_2   "1.2"			/* BASIL_ATR_PROTOCOL 1.2 */
#define BASIL_VAL_VERSION_1_3   "1.3"			/* BASIL_ATR_PROTOCOL 1.3 */
#define BASIL_VAL_VERSION_1_4   "1.4"			/* BASIL_ATR_PROTOCOL 1.4 */


#define BASIL_VAL_UNDEFINED	"UNDEFINED"	/* All attributes */
#define BASIL_VAL_SUCCESS	"SUCCESS"	/* BASIL_ATR_STATUS */
#define BASIL_VAL_FAILURE	"FAILURE"	/* BASIL_ATR_STATUS */
#define BASIL_VAL_PERMANENT	"PERMANENT"	/* BASIL_ATR_ERROR_CLASS */
#define BASIL_VAL_TRANSIENT	"TRANSIENT"	/* BASIL_ATR_ERROR_CLASS */
#define BASIL_VAL_INTERNAL	"INTERNAL"	/* BASIL_ATR_ERROR_SOURCE */
#define BASIL_VAL_SYSTEM	"SYSTEM"	/* BASIL_ATR_ERROR_SOURCE */
						/* BASIL_ATR_QRY_TYPE */
#define BASIL_VAL_PARSER	"PARSER"	/* BASIL_ATR_ERROR_SOURCE */
#define BASIL_VAL_SYNTAX	"SYNTAX"	/* BASIL_ATR_ERROR_SOURCE */
#define BASIL_VAL_BACKEND	"BACKEND"	/* BASIL_ATR_ERROR_SOURCE */
#define BASIL_VAL_ERROR		"ERROR"		/* BASIL_ATR_SEVERITY */
#define BASIL_VAL_WARNING	"WARNING"	/* BASIL_ATR_SEVERITY */
#define BASIL_VAL_DEBUG		"DEBUG"		/* BASIL_ATR_SEVERITY */
#define BASIL_VAL_RESERVE	"RESERVE"	/* BASIL_ATR_METHOD */
#define BASIL_VAL_CONFIRM	"CONFIRM"	/* BASIL_ATR_METHOD */
#define BASIL_VAL_RELEASE	"RELEASE"	/* BASIL_ATR_METHOD */
#define BASIL_VAL_QUERY		"QUERY"		/* BASIL_ATR_METHOD */
#define BASIL_VAL_SWITCH	"SWITCH"	/* BASIL_ATR_METHOD */
#define BASIL_VAL_STATUS	"STATUS"	/* BASIL_ATR_QRY_TYPE */
#define BASIL_VAL_SUMMARY	"SUMMARY"	/* BASIL_ATR_QRY_TYPE */
#define BASIL_VAL_ENGINE	"ENGINE"	/* BASIL_ATR_QRY_TYPE */
#define BASIL_VAL_INVENTORY	"INVENTORY"	/* BASIL_ATR_QRY_TYPE */
#define BASIL_VAL_NETWORK	"NETWORK"	/* BASIL_ATR_QRY_TYPE */
#define BASIL_VAL_TOPOLOGY	"TOPOLOGY"	/* BASIL_ATR_QRY_TYPE */
#define BASIL_VAL_SHARED	"SHARED"	/* BASIL_ATR_MODE */
#define BASIL_VAL_EXCLUSIVE	"EXCLUSIVE"	/* BASIL_ATR_MODE */
#define BASIL_VAL_CATAMOUNT	"CATAMOUNT"	/* BASIL_ATR_OS */
#define BASIL_VAL_LINUX		"LINUX"		/* BASIL_ATR_OS */
#define BASIL_VAL_XT		"XT"		/* BASIL_ATR_ARCH:node */
#define BASIL_VAL_X2		"X2"		/* BASIL_ATR_ARCH:node */
#define BASIL_VAL_X86_64	"x86_64"	/* BASIL_ATR_ARCH:proc */
#define BASIL_VAL_AARCH64	"aarch64"	/* BASIL_ATR_ARCH:proc */
#define BASIL_VAL_CRAY_X2	"cray_x2"	/* BASIL_ATR_ARCH:proc */
#define BASIL_VAL_OS		"OS"		/* BASIL_ATR_MEM_TYPE */
#define BASIL_VAL_HUGEPAGE	"HUGEPAGE"	/* BASIL_ATR_MEM_TYPE */
#define BASIL_VAL_VIRTUAL	"VIRTUAL"	/* BASIL_ATR_MEM_TYPE */
#define BASIL_VAL_HARD		"HARD"		/* BASIL_ATR_LABEL_TYPE */
#define BASIL_VAL_SOFT		"SOFT"		/* BASIL_ATR_LABEL_TYPE */
#define BASIL_VAL_ATTRACT	"ATTRACT"	/* BASIL_ATR_LABEL_DSPN */
#define BASIL_VAL_REPEL		"REPEL"		/* BASIL_ATR_LABEL_DSPN */
#define BASIL_VAL_INTERACTIVE	"INTERACTIVE"	/* BASIL_ATR_ROLE */
#define BASIL_VAL_BATCH		"BATCH"		/* BASIL_ATR_ROLE */
#define BASIL_VAL_UP		"UP"		/* BASIL_ATR_STATE */
#define BASIL_VAL_DOWN		"DOWN"		/* BASIL_ATR_STATE */
#define BASIL_VAL_UNAVAILABLE	"UNAVAILABLE"	/* BASIL_ATR_STATE */
#define BASIL_VAL_ROUTING	"ROUTING"	/* BASIL_ATR_STATE */
#define BASIL_VAL_SUSPECT	"SUSPECT"	/* BASIL_ATR_STATE */
#define BASIL_VAL_ADMIN		"ADMIN"		/* BASIL_ATR_STATE */
#define BASIL_VAL_UNKNOWN	"UNKNOWN"	/* BASIL_ATR_STATE */
						/* BASIL_ATR_ARCH:node */
						/* BASIL_ATR_ARCH:proc */
#define BASIL_VAL_NONE		"NONE"		/* BASIL_ATR_GPC */
#define BASIL_VAL_PROCESSOR	"PROCESSOR"	/* BASIL_ATR_GPC */
#define BASIL_VAL_LOCAL		"LOCAL"		/* BASIL_ATR_GPC */
#define BASIL_VAL_GLOBAL	"GLOBAL"	/* BASIL_ATR_GPC */
#define BASIL_VAL_GPU		"GPU"		/* BASIL_ATR_TYPE */
#define BASIL_VAL_INVALID	"INVALID"	/* BASIL_ATR_STATUS */
#define BASIL_VAL_RUN		"RUN"		/* BASIL_ATR_STATUS */
#define BASIL_VAL_SUSPEND	"SUSPEND"	/* BASIL_ATR_STATUS */
#define BASIL_VAL_SWITCH	"SWITCH"	/* BASIL_ATR_STATUS */
#define BASIL_VAL_UNKNOWN	"UNKNOWN"	/* BASIL_ATR_STATUS */
#define BASIL_VAL_EMPTY		"EMPTY"		/* BASIL_ATR_STATUS */
#define BASIL_VAL_MIX		"MIX"		/* BASIL_ATR_STATUS */
#define BASIL_VAL_IN		"IN"		/* BASIL_ATR_ACTION */
#define BASIL_VAL_OUT		"OUT"		/* BASIL_ATR_ACTION */

/*
 * The following SYSTEM Query (and BASIL 1.7) specific Macro definitions have
 * been copied from the Cray-supplied basil.h header file.
 * ('Role', 'State', 'Page_Size' & 'Page_Count' related Macros already exist.
 * These attributes are common across XML Elements such as Inventory & System.)
 */
#define BASIL_ELM_SYSTEM        "System"        /* BASIL_ELM_RESPONSEDATA */
#define BASIL_ELM_NODES         "Nodes"         /* BASIL_ELM_SYSTEM */
#define BASIL_ATR_CPCU          "cpcu"          /* BASIL_ELM_SYSTEM */
#define BASIL_ATR_SPEED         "speed"         /* BASIL_ELM_NODES */
#define BASIL_ATR_NUMA_NODES    "numa_nodes"    /* BASIL_ELM_NODES */
#define BASIL_ATR_DIES          "dies"          /* BASIL_ELM_NODES */
#define BASIL_ATR_COMPUTE_UNITS "compute_units" /* BASIL_ELM_NODES */
#define BASIL_ATR_CPUS_PER_CU   "cpus_per_cu"   /* BASIL_ELM_NODES */
#define BASIL_ATR_ACCELS        "accels"        /* BASIL_ELM_NODES */
#define BASIL_ATR_ACCEL_STATE   "accel_state"   /* BASIL_ELM_NODES */
#define BASIL_ATR_NUMA_CFG      "numa_cfg"      /* BASIL_ELM_NODES */
#define BASIL_ATR_HBMSIZE       "hbm_size_mb"   /* BASIL_ELM_NODES */
#define BASIL_ATR_HBM_CFG       "hbm_cache_pct" /* BASIL_ELM_NODES */
#define BASIL_VAL_VERSION_1_7   "1.7"           /* BASIL_ATR_PROTOCOL 1.7 */
#define BASIL_VAL_VERSION       BASIL_VAL_VERSION_1_7

/*
 * The following Macro definitions have been created by Altair to support
 * SYSTEM Query processing.
 */
#define BASIL_VAL_INTERACTIVE_SYS "interactive" /* BASIL_ATR_ROLE */
#define BASIL_VAL_BATCH_SYS     "batch"		/* BASIL_ATR_ROLE */
#define BASIL_VAL_UP_SYS        "up"          	/* BASIL_ATR_STATE */
#define BASIL_VAL_DOWN_SYS      "down"        	/* BASIL_ATR_STATE */
#define BASIL_VAL_UNAVAILABLE_SYS "unavailable" /* BASIL_ATR_STATE */
#define BASIL_VAL_ROUTING_SYS   "routing"     	/* BASIL_ATR_STATE */
#define BASIL_VAL_SUSPECT_SYS   "suspect"     	/* BASIL_ATR_STATE */
#define BASIL_VAL_ADMIN_SYS     "admin"       	/* BASIL_ATR_STATE */
#define BASIL_VAL_EMPTY_SYS	""              /* BASIL_ATR_NUMA_CFG */
#define BASIL_VAL_A2A_SYS     	"a2a"           /* BASIL_ATR_NUMA_CFG */
#define BASIL_VAL_SNC2_SYS    	"snc2"          /* BASIL_ATR_NUMA_CFG */
#define BASIL_VAL_SNC4_SYS    	"snc4"          /* BASIL_ATR_NUMA_CFG */
#define BASIL_VAL_HEMI_SYS    	"hemi"          /* BASIL_ATR_NUMA_CFG */
#define BASIL_VAL_QUAD_SYS    	"quad"          /* BASIL_ATR_NUMA_CFG */
#define BASIL_VAL_0_SYS       	"0"             /* BASIL_ATR_HBM_CFG */
#define BASIL_VAL_25_SYS      	"25"            /* BASIL_ATR_HBM_CFG */
#define BASIL_VAL_50_SYS      	"50"            /* BASIL_ATR_HBM_CFG */
#define BASIL_VAL_100_SYS     	"100"           /* BASIL_ATR_HBM_CFG */

/* if set, the specified env var is the href (i.e., url) of an xslt file */
#define BASIL_XSLT_HREF_ENV	"BASIL_XSLT_HREF"

/*
 * BASIL versions.
 * To add a new version, define the BASIL_VAL_VERSION_#_# string, above,
 * then place it at the top of the supported_versions array.
 * Define a numeric version value in the enum, below.
 * Add the strcmp to match the string to the enum value in
 * request_start() in handlers.c
 */

/* BASIL supported versions string array */

/* The first version listed is considered the current version. */
static const char *basil_supported_versions[] __attribute__((unused)) = {
	BASIL_VAL_VERSION_1_7,
	BASIL_VAL_VERSION_1_4,
	BASIL_VAL_VERSION_1_3,
	BASIL_VAL_VERSION_1_2,
	BASIL_VAL_VERSION_1_1,
	BASIL_VAL_VERSION_1_0,
	NULL
};

/*
 * BASIL versions -- numerical
 */
typedef enum {
	basil_1_0 = 10,
	basil_1_1,
	basil_1_2,
	basil_1_3,
	basil_1_4,
	/* basil_1_5 and basil_1_6 are not supported */
	basil_1_7 = 17
} basil_version_t;

/*
 * For conversion from enum to string array index
 * always make BASIL_VERSION_MAX the current, largest version
 * number from the basil_version_t enum.
 */
#define BASIL_VERSION_MAX basil_1_7
#define BASIL_VERSION_MIN basil_1_0

/* BASIL enumerated types */

typedef enum {
	basil_method_none = 0,
	basil_method_reserve,
	basil_method_confirm,
	basil_method_release,
	basil_method_query,
	basil_method_switch
} basil_method_t;

typedef enum {
	basil_query_none = 0,
	basil_query_engine,
	basil_query_inventory,
	basil_query_network,
	basil_query_status,
	basil_query_summary,
	basil_query_system,
	basil_query_topology
} basil_query_t;

typedef enum {
	basil_node_arch_none = 0,
	basil_node_arch_x2,
	basil_node_arch_xt,
	basil_node_arch_unknown
} basil_node_arch_t;

typedef enum {
	basil_node_state_none = 0,
	basil_node_state_up,
	basil_node_state_down,
	basil_node_state_unavail,
	basil_node_state_route,
	basil_node_state_suspect,
	basil_node_state_admindown,
	basil_node_state_unknown
} basil_node_state_t;

typedef enum {
	basil_node_role_none = 0,
	basil_node_role_interactive,
	basil_node_role_batch,
	basil_node_role_unknown
} basil_node_role_t;

typedef enum {
	basil_accel_none = 0,
	basil_accel_gpu
} basil_accel_t;

typedef enum {
	basil_accel_state_none = 0,
	basil_accel_state_up,
	basil_accel_state_down,
	basil_accel_state_unknown
} basil_accel_state_t;

typedef enum {
	basil_processor_arch_none = 0,
	basil_processor_cray_x2,
	basil_processor_x86_64,
	basil_processor_aarch64,
	basil_processor_arch_unknown
} basil_processor_arch_t;

typedef enum {
	basil_memory_type_none = 0,
	basil_memory_type_os,
	basil_memory_type_hugepage,
	basil_memory_type_virtual
} basil_memory_type_t;

typedef enum {
	basil_label_type_none = 0,
	basil_label_type_hard,
	basil_label_type_soft
} basil_label_type_t;

typedef enum {
	basil_label_disposition_none = 0,
	basil_label_disposition_attract,
	basil_label_disposition_repel
} basil_label_disposition_t;

typedef enum {
	basil_component_state_none = 0,
	basil_component_state_available,
	basil_component_state_unavailable
} basil_component_state_t;

typedef enum {
	basil_rsvn_mode_none = 0,
	basil_rsvn_mode_exclusive,
	basil_rsvn_mode_shared
} basil_rsvn_mode_t;

typedef enum {
	basil_gpc_mode_none = 0,
	basil_gpc_mode_processor,
	basil_gpc_mode_local,
	basil_gpc_mode_global
} basil_gpc_mode_t;

typedef enum {
	basil_application_status_none = 0,
	basil_application_status_invalid,
	basil_application_status_run,
	basil_application_status_suspend,
	basil_application_status_switch,
	basil_application_status_unknown
} basil_application_status_t;

typedef enum {
	basil_reservation_status_none = 0,
	basil_reservation_status_empty,
	basil_reservation_status_invalid,
	basil_reservation_status_mix,
	basil_reservation_status_run,
	basil_reservation_status_suspend,
	basil_reservation_status_switch,
	basil_reservation_status_unknown
} basil_reservation_status_t;

typedef enum {
	basil_switch_action_none = 0,
	basil_switch_action_in,
	basil_switch_action_out,
	basil_switch_action_unknown
} basil_switch_action_t;

typedef enum {
	basil_switch_status_none = 0,
	basil_switch_status_success,
	basil_switch_status_failure,
	basil_switch_status_invalid,
	basil_switch_status_unknown
} basil_switch_status_t;

/* Basil data structures common to requests and responses */

typedef struct basil_label {
	char name[BASIL_STRING_MEDIUM];
	basil_label_type_t type;
	basil_label_disposition_t disposition;
	struct basil_label *next;
} basil_label_t;

typedef basil_label_t basil_label_param_t;

typedef struct basil_accelerator_gpu {
	char *family;
	unsigned int memory;
	unsigned int clock_mhz;
} basil_accelerator_gpu_t;

/* BASIL request data structures */

typedef struct basil_accelerator_param {
	basil_accel_t type;
	basil_accel_state_t state;
	union {
		basil_accelerator_gpu_t *gpu;
	} data;
	struct basil_accelerator_param *next;
} basil_accelerator_param_t;

typedef struct basil_memory_param {
	long size_mb;
	basil_memory_type_t type;
	struct basil_memory_param *next;
} basil_memory_param_t;

typedef struct basil_nodelist_param {
	char *nodelist;
	struct basil_nodelist_param *next;
} basil_nodelist_param_t;

typedef struct basil_reserve_param {
	basil_node_arch_t arch;
	long width;
	long depth;
	long oscpn;
	long nppn;
	long npps;
	long nspn;
	long nppcu;
	long pstate;
	char pgovernor[BASIL_STRING_SHORT];
	basil_rsvn_mode_t rsvn_mode;
	basil_gpc_mode_t gpc_mode;
	char segments[BASIL_STRING_MEDIUM];
	basil_memory_param_t *memory;
	basil_label_param_t *labels;
	basil_nodelist_param_t *nodelists;
	basil_accelerator_param_t *accelerators;
	struct basil_reserve_param *next;
} basil_reserve_param_t;

typedef struct basil_request_reserve {
	char user_name[BASIL_STRING_MEDIUM];
	char account_name[BASIL_STRING_MEDIUM];
	char batch_id[BASIL_STRING_LONG];
	long rsvn_id;	/* debug only */
	basil_reserve_param_t *params;
} basil_request_reserve_t;

typedef struct basil_request_confirm {
	long rsvn_id;
	unsigned long long pagg_id;
	char job_name[BASIL_STRING_LONG];
} basil_request_confirm_t;

typedef struct basil_request_release {
	long rsvn_id;
	unsigned long long pagg_id;
} basil_request_release_t;

typedef struct basil_request_query_inventory {
	unsigned long long changecount;
	int doNodeArray;
	int doResvArray;
} basil_request_query_inventory_t;

typedef struct basil_request_query_status_app {
	unsigned long long apid;
	struct basil_request_query_status_app *next;
} basil_request_query_status_app_t;

typedef struct basil_request_query_status_res {
	long rsvn_id;
	struct basil_request_query_status_res *next;
} basil_request_query_status_res_t;

typedef struct basil_request_query_status {
	int doAppArray;
	basil_request_query_status_app_t *application;
	int doResvArray;
	basil_request_query_status_res_t *reservation;
} basil_request_query_status_t;

/*
 * Copied this System Query specific (BASIL 1.7) structure definition
 * (basil_request_query_system_t) from the Cray-supplied basil.h file.
 */
typedef struct basil_request_query_system {
    unsigned long long changecount;
} basil_request_query_system_t;

typedef struct basil_topology_filter {
	char name[BASIL_STRING_LONG];
	struct basil_topology_filter *next;
} basil_topology_filter_t;

typedef struct basil_request_query_topology {
	int executeFilters;
	basil_topology_filter_t *filters;
} basil_request_query_topology_t;

typedef struct basil_request_query {
	basil_query_t type;
	union {
		basil_request_query_inventory_t *inv;
		basil_request_query_status_t *status;
		basil_request_query_system_t *system;
		basil_request_query_topology_t *topology;
	} data;
} basil_request_query_t;

typedef struct basil_request_switch_app {
	unsigned long long apid;
	basil_switch_action_t action;
	struct basil_request_switch_app *next;
} basil_request_switch_app_t;

typedef struct basil_request_switch_res {
	long rsvn_id;
	basil_switch_action_t action;
	struct basil_request_switch_res *next;
} basil_request_switch_res_t;

typedef struct basil_request_switch {
	basil_request_switch_app_t *application;
	basil_request_switch_res_t *reservation;
} basil_request_switch_t;

typedef struct basil_request {
	basil_version_t protocol;
	basil_method_t method;
	union {
		basil_request_reserve_t reserve;
		basil_request_confirm_t confirm;
		basil_request_release_t release;
		basil_request_switch_t swtch;
		basil_request_query_t query;
	} data;
} basil_request_t;

/* BASIL response data structures */

typedef struct basil_rsvn_application_cmd {
	int width;
	int depth;
	int nppn;
	int memory;
	basil_node_arch_t arch;
	char cmd[BASIL_STRING_MEDIUM];
	struct basil_rsvn_application_cmd *next;
} basil_rsvn_application_cmd_t;

typedef struct basil_rsvn_application {
	unsigned long long application_id;
	unsigned int user_id;
	unsigned int group_id;
	char time_stamp[BASIL_STRING_MEDIUM];
	basil_rsvn_application_cmd_t *cmds;
	struct basil_rsvn_application *next;
} basil_rsvn_application_t;

typedef struct basil_rsvn {
	long rsvn_id;
	char user_name[BASIL_STRING_MEDIUM];
	char account_name[BASIL_STRING_MEDIUM];
	char batch_id[BASIL_STRING_LONG];
	char time_stamp[BASIL_STRING_MEDIUM];
	char rsvn_mode[BASIL_STRING_MEDIUM];
	char gpc_mode[BASIL_STRING_MEDIUM];
	basil_rsvn_application_t *applications;
	struct basil_rsvn *next;
} basil_rsvn_t;

typedef struct basil_memory_allocation {
	long rsvn_id;
	long page_count;
	struct basil_memory_allocation *next;
} basil_memory_allocation_t;

typedef struct basil_node_memory {
	basil_memory_type_t type;
	long page_size_kb;
	long page_count;
	basil_memory_allocation_t *allocations;
	struct basil_node_memory *next;
} basil_node_memory_t;

typedef struct basil_node_computeunit {
	int ordinal;
	int proc_per_cu_count;
	struct basil_node_computeunit *next;
} basil_node_computeunit_t;

typedef struct basil_processor_allocation {
	long rsvn_id;
	struct basil_processor_allocation *next;
} basil_processor_allocation_t;

typedef struct basil_node_processor {
	int ordinal;
	basil_processor_arch_t arch;
	int clock_mhz;
	basil_processor_allocation_t *allocations;
	struct basil_node_processor *next;
} basil_node_processor_t;

typedef struct basil_node_segment {
	int ordinal;
	basil_node_processor_t *processors;
	basil_node_memory_t *memory;
	basil_label_t *labels;
	basil_node_computeunit_t *computeunits;
	struct basil_node_segment *next;
} basil_node_segment_t;

typedef struct basil_node_socket {
	int ordinal;
	basil_processor_arch_t arch;
	int clock_mhz;
	basil_node_segment_t *segments;
	struct basil_node_socket *next;
} basil_node_socket_t;

typedef struct basil_accelerator_allocation {
	long rsvn_id;
	struct basil_accelerator_allocation *next;
} basil_accelerator_allocation_t;

typedef struct basil_node_accelerator {
	basil_accel_t type;
	basil_accel_state_t state;
	union {
		basil_accelerator_gpu_t *gpu;
	} data;
	basil_accelerator_allocation_t *allocations;
	struct basil_node_accelerator *next;
} basil_node_accelerator_t;

typedef struct basil_node {
	long node_id;
	long router_id;
	basil_node_arch_t arch;
	basil_node_state_t state;
	basil_node_role_t role;
	unsigned int numcpus;	/* numcores */
	long clock_mhz;
	char name[BASIL_STRING_SHORT];
	basil_node_socket_t *sockets;
	basil_node_segment_t *segments;
	basil_node_accelerator_t *accelerators;
	struct basil_node *next;
} basil_node_t;

typedef struct basil_response_query_inventory {
	long long timestamp;
	char mpp_host[BASIL_STRING_LONG];
	int node_count;
	int node_maxid;
	unsigned long long int changecount;
	unsigned long long int schedcount;
	basil_node_t *nodes;
	int rsvn_count;
	basil_rsvn_t *rsvns;
} basil_response_query_inventory_t;

typedef struct basil_response_query_engine {
	char *name;
	char *version;
	char *basil_support;
} basil_response_query_engine_t;

typedef struct basil_response_query_network {
} basil_response_query_network_t;

typedef struct basil_response_query_status_app {
	unsigned long long apid;
	basil_application_status_t status;
	struct basil_response_query_status_app *next;
} basil_response_query_status_app_t;

typedef struct basil_response_query_status_res {
	long rsvn_id;
	basil_reservation_status_t status;
	struct basil_response_query_status_res *next;
} basil_response_query_status_res_t;

typedef struct basil_response_query_status {
	basil_response_query_status_app_t *application;
	basil_response_query_status_res_t *reservation;
} basil_response_query_status_t;

/*
 * Selectively copied System Query specific (BASIL 1.7) structure definitions
 * (basil_system_element_t, basil_response_query_system_t) from the cray
 * supplied basil.h file.
 */
typedef struct basil_system_element {
    char role[BASIL_STRING_SHORT];
    char state[BASIL_STRING_SHORT];
    char speed[BASIL_STRING_SHORT];
    char numa_nodes[BASIL_STRING_SHORT];
    char n_dies[BASIL_STRING_SHORT];
    char compute_units[BASIL_STRING_SHORT];
    char cpus_per_cu[BASIL_STRING_SHORT];
    char pgszl2[BASIL_STRING_SHORT];
    char avlmem[BASIL_STRING_SHORT];
    char accel_name[BASIL_STRING_SHORT];
    char accel_state[BASIL_STRING_SHORT];
    char numa_cfg[BASIL_STRING_SHORT];
    char hbmsize[BASIL_STRING_SHORT];
    char hbm_cfg[BASIL_STRING_SHORT];
    char *nidlist;
    struct basil_system_element *next;
} basil_system_element_t;

typedef struct basil_response_query_system {
    long long timestamp;
    char mpp_host[BASIL_STRING_LONG];
    int cpcu_val;
    basil_system_element_t *elements;
} basil_response_query_system_t;

typedef struct basil_response_query_topology {
	int executeFilters;
	basil_topology_filter_t *filters;
} basil_response_query_topology_t;

typedef struct basil_response_query {
	basil_query_t type;
	union {
		basil_response_query_inventory_t inventory;
		basil_response_query_engine_t engine;
		basil_response_query_network_t network;
		basil_response_query_status_t status;
		basil_response_query_system_t system;
		basil_response_query_topology_t topology;
	} data;
} basil_response_query_t;

typedef struct basil_response_reserve {
	long rsvn_id;
	basil_node_t **nodes;
	int *nids;
	size_t nidslen;
	/* CPA admin_cookie deprecated as of 1.1 */
	/* CPA alloc_cookie deprecated as of 1.1 */
} basil_response_reserve_t;

typedef struct basil_response_confirm {
	long rsvn_id;
	unsigned long long pagg_id;
} basil_response_confirm_t;

typedef struct basil_response_release {
	long rsvn_id;
	unsigned int claims;
} basil_response_release_t;

typedef struct basil_response_switch_app {
	unsigned long long apid;
	basil_switch_status_t status;
	struct basil_response_switch_app *next;
} basil_response_switch_app_t;

typedef struct basil_response_switch_res {
	long rsvn_id;
	basil_switch_status_t status;
	struct basil_response_switch_res *next;
} basil_response_switch_res_t;

typedef struct basil_response_switch {
	basil_response_switch_app_t *application;
	basil_response_switch_res_t *reservation;
} basil_response_switch_t;

typedef struct basil_response {
	basil_version_t protocol;
	basil_method_t method;
	unsigned long error_flags;
	char error[BASIL_ERROR_BUFFER_SIZE];
	union {
		basil_response_reserve_t reserve;
		basil_response_confirm_t confirm;
		basil_response_release_t release;
		basil_response_query_t query;
		basil_response_switch_t swtch;
	} data;
} basil_response_t;

/*
 * Bit assignments for error_flags define in basil_response_t for
 * use in callback functions.
 */
#define BASIL_ERR_TRANSIENT	0x00000001UL

#endif /* _BASIL_H */

// clang-format on

