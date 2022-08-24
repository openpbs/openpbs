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
 * @file	alps.c
 * @brief
 * Cray ALPS related functionality.
 * The functions in this file are responsible for parsing the XML response
 * from the ALPS BASIL client (either catnip or apbasil). These functions
 * rely on the expat XML parsing engine, and require libexpat to be linked
 * with the binary. The expat library is commonly installed with all Linux
 * distributions, but the developer may choose to link the library statically
 * to eliminate the potential for version mismatch or lack of availability.
 * The 64 bit version of the static library is currently less that 256KB in
 * size, so the overhead of static linking is minimal.
 *
 * The Batch and Application Scheduling Interface Layer (BASIL) utilizes
 * the extensible markup language (XML) for input and output. A brief
 * description of XML may be found on Wikipedia at
 * http://en.wikipedia.org/wiki/XML
 *
 * A nice description of Expat can be found at:
 * http://www.xml.com/pub/a/1999/09/expat/index.html
 *
 * We are primarily concerned with XML elements and attributes. Perhaps
 * the easiest way to think of these structures is in relation to their
 * HTML counterparts. Both document types are heirarchical in nature and
 * are built upon a set of elements that may each contain attributes.
 * Descriptions of each element and its associated attributes may be
 * found in the basil.h header file.
 */

#include "pbs_config.h"

#if MOM_ALPS /* Defined when --enable-alps is passed to configure. */

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <ctype.h>
#include <fcntl.h>
#include <errno.h>
#include <expat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <stdarg.h>
#include <pwd.h>
#include <assert.h>

#ifndef _XOPEN_SOURCE
extern pid_t getsid(pid_t);
#endif /* _XOPEN_SOURCE */

#include "pbs_error.h"
#include "list_link.h"
#include "server_limits.h"
#include "attribute.h"
#include "resource.h"
#include "job.h"
#include "log.h"
#include "mom_func.h"
#include "basil.h"
#include "placementsets.h"
#include "mom_server.h"
#include "mom_vnode.h"
#include "resmon.h"
#include "hwloc.h"

/**
 * Remember the PBScrayhost (mpphost) reported by ALPS.
 * Utilized during Inventory query procession for Compute nodes.
 */
char mpphost[BASIL_STRING_LONG];

/*
 * Data types to support interaction with the Cray ALPS implementation.
 */

extern char *alps_client;
extern int vnode_per_numa_node;
extern char *ret_string;
extern vnl_t *vnlp;

/**
 * Define a sane BASIL stack limit.
 * This specifies the how many levels deep the BASIL can go.
 * Need to increase this for each XML level indentation addition.
 */
#define MAX_BASIL_STACK (16)

/**
 * Maintain counts on elements that are limited to one instance per context.
 * These counters help keep track of the XML structure that is imposed
 * by ALPS. The counter is checked to be sure they are not nested or
 * get jumbled in any way.
 */
typedef struct element_counts {
	int response;
	int response_data;
	int reserved;
	int confirmed;
	int released;
	int inventory;
	int node_array;
	int socket_array;
	int segment_array;
	int processor_array;
	int memory_array;
	int label_array;
	int reservation_array;
	int application_array;
	int command_array;
	int accelerator_array;
	int computeunit_array;
/*
	The following entries are not needed now because we are just
	ignoring the corresponding XML tags. If they become nesessary
	in the future, here they are.
*/
#if 0
	int reserved_node_array;
	int reserved_segment_array;
	int reserved_processor_array;
	int reserved_memory_array;
#endif
} element_counts_t;

/**
 * This is for the SYSTEM Query XML Response.
 * Maintain counts on elements that are limited to one instance per context.
 * These counters are checked to ensure that the XML Response is not nested/
 * jumbled in any way.
 */
typedef struct element_counts_sys {
	int response;
	int response_data;
	int system;
} element_counts_sys_t;

/**
 * Pointers for node data used when parsing inventory.
 * These provide a place to hang lists of any possible result from an
 * ALPS inventory. Additionally, counters for node states are kept here.
 */
typedef struct inventory_data {
	basil_node_t *node;
	basil_node_socket_t *socket;
	basil_node_segment_t *segment;
	basil_node_processor_t *processor;
	basil_processor_allocation_t *processor_allocation;
	basil_node_memory_t *memory;
	basil_memory_allocation_t *memory_allocation;
	basil_label_t *label;
	basil_rsvn_t *reservation;
	basil_node_computeunit_t *cu;
	int role_int;
	int role_batch;
	int role_unknown;
	int state_up;
	int state_down;
	int state_unavail;
	int state_routing;
	int state_suspect;
	int state_admin;
	int state_unknown;
	basil_node_accelerator_t *accelerator;
	basil_accelerator_allocation_t *accelerator_allocation;
	int accel_type_gpu;
	int accel_type_unknown;
	int accel_state_up;
	int accel_state_down;
	int accel_state_unknown;
	int socket_count;
} inventory_data_t;

/**
 * Pointer to System <Nodes> data used when parsing System response.
 * This structure is expected to grow as/when we implement more of
 * the BASIL 1.7 features.
 */
typedef struct system_data {
	basil_system_element_t *node_group;
} system_data_t;

/**
 * The user data structure for expat.
 */
typedef struct ud {
	int depth;
	int stack[MAX_BASIL_STACK + 1];
	char status[BASIL_STRING_SHORT];
	char message[BASIL_ERROR_BUFFER_SIZE];
	char type[BASIL_STRING_SHORT];
	char basil_ver[BASIL_STRING_SHORT];
	char error_class[BASIL_STRING_SHORT];
	char error_source[BASIL_STRING_SHORT];
	element_counts_t count;
	element_counts_sys_t count_sys;
	inventory_data_t current;
	system_data_t current_sys;
	basil_response_t *brp;
} ud_t;

/**
 * Pointer to a response structure (that gets filled in with KNL Node information).
 */
static basil_response_t *brp_knl;

/**
 * List of all KNL Nodes extracted from the System (BASIL 1.7) XML Response.
 */
static char *knl_node_list;

/**
 * Function pointers to XML handler functions.
 * @param element string giving the XML tag
 * @param start function to call when the tag is seen
 * @param end function to call when the XML segment is finished
 * @param char_data character handler for the given XML segment
 */
typedef struct element_handler {
	char *element;
	void (*start)(ud_t *, const XML_Char *, const XML_Char **);
	void (*end)(ud_t *, const XML_Char *);
	void (*char_data)(ud_t *, const XML_Char *, int);
} element_handler_t;

static XML_Parser parser;
static element_handler_t handler[];

#define EXPAT_BUFFER_LEN (65536)
static char expatBuffer[(EXPAT_BUFFER_LEN * sizeof(char))];
static char *basil_inventory;
static char *alps_client_out;

static char *requestBuffer;
static char *requestBuffer_knl;
static size_t requestSize_knl;
static size_t requestCurr = 0;
static size_t requestSize = 0;

#define UTIL_BUFFER_LEN (4096)
static char utilBuffer[(UTIL_BUFFER_LEN * sizeof(char))];

#define VNODE_NAME_LEN 255

#define BASIL_ERR_ID "BASIL"

/**
 * Flag set to true when talking to Basil 1.1 original.
 */
static int basil11orig = 0;

/**
 * Variables that keep track of which basil version to speak.
 * The Inventory Query speaks BASIL 1.4 (stored in basilversion_inventory) and
 * the System Query speaks BASIL 1.7 (stored in basilversion_system).
 */
static char basilversion_inventory[BASIL_STRING_SHORT];
static char basilversion_system[BASIL_STRING_SHORT];

/**
 * Flag to indicate BASIL 1.7 support.
 */
static int basil_1_7_supported;

/**
 * Variable that keeps track of the numeric value related to the basil version.
 * It is used to do specific validation per basil version.
 */
static basil_version_t basilver = 0;

/**
 * Versions of BASIL that PBS supports.
 * It is a smaller subset that what ALPS likely provides in
 * basil_supported_versions.
 * PBS no longer supports version 1.0.
 * As ALPS adds BASIL versions, once PBS supports them, they should
 * be added here.
 */
static const char *pbs_supported_basil_versions[] __attribute__((unused)) = {
	BASIL_VAL_VERSION_1_4,
	BASIL_VAL_VERSION_1_3,
	BASIL_VAL_VERSION_1_2,
	BASIL_VAL_VERSION_1_1,
	NULL};

static int first_compute_node = 1;

/**
 * String to use for mpp_host in vnode names when basil11orig
 * is true.
 */
#define FAKE_MPP_HOST "default"

/**
 * Prototype declarations for System Query (KNL) related functions.
 */
static int init_KNL_alps_req_buf(void);
static void create_vnodes_KNL(basil_response_query_system_t *);
static int exclude_from_KNL_processing(basil_system_element_t *,
				       short int check_state);
static long *process_nodelist_KNL(char *, int *);
static void store_nids(int, char *, long **, int *);
static void free_basil_elements_KNL(basil_system_element_t *);
static void alps_engine_query_KNL(void);

/**
 * @brief
 *	When DEBUG is defined, log XML parsing messages to MOM log file.
 *
 * @param[in] fmt - format of msg
 *
 * @return Void
 */
static void
xml_dbg(char *fmt, ...)
{
#ifdef DEBUG
	va_list argp;
	va_start(argp, fmt);
	vsnprintf(log_buffer, sizeof(log_buffer), fmt, argp);
	va_end(argp);
	log_event(PBSEVENT_DEBUG2, 0, LOG_DEBUG, BASIL_ERR_ID, log_buffer);
#endif /* DEBUG */
	return;
}

/**
 * @brief
 * 	Start a new ALPS request.
 * 	If need be, allocate a buffer. Set the start point requestCurr to 0.
 *
 * @return Void
 *
 */
static void
new_alps_req(void)
{
	if (requestBuffer == NULL) {
		requestSize = UTIL_BUFFER_LEN;
		requestBuffer = malloc(UTIL_BUFFER_LEN);
	}
	assert(requestBuffer != NULL);
	requestCurr = 0;
}

/**
 * @brief
 * Start a new ALPS request for KNL.
 *
 * If need be, allocate a buffer.
 * @retval 1 if buffer allocation failed.
 * @retval 0 if success.
 */
static int
init_KNL_alps_req_buf(void)
{
	if (requestBuffer_knl == NULL) {
		requestSize_knl = UTIL_BUFFER_LEN;
		if ((requestBuffer_knl = (char *) malloc(UTIL_BUFFER_LEN)) == NULL) {
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_ERR, __func__,
				  "Memory allocation for XML request buffer failed.");
			return 1;
		}
	}
	return 0;
}

/**
 * @brief
 * 	Add new text to current ALPS request.
 *
 * 	If need be, extend the buffer. Copy the new text into the buffer
 * 	and set the start point requestCurr to follow the added text.
 *
 * @param[in] new - text to add
 *
 * @return Void
 *
 */
static void
add_alps_req(char *new)
{
	size_t len = strlen(new);

	if (requestCurr + len >= requestSize) {
		size_t num = (UTIL_BUFFER_LEN + len) / UTIL_BUFFER_LEN;
		requestSize += num * UTIL_BUFFER_LEN;
		requestBuffer = realloc(requestBuffer, requestSize);
		assert(requestBuffer != NULL);
	}
	strcpy(&requestBuffer[requestCurr], new);
	requestCurr += len;
}

/**
 * @brief
 * 	When an internal parse error is encountered, set the source, class,
 * 	and message pointers in the expat user data structure.
 *
 * @param d - pointer to user data structure
 *
 * @return Void
 *
 */
static void
parse_err_internal(ud_t *d)
{
	snprintf(d->message, sizeof(d->message), "Internal error.");
	sprintf(d->error_source, "%s", BASIL_VAL_INTERNAL);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When an out of memory error is encountered, set the source, class,
 *	and message pointers in the expat user data structure.
 *
 * @param[in] d - pointer to user data structure
 *
 * @return Void
 *
 */
static void
parse_err_out_of_memory(ud_t *d)
{
	snprintf(d->message, sizeof(d->message), "Out of memory.");
	sprintf(d->error_source, "%s", BASIL_VAL_SYSTEM);
	sprintf(d->error_class, "%s", BASIL_VAL_TRANSIENT);
	return;
}

/**
 * @brief
 * 	When a stack depth error is encountered, set the source, class,
 * 	and message pointers in the expat user data structure.
 *
 * @param[in] d - pointer to user data structure
 *
 * @return Void
 *
 */
static void
parse_err_stack_depth(ud_t *d)
{
	snprintf(d->message, sizeof(d->message), "Stack too deep.");
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When an invalid XML element is encountered, set the source, class,
 * 	and message pointers in the expat user data structure.
 *
 * @param[in] d - pointer to user data structure
 *
 * @return Void
 *
 */
static void
parse_err_illegal_start(ud_t *d)
{
	char *el = handler[d->stack[d->depth]].element;

	snprintf(d->message, sizeof(d->message),
		 "Illegal element: %s", el);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When a single XML element is expected, but multiple instances are
 * 	encountered, set the source, class, and message pointers in the
 * 	expat user data structure.
 *
 * param[in] d - pointer to user data structure
 *
 * @return Void
 *
 */

static void
parse_err_multiple_elements(ud_t *d)
{
	char *el = handler[d->stack[d->depth]].element;

	snprintf(d->message, sizeof(d->message),
		 "Multiple instances of element: %s", el);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When an unsupported BASIL version is encountered, set the source, class,
 * 	and message pointers in the expat user data structure.
 *
 * @param d pointer to user data structure
 * @param[in] remote version string from the XML
 * @param[in] local version define from 'basil.h' (BASIL_VAL_VERSION)
 *
 * @retval Void
 *
 */
static void
parse_err_version_mismatch(ud_t *d, const char *remote, const char *local)
{
	snprintf(d->message, sizeof(d->message),
		 "BASIL version mismatch: us=%s, them=%s", local, remote);
	sprintf(d->error_source, "%s", BASIL_VAL_BACKEND);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When an XML attribute is required but not specified, set the source,
 * 	class, and message pointers in the expat user data structure.
 *
 * @param d pointer to user data structure
 * @param[in] attr name of the unspecified attribute
 *
 * @retval Void
 *
 */
static void
parse_err_unspecified_attr(ud_t *d, const char *attr)
{
	snprintf(d->message, sizeof(d->message),
		 "Unspecified attribute: %s", attr);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When a single XML attribute is expected, but multiple instances are
 * 	encountered, set the source, class, and message pointers in the
 * 	expat user data structure.
 * 	Most fields are initialized to zero so a non-zero value means a repeat
 * 	has taken place.
 *
 * @param[in] d pointer to user data structure
 * @param[in] attr name of the repeated attribute
 *
 * @retval Void
 *
 */
static void
parse_err_multiple_attrs(ud_t *d, const char *attr)
{
	snprintf(d->message, sizeof(d->message),
		 "Multiple attribute instances: %s", attr);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When an unrecognized XML attribute is specified within an element, set
 * 	the source, class, and message pointers in the expat user data structure.
 *
 * @param[in] d pointer to user data structure
 * @param[in] attr name of the unrecognized attribute
 *
 * @return Void
 *
 */
static void
parse_err_unrecognized_attr(ud_t *d, const char *attr)
{
	snprintf(d->message, sizeof(d->message),
		 "Unrecognized attribute: %s", attr);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When an illegal value is assigned to an attribute within an element, set
 * 	the source, class, and message pointers in the expat user data structure.
 *
 * @param[in] d pointer to user data structure
 * @param[in] name name of the attribute
 * @param[in] value bad value
 *
 * @retval Void
 *
 */
static void
parse_err_illegal_attr_val(ud_t *d, const char *name, const char *value)
{
	snprintf(d->message, sizeof(d->message),
		 "Illegal attribute assignment: %s = %s", name, value);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When illegal characters are encountered within the XML data, set the
 * 	source, class, and message pointers in the expat user data structure.
 *
 * @param[in] d pointer to user data structure
 * @param[in] s string with bad characters
 *
 * @retval Void
 *
 */
static void
parse_err_illegal_char_data(ud_t *d, const char *s)
{
	snprintf(d->message, sizeof(d->message),
		 "Illegal character data: %s", s);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * 	When the end of the XML data is encountered prematurely, set the
 * 	source, class, and message pointers in the expat user data structure.
 *
 * @param[in] d pointer to user data structure
 * @param[in] el name of bad end element
 *
 * @retval Void
 *
 */
static void
parse_err_illegal_end(ud_t *d, const char *el)
{
	snprintf(d->message, sizeof(d->message),
		 "Illegal end of element: %s", el);
	sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
	sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
	return;
}

/**
 * @brief
 * This function enforces the structure of the XML elements. Since
 * messages can occur in any element, they are not part of the check.
 *
 * Check that the depth is okay then look at the top element. Make
 * sure that what comes before the top is legal in the XML structure
 * we are parsing.
 *
 * @return int
 * @retval 1 if XML structure is incorrect
 * @retval 0 okay
 *
 */
static int
stack_busted(ud_t *d)
{
	char *top;
	char *prev;
	basil_response_t *brp;

	if (!d) {
		parse_err_internal(NULL);
		return (1);
	}
	brp = d->brp;
	if (d->depth < 1 || d->depth >= MAX_BASIL_STACK) {
		parse_err_stack_depth(d);
		return (1);
	} else if (d->depth == 1) {
		top = handler[d->stack[d->depth]].element;
		if (strcmp(BASIL_ELM_RESPONSE, top) != 0) {
			parse_err_illegal_start(d);
			return (1);
		}
	} else {
		top = handler[d->stack[d->depth]].element;
		prev = handler[d->stack[(d->depth - 1)]].element;
		if (strcmp(BASIL_ELM_RESPONSE, top) == 0) {
			parse_err_illegal_start(d);
			return (1);
		} else if (strcmp(BASIL_ELM_RESPONSEDATA, top) == 0) {
			if (strcmp(BASIL_ELM_RESPONSE, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RESERVED, top) == 0) {
			if (strcmp(BASIL_ELM_RESPONSEDATA, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
			if (brp->method != basil_method_reserve) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_CONFIRMED, top) == 0) {
			if (strcmp(BASIL_ELM_RESPONSEDATA, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
			if (brp->method != basil_method_confirm) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RELEASED, top) == 0) {
			if (strcmp(BASIL_ELM_RESPONSEDATA, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
			if (brp->method != basil_method_release) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_INVENTORY, top) == 0) {
			if (strcmp(BASIL_ELM_RESPONSEDATA, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
			if (brp->method != basil_method_query) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_NODEARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_INVENTORY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
			if (brp->data.query.type != basil_query_inventory) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_NODE, top) == 0) {
			if (strcmp(BASIL_ELM_NODEARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_SOCKETARRAY, top) == 0) {
			/* socket XML was introduced in BASIL 1.3*/
			if (strcmp(BASIL_ELM_NODE, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_SOCKET, top) == 0) {
			if (strcmp(BASIL_ELM_SOCKETARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_SEGMENTARRAY, top) == 0) {
			switch (basilver) {
				case basil_1_0:
				case basil_1_1:
				case basil_1_2:
					if (strcmp(BASIL_ELM_NODE, prev) != 0) {
						parse_err_illegal_start(d);
						return (1);
					}
					break;
				case basil_1_3:
				case basil_1_4:
				case basil_1_7:
					if (strcmp(BASIL_ELM_SOCKET, prev) != 0) {
						parse_err_illegal_start(d);
						return (1);
					}
					break;
			}
		} else if (strcmp(BASIL_ELM_SEGMENT, top) == 0) {
			if (strcmp(BASIL_ELM_SEGMENTARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_CUARRAY, top) == 0) {
			/* ComputeUnit Array XML was introduced in BASIL 1.3*/
			if (strcmp(BASIL_ELM_SEGMENT, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_COMPUTEUNIT, top) == 0) {
			/* Compute Unit XML was introduced in BASIL 1.3*/
			if (strcmp(BASIL_ELM_CUARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_PROCESSORARRAY, top) == 0) {
			switch (basilver) {
				case basil_1_0:
				case basil_1_1:
				case basil_1_2:
					if (strcmp(BASIL_ELM_SEGMENT, prev) != 0) {
						parse_err_illegal_start(d);
						return (1);
					}
					break;
				case basil_1_3:
				case basil_1_4:
				case basil_1_7:
					if (strcmp(BASIL_ELM_COMPUTEUNIT, prev) != 0) {
						parse_err_illegal_start(d);
						return (1);
					}
					break;
			}
		} else if (strcmp(BASIL_ELM_PROCESSOR, top) == 0) {
			if (strcmp(BASIL_ELM_PROCESSORARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_PROCESSORALLOC, top) == 0) {
			if (strcmp(BASIL_ELM_PROCESSOR, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_MEMORYARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_SEGMENT, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_MEMORY, top) == 0) {
			if (strcmp(BASIL_ELM_MEMORYARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_MEMORYALLOC, top) == 0) {
			if (strcmp(BASIL_ELM_MEMORY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_LABELARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_SEGMENT, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_LABEL, top) == 0) {
			if (strcmp(BASIL_ELM_LABELARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVNARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_INVENTORY, prev) != 0) {
				if (strcmp(BASIL_ELM_RESPONSEDATA, prev) != 0) {
					parse_err_illegal_start(d);
					return (1);
				}
			}
		} else if (strcmp(BASIL_ELM_RESERVATION, top) == 0) {
			if (strcmp(BASIL_ELM_RSVNARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_APPARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_RESERVATION, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_APPLICATION, top) == 0) {
			if (strcmp(BASIL_ELM_APPARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_CMDARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_APPLICATION, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_COMMAND, top) == 0) {
			if (strcmp(BASIL_ELM_CMDARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_ACCELERATORARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_NODE, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_ACCELERATOR, top) == 0) {
			if (strcmp(BASIL_ELM_ACCELERATORARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_ACCELERATORALLOC, top) == 0) {
			if (strcmp(BASIL_ELM_ACCELERATOR, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_NODEARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_RESERVED, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_NODE, top) == 0) {
			if (strcmp(BASIL_ELM_RSVD_NODEARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_SGMTARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_RESERVED, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_SGMT, top) == 0) {
			if (strcmp(BASIL_ELM_RSVD_SGMTARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_PROCARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_RESERVED, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_PROCESSOR, top) == 0) {
			if (strcmp(BASIL_ELM_RSVD_PROCARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_MEMARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_RESERVED, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_RSVD_MEMORY, top) == 0) {
			if (strcmp(BASIL_ELM_RSVD_MEMARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		}
	}
	return (0);
}

/**
 * @brief
 * 	This function is registered to handle the start of the BASIL response.
 * 	Checks the stack (depth should be 1) and the protocol version. The
 * 	protocol version is defined in basil.h and will be updated whenever
 * 	the BASIL document format changes. Cray will provide a new basil.h
 * 	when this occurs.
 *
 *
 * The standard Expat start handler function prototype is used.
 * @param[in] d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 *
 */
static void
response_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	char protocol[BASIL_STRING_SHORT];

	if (stack_busted(d))
		return;
	if (++(d->count.response) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	protocol[0] = '\0';
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_PROTOCOL, *np) == 0) {
			BASIL_STRSET_SHORT(protocol, *vp);
			if ((strcmp(BASIL_VAL_VERSION_1_7, *vp) != 0) &&
			    (strcmp(BASIL_VAL_VERSION_1_4, *vp) != 0) &&
			    (strcmp(BASIL_VAL_VERSION_1_3, *vp) != 0) &&
			    (strcmp(BASIL_VAL_VERSION_1_2, *vp) != 0) &&
			    (strcmp(BASIL_VAL_VERSION_1_1, *vp) != 0)) {
				parse_err_version_mismatch(d, *vp, d->basil_ver);
				return;
			}
		}
	}
	if (protocol[0] == '\0') {
		parse_err_unspecified_attr(d, BASIL_ATR_PROTOCOL);
		return;
	}
}

/**
 * @brief
 * 	This funtion is registered to handle the start of the BASIL data.
 * 	It checks to make sure there is a valid method type so we know
 * 	what elements to expect later on.
 *
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param[in] d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 *
 */
static void
response_data_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_response_t *brp;

	if (stack_busted(d))
		return;
	brp = d->brp;
	if (++(d->count.response_data) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_METHOD, *np) == 0) {
			if (brp->method != basil_method_none) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_RESERVE, *vp) == 0) {
				brp->method = basil_method_reserve;
				brp->data.reserve.rsvn_id = -1;
			} else if (strcmp(BASIL_VAL_CONFIRM, *vp) == 0) {
				brp->method = basil_method_confirm;
			} else if (strcmp(BASIL_VAL_RELEASE, *vp) == 0) {
				brp->method = basil_method_release;
				brp->data.release.claims = 0;
			} else if (strcmp(BASIL_VAL_QUERY, *vp) == 0) {
				brp->method = basil_method_query;
				/*
				 * Set type to status, for the switch status
				 * response. The other types can get set in
				 * inventory_start and engine_start.
				 */
				brp->data.query.type = basil_query_status;
			} else if (strcmp(BASIL_VAL_SWITCH, *vp) == 0) {
				brp->method = basil_method_switch;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_STATUS, *np) == 0) {
			pbs_strncpy(d->status, *vp, sizeof(d->status));
			if (strcmp(BASIL_VAL_SUCCESS, *vp) == 0) {
				*brp->error = '\0';
			} else if (strcmp(BASIL_VAL_FAILURE, *vp) == 0) {
				/* do nothing here, brp->error was set */
				/* in alps_request_parent              */
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_ERROR_CLASS, *np) == 0) {
			pbs_strncpy(d->error_class, *vp, sizeof(d->error_class));
			/*
			 * The existence of a PERMENENT error used to
			 * reset the BASIL_ERR_TRANSIENT flag. This
			 * is no longer done since the error_flags
			 * field is initialized to zero.
			 */
			if (strcmp(BASIL_VAL_TRANSIENT, *vp) == 0) {
				brp->error_flags |= (BASIL_ERR_TRANSIENT);
			} else if (strcmp(BASIL_VAL_PERMANENT, *vp) != 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_ERROR_SOURCE, *np) == 0) {
			pbs_strncpy(d->error_source, *vp, sizeof(d->error_source));
			/*
			 * Consider "BACKEND" errors TRANSIENT when trying
			 * to create an ALPS reservation.
			 * It was found that a node being changed from
			 * batch to interactive would cause a PERMANENT,
			 * BACKEND error when a job was run on it. We
			 * want this to not result in the job being deleted.
			 */
			if (brp->method == basil_method_reserve) {
				if (strcmp(BASIL_VAL_BACKEND, *vp) == 0) {
					brp->error_flags |= (BASIL_ERR_TRANSIENT);
				}
			}
		} else if (strcmp(BASIL_ATR_TYPE, *np) == 0) {
			pbs_strncpy(d->type, *vp, sizeof(d->type));
			if ((strcmp(BASIL_VAL_SYSTEM, *vp) != 0) &&
			    (strcmp(BASIL_VAL_ENGINE, *vp) != 0)) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}

	if (brp->method == basil_method_none) {
		parse_err_unspecified_attr(d, BASIL_ATR_METHOD);
		return;
	}
	if (*d->status == '\0') {
		parse_err_unspecified_attr(d, BASIL_ATR_STATUS);
		return;
	}
}

/**
 * @brief
 * 	This funtion is registered to handle BASIL message elements. Message
 * 	elements may appear anywhere in the XML, and may be selectively
 * 	ignored. Each message must have a severity defined as an attribute.
 *
 * 	The standard Expat start handler function prototype is used.
 *
 * @param[in] d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 */
static void
message_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	*d->message = '\0';
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_SEVERITY, *np) == 0) {
			if (strcmp(BASIL_VAL_DEBUG, *vp) == 0) {
				strcat(d->message, BASIL_VAL_DEBUG ": ");
			} else if (strcmp(BASIL_VAL_WARNING, *vp) == 0) {
				strcat(d->message, BASIL_VAL_WARNING ": ");
			} else if (strcmp(BASIL_VAL_ERROR, *vp) == 0) {
				strcat(d->message, BASIL_VAL_ERROR ": ");
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (*d->message == '\0') {
		parse_err_unspecified_attr(d, BASIL_ATR_SEVERITY);
		return;
	}
	return;
}

/**
 * @brief
 * 	This function digests the text component of the message element and
 * 	updates the message pointer in the user data structure.
 *
 * The standard Expat character handler function prototype is used.
 *
 * @param[in] d pointer to user data structure
 * @param[in] s string
 * @param[in] len length of string
 *
 * @retval Void
 *
 */
static void
message_char_data(ud_t *d, const XML_Char *s, int len)
{
	strncat(d->message, s, len);
}

/**
 * @brief
 * 	This function handles the end of a BASIL message element by logging
 * 	the message to the MOM log file.
 *
 * 	The standard Expat end handler function prototype is used.
 *
 * @param[in] d pointer to user data structure
 * @param[in] el name of end element
 *
 * @retval Void\
 *
 */
static void
message_end(ud_t *d, const XML_Char *el)
{
	if (strcmp(el, handler[d->stack[d->depth]].element) != 0)
		parse_err_illegal_end(d, el);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  BASIL_ERR_ID, d->message);
	return;
}

/**
 * @brief
 * 	This function is registered to handle the reserved element in
 * 	response to a reservation creation request.
 *
 * Change from basil 1.0: admin_cookie is renamed to pagg_id
 * and alloc_cookie is deprecated as of 1.1.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param[in] d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 *
 */
static void
reserved_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_response_t *brp;

	if (stack_busted(d))
		return;
	if (++(d->count.reserved) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	brp = d->brp;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			brp->data.reserve.rsvn_id = strtol(*vp, NULL, 10);
		} else if (!basil11orig) {
			/*
			 * Basil 1.1+ doesn't have any other elements
			 * but Basil 1.1 orig has dummy entries for
			 * "admin_cookie" and "alloc_cookie". Just
			 * ignore them.
			 */
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	/* rsvn_id is initialized to -1 so this catches the unset case. */
	if (brp->data.reserve.rsvn_id < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_RSVN_ID);
		return;
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the confirmed element in
 * 	response to a reservation confirmation request.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 *
 */
static void
confirmed_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.confirmed) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		/*
		 * These keywords do not need to be saved. The CONFIRM
		 * reply is just sending back the same values given in
		 * the CONFIRM request.
		 */
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
		} else if (strcmp(BASIL_ATR_PAGG_ID, *np) == 0) {
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
		}
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the released element in
 * 	response to a reservation release request.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 *
 */
static void
released_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_response_t *brp;

	if (stack_busted(d))
		return;
	if (++(d->count.released) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	brp = d->brp;

	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		/*
		 * This keyword does not need to be saved. The
		 * RELEASE reply is just sending back the same value
		 * given in the RELEASE request.
		 */
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
		} else if (strcmp(BASIL_ATR_CLAIMS, *np) == 0) {
			brp->data.release.claims = strtol(*vp, NULL, 10);
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the engine element in
 * 	response to an engine request.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 *
 */
static void
engine_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_response_t *brp;
	basil_response_query_engine_t *eng;
	int len = 0;

	if (stack_busted(d))
		return;

	brp = d->brp;
	brp->data.query.type = basil_query_engine;
	eng = &brp->data.query.data.engine;

	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		if (strcmp(BASIL_ATR_NAME, *np) == 0) {
			/* This keyword does not have to be saved */
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
		} else if (strcmp(BASIL_ATR_VERSION, *np) == 0) {
			/* We will need this in alps_engine_query */
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
			if (eng->version) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			len = strlen(*vp) + 1;
			eng->version = malloc(len);
			if (!eng->version) {
				parse_err_out_of_memory(d);
				return;
			}
			snprintf(eng->version, len, "%s", *vp);
		} else if (strcmp(BASIL_ATR_SUPPORTED, *np) == 0) {
			/* Save this for use in alps_engine_query */
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
			if (eng->basil_support) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			len = strlen(*vp) + 1;
			eng->basil_support = malloc(len);
			if (!eng->basil_support) {
				parse_err_out_of_memory(d);
				return;
			}
			snprintf(eng->basil_support, len, "%s", *vp);
		}
	}
	if (!eng->version) {
		parse_err_unspecified_attr(d, BASIL_ATR_VERSION);
		return;
	}
	if (!eng->basil_support) {
		parse_err_unspecified_attr(d, BASIL_ATR_SUPPORTED);
		return;
	}
}

/**
 * @brief
 * 	This function is registered to handle the inventory element in
 * 	response to an inventory request.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
inventory_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_response_t *brp;
	basil_response_query_inventory_t *inv;

	if (stack_busted(d))
		return;
	if (++(d->count.inventory) > 1) {
		parse_err_multiple_elements(d);
		return;
	}

	brp = d->brp;
	brp->data.query.type = basil_query_inventory;
	inv = &brp->data.query.data.inventory;

	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_TIMESTAMP, *np) == 0) {
			if (inv->timestamp != 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			inv->timestamp = atoll(*vp);
		} else if (strcmp(BASIL_ATR_MPPHOST, *np) == 0) {
			if (inv->mpp_host[0] != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(&inv->mpp_host[0],
				 BASIL_STRING_LONG, "%s", *vp);
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}

	/*
	 * The mpp_host and timestamp fields will be filled in
	 * for BASIL_VAL_VERSION_1_1 "plus" and higher. There is no other
	 * way to tell BASIL_VAL_VERSION_1_1 from 1.1+.
	 */
	if (inv->timestamp == 0) {
		inv->timestamp = time(NULL);
		basil11orig = 1;
	}
	if (inv->mpp_host[0] == '\0') {
		pbs_strncpy(inv->mpp_host, FAKE_MPP_HOST, sizeof(inv->mpp_host));
		basil11orig = 1;
	}

	d->count.node_array = 0;
	d->count.reservation_array = 0;
	d->count.accelerator_array = 0;
	d->count.socket_array = 0;
	d->count.segment_array = 0;
	d->count.computeunit_array = 0;

	/* set interesting counts to zero */
	d->current.role_int = 0;
	d->current.role_batch = 0;
	d->current.role_unknown = 0;
	d->current.state_up = 0;
	d->current.state_down = 0;
	d->current.state_unavail = 0;
	d->current.state_routing = 0;
	d->current.state_suspect = 0;
	d->current.state_admin = 0;
	d->current.state_unknown = 0;
	d->current.accel_type_gpu = 0;
	d->current.accel_type_unknown = 0;
	d->current.accel_state_up = 0;
	d->current.accel_state_down = 0;
	d->current.accel_state_unknown = 0;
	d->current.socket_count = 0;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the node array element within
 * 	an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void]
 *
 */
static void
node_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.node_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_CHANGECOUNT, *np) == 0) {
			/*
			 * Currently unused.
			 * We could save changecount if we ever started
			 * requesting inventory more frequently.
			 * changecount could help reduce the amount of data
			 * returned if the inventory has not changed.
			 */
		} else if (strcmp(BASIL_ATR_SCHEDCOUNT, *np) == 0) {
			/*
			 * Currently unused.
			 */
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	d->current.node = NULL;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the node element within an
 * 	inventory response.
 *
 * Due to the new response format introduced in BASIL 1.3, and
 * continuing in BASIL 1.4, the count for different arrays need to be
 * reset at different places.
 * For example, since BASIL 1.1 and BASIL 1.2 have segments but no sockets
 * we need to reset the segment_array as part of node_start, however in
 * BASIL 1.3 and 1.4 segment_array count will be reset in socket_start.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @retval Void
 *
 */
static void
node_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_t *node;
	basil_response_t *brp;

	if (stack_busted(d))
		return;
	brp = d->brp;
	node = malloc(sizeof(basil_node_t));
	if (!node) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(node, 0, sizeof(basil_node_t));
	node->node_id = -1;
	if (d->current.node) {
		(d->current.node)->next = node;
	} else {
		brp->data.query.data.inventory.nodes = node;
	}
	d->current.node = node;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_NODE_ID, *np) == 0) {
			if (node->node_id >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			node->node_id = atol(*vp);
			if (node->node_id < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_ROUTER_ID, *np) == 0) {
			if (node->router_id > 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			node->router_id = atol(*vp);
			if (*vp <= 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_NAME, *np) == 0) {
			if (*node->name) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(node->name, BASIL_STRING_SHORT, "%s", *vp);
		} else if (strcmp(BASIL_ATR_ARCH, *np) == 0) {
			if (node->arch) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_XT, *vp) == 0) {
				node->arch = basil_node_arch_xt;
			} else if (strcmp(BASIL_VAL_X2, *vp) == 0) {
				node->arch = basil_node_arch_x2;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_ROLE, *np) == 0) {
			if (node->role) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_INTERACTIVE, *vp) == 0) {
				d->current.role_int++;
				node->role = basil_node_role_interactive;
			} else if (strcmp(BASIL_VAL_BATCH, *vp) == 0) {
				d->current.role_batch++;
				node->role = basil_node_role_batch;
			} else {
				d->current.role_unknown++;
				node->role = basil_node_role_unknown;
			}
		} else if (strcmp(BASIL_ATR_STATE, *np) == 0) {
			if (node->state) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_UP, *vp) == 0) {
				d->current.state_up++;
				node->state = basil_node_state_up;
			} else if (strcmp(BASIL_VAL_DOWN, *vp) == 0) {
				d->current.state_down++;
				node->state = basil_node_state_down;
			} else if (strcmp(BASIL_VAL_UNAVAILABLE, *vp) == 0) {
				d->current.state_unavail++;
				node->state = basil_node_state_unavail;
			} else if (strcmp(BASIL_VAL_ROUTING, *vp) == 0) {
				d->current.state_routing++;
				node->state = basil_node_state_route;
			} else if (strcmp(BASIL_VAL_SUSPECT, *vp) == 0) {
				d->current.state_suspect++;
				node->state = basil_node_state_suspect;
			} else if (strcmp(BASIL_VAL_ADMIN, *vp) == 0) {
				d->current.state_admin++;
				node->state = basil_node_state_admindown;
			} else {
				d->current.state_unknown++;
				node->state = basil_node_state_unknown;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (node->node_id < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_NODE_ID);
		return;
	}
	if (*node->name == '\0') {
		parse_err_unspecified_attr(d, BASIL_ATR_NAME);
		return;
	}
	if (!node->role) {
		parse_err_unspecified_attr(d, BASIL_ATR_ROLE);
		return;
	}
	if (!node->state) {
		parse_err_unspecified_attr(d, BASIL_ATR_STATE);
		return;
	}
	/* Reset the array counters. */
	switch (basilver) {
		case basil_1_0:
		case basil_1_1:
		case basil_1_2:
			d->count.segment_array = 0;
			break;
		case basil_1_3:
		case basil_1_4:
		case basil_1_7:
			/* segment_array is reset in socket_start() for these
			 * BASIL versions.
			 */
			break;
	}
	d->count.socket_array = 0;
	d->count.accelerator_array = 0;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the segment array element
 * 	within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 * @retval Void
 *
 */
static void
socket_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.socket_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.socket = NULL;
	return;
}

/**
 * @brief
 *	 This function is registered to handle the socket element within an inventory response.
 * Starting with BASIL 1.3 the socket array has the architecture and clock_mhz of the processors.
 * However, this information is not used by PBS.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
socket_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_socket_t *socket;

	if (stack_busted(d))
		return;
	socket = malloc(sizeof(basil_node_socket_t));
	if (!socket) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(socket, 0, sizeof(basil_node_socket_t));
	socket->ordinal = -1;
	socket->clock_mhz = -1;
	if (d->current.socket) {
		(d->current.socket)->next = socket;
	} else {
		if (!d->current.node) {
			parse_err_internal(d);
			free(socket);
			return;
		}
		(d->current.node)->sockets = socket;
	}
	d->current.socket = socket;

	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_ORDINAL, *np) == 0) {
			if (socket->ordinal >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			socket->ordinal = atoi(*vp);
			if (socket->ordinal < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_ARCH, *np) == 0) {
			if (socket->arch) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_X86_64, *vp) == 0) {
				socket->arch = basil_processor_x86_64;
			} else if (strcmp(BASIL_VAL_CRAY_X2, *vp) == 0) {
				socket->arch = basil_processor_cray_x2;
			} else if (strcmp(BASIL_VAL_AARCH64, *vp) == 0) {
				socket->arch = basil_processor_aarch64;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_CLOCK_MHZ, *np) == 0) {
			if (socket->clock_mhz >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			socket->clock_mhz = atoi(*vp);
			if (socket->clock_mhz < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}

	if (socket->ordinal < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_ORDINAL);
		return;
	}
	if (!socket->arch) {
		parse_err_unspecified_attr(d, BASIL_ATR_ARCH);
		return;
	}
	if (socket->clock_mhz < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_CLOCK_MHZ);
		return;
	}
	/* Increase the socket count */
	d->current.socket_count++;

	/* Reset the array counters and segment */
	d->count.segment_array = 0;
	d->current.segment = NULL;

	return;
}

/**
 * @brief
 *	This function is registered to handle the segment array element
 * within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
segment_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.segment_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	if (!d->current.socket)
		d->current.segment = NULL;
	return;
}

/**
 * @brief
 *	This function is registered to handle the segment element within an
 * inventory response.
 *
 * Due to the new XML format introduced in BASIL 1.3, and
 * continuing in BASIL 1.4, the count for different arrays need to be
 * reset at different places.
 * For example, since BASIL 1.1 and BASIL 1.2 have no compute units we don't
 * need to reset the count here. Also for BASIL 1.1 and 1.2, the processor
 * count will be reset in processor_array_start.
 * For BASIL 1.3 and BASIL 1.4 we need to reset the count for compute unit
 * arrays here.
 *
 * The standard Expat start handler function prototype is used.
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
segment_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_segment_t *segment;

	if (stack_busted(d))
		return;
	segment = malloc(sizeof(basil_node_segment_t));
	if (!segment) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(segment, 0, sizeof(basil_node_segment_t));
	segment->ordinal = -1;
	if (d->current.segment) {
		(d->current.segment)->next = segment;
	} else {
		if (!d->current.node) {
			parse_err_internal(d);
			free(segment);
			return;
		}
		switch (basilver) {
			case basil_1_0:
			case basil_1_1:
			case basil_1_2:
				/* There are no socket elements. */
				(d->current.node)->segments = segment;
				break;
			case basil_1_3:
			case basil_1_4:
			case basil_1_7:
				(d->current.socket)->segments = segment;
				break;
		}
	}
	d->current.segment = segment;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_ORDINAL, *np) == 0) {
			if (segment->ordinal >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			segment->ordinal = atol(*vp);
			if (segment->ordinal < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (segment->ordinal < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_ORDINAL);
		return;
	}
	/* Reset the array counters. */
	switch (basilver) {
		case basil_1_0:
		case basil_1_1:
		case basil_1_2:
			/* There are no compute units, and the processor
			 * count was initialized as part of processor_array_start()
			 */
			break;
		case basil_1_3:
		case basil_1_4:
		case basil_1_7:
			d->count.computeunit_array = 0;
			d->current.processor = NULL;
			break;
	}
	d->count.processor_array = 0;
	d->count.memory_array = 0;
	d->count.label_array = 0;
	return;
}

/**
 * @brief
 *	This function is registered to handle the computeunit array element
 * within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 */
static void
computeunit_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.computeunit_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.cu = NULL;
	return;
}

/**
 * @brief
 *	This function is registered to handle the computeunit element within an
 * inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
computeunit_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_computeunit_t *cu;

	if (stack_busted(d))
		return;
	cu = malloc(sizeof(basil_node_computeunit_t));
	if (!cu) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(cu, 0, sizeof(basil_node_computeunit_t));
	cu->ordinal = -1;
	cu->proc_per_cu_count = 0;

	if (d->current.cu) {
		(d->current.cu)->next = cu;
	} else {
		if (!d->current.segment) {
			parse_err_internal(d);
			free(cu);
			return;
		}
		(d->current.segment)->computeunits = cu;
	}
	d->current.cu = cu;

	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_ORDINAL, *np) == 0) {
			if (cu->ordinal >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			cu->ordinal = atol(*vp);
			if (cu->ordinal < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (cu->ordinal < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_ORDINAL);
		return;
	}
	/* Reset the array counter */
	d->count.processor_array = 0;
}

/**
 * @brief
 *	This function is registered to handle the processor array element
 * within an inventory response.
 *
 * Due to the new response format introduced in BASIL 1.3, and
 * continuing in BASIL 1.4, the count for different arrays need to be
 * reset at different times.
 * For example, for BASIL 1.1 and 1.2, the processor pointer will be
 * set to NULL.
 * Whereas, for BASIL 1.3 and BASIL 1.4 we reset it in segment_start.
 *
 * The standard Expat start handler function prototype is used.
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 * @return Void
 *
 */
static void
processor_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.processor_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	switch (basilver) {
		case basil_1_0:
		case basil_1_1:
		case basil_1_2:
			d->current.processor = NULL;
			break;
		case basil_1_3:
		case basil_1_4:
		case basil_1_7:
			/* processor is reset in segment_start()
			 * for these BASIL versions
			 */
			break;
	}
	return;
}

/**
 * @brief
 *	This function is registered to handle the processor element within an
 * inventory response.
 *
 * Due to the new response format introduced in BASIL 1.3, and
 * continuing in BASIL 1.4, the information attached to different XML
 * sections has changed. For example, processor arch and MHz info is
 * no longer part of the processor XML for BASIL 1.3 and 1.4. Thus that
 * information is not verified here.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 */
static void
processor_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_processor_t *processor;
	basil_node_computeunit_t *cu = NULL;

	if (stack_busted(d))
		return;
	processor = malloc(sizeof(basil_node_processor_t));
	if (!processor) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(processor, 0, sizeof(basil_node_processor_t));
	processor->ordinal = -1;
	processor->clock_mhz = -1;
	if (d->current.processor) {
		(d->current.processor)->next = processor;
	} else {
		if (!d->current.segment) {
			parse_err_internal(d);
			free(processor);
			return;
		}
		(d->current.segment)->processors = processor;
	}
	d->current.processor = processor;
	switch (basilver) {
		case basil_1_0:
		case basil_1_1:
		case basil_1_2:
			/* There are no computeunits for these BASIL versions */
			break;
		case basil_1_3:
		case basil_1_4:
		case basil_1_7:
			cu = (d->current.segment)->computeunits;
			if (!cu) {
				parse_err_internal(d);
				return;
			}
			break;
	}

	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_ORDINAL, *np) == 0) {
			if (processor->ordinal >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			processor->ordinal = atol(*vp);
			if (processor->ordinal < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
			if (cu) {
				cu->proc_per_cu_count = processor->ordinal + 1;
			}
		} else if (strcmp(BASIL_ATR_ARCH, *np) == 0) {
			if (processor->arch) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_X86_64, *vp) == 0) {
				processor->arch = basil_processor_x86_64;
			} else if (strcmp(BASIL_VAL_CRAY_X2, *vp) == 0) {
				processor->arch = basil_processor_cray_x2;
			} else if (strcmp(BASIL_VAL_AARCH64, *vp) == 0) {
				processor->arch = basil_processor_aarch64;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_CLOCK_MHZ, *np) == 0) {
			if (processor->clock_mhz >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			processor->clock_mhz = atoi(*vp);
			if (processor->clock_mhz < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (processor->ordinal < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_ORDINAL);
		return;
	}
	switch (basilver) {
		case basil_1_0:
		case basil_1_1:
		case basil_1_2:
			if (!processor->arch) {
				parse_err_unspecified_attr(d, BASIL_ATR_ARCH);
				return;
			}
			if (processor->clock_mhz < 0) {
				parse_err_unspecified_attr(d, BASIL_ATR_CLOCK_MHZ);
				return;
			}
			break;
		case basil_1_3:
		case basil_1_4:
		case basil_1_7:
			/* The arch and mhz info is no longer part of the
			 * processor XML for these BASIL versions
			 */
			break;
	}
	d->current.processor_allocation = NULL;
	return;
}

/**
 * This function is registered to handle the processor allocation element
 * within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 */
static void
processor_allocation_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_processor_allocation_t *procalloc;

	if (stack_busted(d))
		return;
	procalloc = malloc(sizeof(basil_processor_allocation_t));
	if (!procalloc) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(procalloc, 0, sizeof(basil_processor_allocation_t));
	procalloc->rsvn_id = -1;
	if (d->current.processor_allocation) {
		(d->current.processor_allocation)->next = procalloc;
	} else {
		if (!d->current.processor) {
			parse_err_internal(d);
			free(procalloc);
			return;
		}
		(d->current.processor)->allocations = procalloc;
	}
	d->current.processor_allocation = procalloc;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			if (procalloc->rsvn_id >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			procalloc->rsvn_id = atol(*vp);
			if (procalloc->rsvn_id < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (procalloc->rsvn_id < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_RSVN_ID);
		return;
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the memory array element within
 * an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
memory_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.memory_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.memory = NULL;
	return;
}

/**
 * @brief
 *	This function is registered to handle the memory element within an
 * inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 */
static void
memory_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_memory_t *memory;

	if (stack_busted(d))
		return;
	memory = malloc(sizeof(basil_node_memory_t));
	if (!memory) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(memory, 0, sizeof(basil_node_memory_t));
	memory->page_size_kb = -1;
	memory->page_count = -1;
	if (d->current.memory) {
		(d->current.memory)->next = memory;
	} else {
		if (!d->current.segment) {
			parse_err_internal(d);
			free(memory);
			return;
		}
		(d->current.segment)->memory = memory;
	}
	d->current.memory = memory;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_TYPE, *np) == 0) {
			if (memory->type != 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_OS, *vp) == 0) {
				memory->type = basil_memory_type_os;
			} else if (strcmp(BASIL_VAL_VIRTUAL, *vp) == 0) {
				memory->type = basil_memory_type_virtual;
			} else if (strcmp(BASIL_VAL_HUGEPAGE, *vp) == 0) {
				memory->type = basil_memory_type_hugepage;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_PAGE_SIZE_KB, *np) == 0) {
			if (memory->page_size_kb >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			memory->page_size_kb = atol(*vp);
			if (memory->page_size_kb < 1) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_PAGE_COUNT, *np) == 0) {
			if (memory->page_count >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			memory->page_count = atol(*vp);
			if (memory->page_count < 1) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (!memory->type) {
		parse_err_unspecified_attr(d, BASIL_ATR_TYPE);
		return;
	}
	if (memory->page_size_kb < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_PAGE_SIZE_KB);
		return;
	}
	if (memory->page_count < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_PAGE_COUNT);
		return;
	}
	d->current.memory_allocation = NULL;
	return;
}

/**
 * @brief
 *	This function is registered to handle the memory allocation element
 * 	within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
memory_allocation_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_memory_allocation_t *memalloc;

	if (stack_busted(d))
		return;
	memalloc = malloc(sizeof(basil_memory_allocation_t));
	if (!memalloc) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(memalloc, 0, sizeof(basil_memory_allocation_t));
	memalloc->rsvn_id = -1;
	memalloc->page_count = -1;
	if (d->current.memory_allocation) {
		(d->current.memory_allocation)->next = memalloc;
	} else {
		if (!d->current.memory) {
			parse_err_internal(d);
			free(memalloc);
			return;
		}
		(d->current.memory)->allocations = memalloc;
	}
	d->current.memory_allocation = memalloc;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			if (memalloc->rsvn_id >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			memalloc->rsvn_id = atol(*vp);
			if (memalloc->rsvn_id < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_PAGE_COUNT, *np) == 0) {
			if (memalloc->page_count > 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			memalloc->page_count = atol(*vp);
			if (memalloc->page_count <= 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (memalloc->rsvn_id < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_RSVN_ID);
		return;
	}
	if (memalloc->page_count <= 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_PAGE_COUNT);
		return;
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the label array element within
 * 	an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
label_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.label_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.label = NULL;
	return;
}

/**
 * @brief
 *	 This function is registered to handle the label element within an
 * 	inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
label_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_label_t *label;

	if (stack_busted(d))
		return;
	label = malloc(sizeof(basil_label_t));
	if (!label) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(label, 0, sizeof(basil_label_t));
	if (d->current.label) {
		(d->current.label)->next = label;
	} else {
		if (!d->current.segment) {
			parse_err_internal(d);
			free(label);
			return;
		}
		(d->current.segment)->labels = label;
	}
	d->current.label = label;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_NAME, *np) == 0) {
			if (*label->name) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(label->name, BASIL_STRING_MEDIUM, "%s", *vp);
		} else if (strcmp(BASIL_ATR_TYPE, *np) == 0) {
			if (label->type) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_HARD, *vp) == 0) {
				label->type = basil_label_type_hard;
			} else if (strcmp(BASIL_VAL_SOFT, *vp) == 0) {
				label->type = basil_label_type_soft;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_DISPOSITION, *np) == 0) {
			if (label->disposition) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_ATTRACT, *vp) == 0) {
				label->disposition =
					basil_label_disposition_attract;
			} else if (strcmp(BASIL_VAL_REPEL, *vp) == 0) {
				label->disposition =
					basil_label_disposition_repel;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (*label->name == '\0') {
		parse_err_unspecified_attr(d, BASIL_ATR_NAME);
		return;
	}
	if (!label->type) {
		label->type = basil_label_type_hard;
	}
	if (!label->disposition) {
		label->disposition = basil_label_disposition_attract;
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the accelerator array element
 * 	within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
accelerator_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.accelerator_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.accelerator = NULL;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the accelerator element within an
 * 	inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
accelerator_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_accelerator_t *accelerator;
	basil_accelerator_gpu_t *gpu;
	char *family;

	if (stack_busted(d))
		return;
	accelerator = malloc(sizeof(basil_node_accelerator_t));
	if (!accelerator) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(accelerator, 0, sizeof(basil_node_accelerator_t));
	gpu = malloc(sizeof(basil_accelerator_gpu_t));
	if (!gpu) {
		parse_err_out_of_memory(d);
		free(accelerator);
		return;
	}
	memset(gpu, 0, sizeof(basil_accelerator_gpu_t));
	accelerator->data.gpu = gpu;
	if (d->current.accelerator) {
		(d->current.accelerator)->next = accelerator;
	} else {
		if (!d->current.node) {
			parse_err_internal(d);
			free(gpu);
			free(accelerator);
			return;
		}
		(d->current.node)->accelerators = accelerator;
	}
	d->current.accelerator = accelerator;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		int len = 0;
		if (strcmp(BASIL_ATR_ORDINAL, *np) == 0) {
			/*
			 * Do nothing with the ordinal there is no
			 * place in the structure to put it
			 */
		} else if (strcmp(BASIL_ATR_TYPE, *np) == 0) {
			if (accelerator->type) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_GPU, *vp) == 0) {
				accelerator->type = basil_accel_gpu;
				d->current.accel_type_gpu++;
			} else {
				d->current.accel_type_unknown++;
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_STATE, *np) == 0) {
			if (accelerator->state) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_UP, *vp) == 0) {
				d->current.accel_state_up++;
				accelerator->state = basil_accel_state_up;
			} else if (strcmp(BASIL_VAL_DOWN, *vp) == 0) {
				d->current.accel_state_down++;
				accelerator->state = basil_accel_state_down;
			} else {
				d->current.accel_state_unknown++;
				accelerator->state = basil_accel_state_unknown;
			}
		} else if (strcmp(BASIL_ATR_FAMILY, *np) == 0) {
			if (gpu->family) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			len = strlen(*vp) + 1;
			family = malloc(len);
			if (!family) {
				parse_err_out_of_memory(d);
				return;
			}
			snprintf(family, len, "%s", *vp);
			gpu->family = family;
		} else if (strcmp(BASIL_ATR_MEMORY_MB, *np) == 0) {
			if (gpu->memory > 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			gpu->memory = atoi(*vp);
			if (gpu->memory < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_CLOCK_MHZ, *np) == 0) {
			if (gpu->clock_mhz > 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			gpu->clock_mhz = atoi(*vp);
			if (gpu->memory < 1) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (!accelerator->type) {
		parse_err_unspecified_attr(d, BASIL_ATR_TYPE);
		return;
	}
	if (!accelerator->state) {
		parse_err_unspecified_attr(d, BASIL_ATR_STATE);
		return;
	}
	if (!gpu->family) {
		parse_err_unspecified_attr(d, BASIL_ATR_FAMILY);
		return;
	}
	if (gpu->clock_mhz < 1) {
		parse_err_unspecified_attr(d, BASIL_ATR_CLOCK_MHZ);
		return;
	}
	d->current.accelerator_allocation = NULL;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the accelerator allocation element
 * 	within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
accelerator_allocation_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_accelerator_allocation_t *accelalloc;

	if (stack_busted(d))
		return;
	accelalloc = malloc(sizeof(basil_accelerator_allocation_t));
	if (!accelalloc) {
		parse_err_out_of_memory(d);
		return;
	}
	memset(accelalloc, 0, sizeof(basil_accelerator_allocation_t));
	accelalloc->rsvn_id = -1;
	if (d->current.accelerator_allocation) {
		(d->current.accelerator_allocation)->next = accelalloc;
	} else {
		if (!d->current.accelerator) {
			parse_err_internal(d);
			free(accelalloc);
			return;
		}
		(d->current.accelerator)->allocations = accelalloc;
	}
	d->current.accelerator_allocation = accelalloc;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			if (accelalloc->rsvn_id >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			accelalloc->rsvn_id = atol(*vp);
			if (accelalloc->rsvn_id < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
	if (accelalloc->rsvn_id < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_RSVN_ID);
		return;
	}
	return;
}

/**
 * @brief
 *	 This function is registered to handle the reservation array element
 * 	within an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
reservation_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.reservation_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.reservation = NULL;
	return;
}

/**
 * This function is registered to handle the reservation element within a
 * query response.  This is used for both status response and inventory response.
 *
 * The standard Expat start handler function prototype is used.
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 */
static void
reservation_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_rsvn_t *rsvn;
	basil_response_t *brp;
	basil_response_query_status_res_t *res_status = NULL;
	basil_response_switch_res_t *switch_res = NULL;

	if (stack_busted(d))
		return;

	/*
	 * Which type of reservation line is this?  Is it for an INVENTORY response?
	 * Or is it for a SWITCH STATUS response?
	 */
	brp = d->brp;
	if (!brp)
		return;

	if ((brp->method == basil_method_query) && (brp->data.query.type == basil_query_status)) {
		/* This is for a SWITCH status response */
		res_status = malloc(sizeof(basil_response_query_status_res_t));
		if (!res_status) {
			parse_err_out_of_memory(d);
			return;
		}
		memset(res_status, 0, sizeof(basil_response_query_status_res_t));
		res_status->rsvn_id = -1;
		res_status->status = basil_reservation_status_none;
		if (d->brp->data.query.data.status.reservation) {
			(d->brp->data.query.data.status.reservation)->next = res_status;
		} else {
			d->brp->data.query.data.status.reservation = res_status;
		}

		/*
		 * work through the attribute pairs updating the name pointer
		 * and value pointer with each loop.  The somewhat complex loop
		 * control syntax is just a fancy way of stepping through
		 * the pairs.
		 */
		for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
			xml_dbg("%s: %s = %s", (char *) __func__, *np, *vp);
			if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
				if (res_status->rsvn_id >= 0) {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				res_status->rsvn_id = atol(*vp);
				if (res_status->rsvn_id < 0) {
					parse_err_illegal_attr_val(d, *np, *vp);
					return;
				}
			} else if (strcmp(BASIL_ATR_STATUS, *np) == 0) {
				if (res_status->status > 0) {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				if (strcmp(BASIL_VAL_EMPTY, *vp) == 0) {
					res_status->status = basil_reservation_status_empty;
				} else if (strcmp(BASIL_VAL_INVALID, *vp) == 0) {
					res_status->status = basil_reservation_status_invalid;
				} else if (strcmp(BASIL_VAL_MIX, *vp) == 0) {
					res_status->status = basil_reservation_status_mix;
				} else if (strcmp(BASIL_VAL_RUN, *vp) == 0) {
					res_status->status = basil_reservation_status_run;
				} else if (strcmp(BASIL_VAL_SUSPEND, *vp) == 0) {
					res_status->status = basil_reservation_status_suspend;
				} else if (strcmp(BASIL_VAL_SWITCH, *vp) == 0) {
					res_status->status = basil_reservation_status_switch;
				} else if (strcmp(BASIL_VAL_UNKNOWN, *vp) == 0) {
					res_status->status = basil_reservation_status_unknown;
				} else {
					parse_err_illegal_attr_val(d, *np, *vp);
					return;
				}
			} else {
				parse_err_unrecognized_attr(d, *np);
				return;
			}
		}
		if (res_status->rsvn_id < 0) {
			parse_err_unspecified_attr(d, BASIL_ATR_RSVN_ID);
			return;
		}
		if (res_status->status == basil_reservation_status_none) {
			parse_err_unspecified_attr(d, BASIL_ATR_STATUS);
			return;
		}
	} else if (brp->method == basil_method_switch) {
		/* This is for a response to a SWITCH request */
		switch_res = malloc(sizeof(basil_response_switch_res_t));
		if (!switch_res) {
			parse_err_out_of_memory(d);
			return;
		}
		memset(switch_res, 0, sizeof(basil_response_switch_res_t));

		switch_res->rsvn_id = -1;
		switch_res->status = basil_reservation_status_none;
		if (brp->data.swtch.reservation) {
			(brp->data.swtch.reservation)->next = switch_res;
		} else {
			brp->data.swtch.reservation = switch_res;
		}
		/*
		 * work through the attribute pairs updating the name pointer
		 * and value pointer with each loop.  The somewhat complex loop
		 * control syntax is just a fancy way of stepping through
		 * the pairs.
		 */
		for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
			xml_dbg("%s: %s = %s", (char *) __func__, *np, *vp);
			if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
				if (switch_res->rsvn_id >= 0) {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				switch_res->rsvn_id = atol(*vp);
				if (switch_res->rsvn_id < 0) {
					parse_err_illegal_attr_val(d, *np, *vp);
					return;
				}
			} else if (strcmp(BASIL_ATR_STATUS, *np) == 0) {
				if (switch_res->status > 0) {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				if (strcmp(BASIL_VAL_SUCCESS, *vp) == 0) {
					switch_res->status = basil_switch_status_success;
				} else if (strcmp(BASIL_VAL_FAILURE, *vp) == 0) {
					/* do nothing here, brp->error was set 	*/
					/* in alps_request_parent 		*/
				} else {
					parse_err_illegal_attr_val(d, *np, *vp);
					return;
				}
			} else {
				parse_err_unrecognized_attr(d, *np);
				return;
			}
		}
	} else {
		/* This is for an inventory response */
		rsvn = malloc(sizeof(basil_rsvn_t));
		if (!rsvn) {
			parse_err_out_of_memory(d);
			return;
		}
		memset(rsvn, 0, sizeof(basil_rsvn_t));
		rsvn->rsvn_id = -1;
		if (d->current.reservation) {
			(d->current.reservation)->next = rsvn;
		} else {
			brp->data.query.data.inventory.rsvns = rsvn;
		}
		d->current.reservation = rsvn;
		/*
		 * Work through the attribute pairs updating the name pointer and
		 * value pointer with each loop. The somewhat complex loop control
		 * syntax is just a fancy way of stepping through the pairs.
		 */
		for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
			if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
				if (rsvn->rsvn_id >= 0) {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				rsvn->rsvn_id = atol(*vp);
				if (rsvn->rsvn_id < 0) {
					parse_err_illegal_attr_val(d, *np, *vp);
					return;
				}
			} else if (strcmp(BASIL_ATR_USER_NAME, *np) == 0) {
				if (*rsvn->user_name != '\0') {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				snprintf(rsvn->user_name, BASIL_STRING_MEDIUM,
					 "%s", *vp);
			} else if (strcmp(BASIL_ATR_ACCOUNT_NAME, *np) == 0) {
				if (*rsvn->account_name != '\0') {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				snprintf(rsvn->account_name, BASIL_STRING_MEDIUM,
					 "%s", *vp);
			} else if (strcmp(BASIL_ATR_TIME_STAMP, *np) == 0) {
				if (*rsvn->time_stamp != '\0') {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				snprintf(rsvn->time_stamp, BASIL_STRING_MEDIUM,
					 "%s", *vp);
			} else if (strcmp(BASIL_ATR_BATCH_ID, *np) == 0) {
				if (*rsvn->batch_id != '\0') {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				snprintf(rsvn->batch_id, BASIL_STRING_LONG,
					 "%s", *vp);
			} else if (strcmp(BASIL_ATR_RSVN_MODE, *np) == 0) {
				if (*rsvn->rsvn_mode != '\0') {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				snprintf(rsvn->rsvn_mode, BASIL_STRING_MEDIUM,
					 "%s", *vp);
			} else if (strcmp(BASIL_ATR_GPC_MODE, *np) == 0) {
				if (*rsvn->gpc_mode != '\0') {
					parse_err_multiple_attrs(d, *np);
					return;
				}
				snprintf(rsvn->gpc_mode, BASIL_STRING_MEDIUM,
					 "%s", *vp);
			} else {
				parse_err_unrecognized_attr(d, *np);
				return;
			}
		}
		if (rsvn->rsvn_id < 0) {
			parse_err_unspecified_attr(d, BASIL_ATR_RSVN_ID);
			return;
		}
		if (*rsvn->user_name == '\0') {
			parse_err_unspecified_attr(d, BASIL_ATR_USER_NAME);
			return;
		}
		if (*rsvn->account_name == '\0') {
			parse_err_unspecified_attr(d, BASIL_ATR_ACCOUNT_NAME);
			return;
		}
		d->count.application_array = 0;
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the application array element
 * 	within an inventory response.
 *
 * @note
 * 	PBS accepts this element but ignores it.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
application_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.application_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the application element
 * 	within an inventory response.
 *
 * @note
 * 	PBS accepts this element but ignores it.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
application_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	if (stack_busted(d))
		return;
	d->count.command_array = 0;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the command array element
 * 	within an inventory response.
 *
 * @note
 * 	PBS accepts this element but ignores it.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
command_array_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;
	if (++(d->count.command_array) > 1) {
		parse_err_multiple_elements(d);
		return;
	}
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	return;
}

/**
 * @brief
 * 	This function is registered to handle the XML elements that are
 * 	to be ignored.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
ignore_element(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;

	if (stack_busted(d))
		return;

	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
	}
	return;
}

/**
 * @brief
 * 	Generic method registered to handle character data for elements
 * 	that do not utilize it. Make sure we skip whitespace characters
 * 	since they may be there for formatting.
 *
 * The standard Expat character handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] s string
 * @param[in] len length of string
 *
 * @return Void
 *
 */
static void
disallow_char_data(ud_t *d, const XML_Char *s, int len)
{
	int i;

	for (i = 0; i < len; i++) {
		if (!isspace(*(s + i)))
			break;
	}
	if (i == len)
		return;
	parse_err_illegal_char_data(d, s);
	return;
}

/**
 * @brief
 * Helper function for allow_char_data() that is registered to handle
 * character data for elements.
 * The user data structure (ud_t) is populated with the node rangelist associated
 * with the 'Nodes' element (in the System BASIL 1.7 XML response), that is
 * currently being processed.
 *
 * @param d pointer to user data structure.
 * @param[in] s string.
 * @param[in] len length of string.
 *
 * @return void
 */
static void
parse_nidlist_char_data(ud_t *d, const char *s, int len)
{
	char *tmp_ptr = NULL;

	/*
	 * Point 'nidlist' to a copy of s (which now contains the parsed char data
	 * i.e. the node rangelist).
	 */
	if ((d->current_sys.node_group->nidlist = strndup(s, len)) == NULL) {
		parse_err_out_of_memory(d);
		d->current_sys.node_group->nidlist = NULL;
		return;
	}

	/*
	 * Check if the current rangelist of Nodes is of type KNL and that such Nodes
	 * are in "batch" mode.  Checking the state of the node while parsing the
	 * system query for node list is not require, doing this will keep this
	 * (KNL node(s) in down state) out of KNL node list we populate (which we
	 * use in inventory_to_vnodes to skip these node while creating non KNL nodes)
	 * and if this node comes up in the inventory query then this(KNL node) will
	 * be created as non KNL node.
	 */
	if (!exclude_from_KNL_processing(d->current_sys.node_group, 0)) {
		/*
		 * Accummulate KNL Nodes, extracted from each Node group, in a buffer
		 * for later use. The KNL Nodes in this buffer will be excluded from vnode
		 * creation in inventory_to_vnodes() (which creates non-KNL vnodes only).
		 */
		if (!knl_node_list) {
			knl_node_list = malloc(sizeof(char) * (len + 1));
			if (knl_node_list == NULL) {
				log_err(errno, __func__, "malloc failure");
				return;
			}
			pbs_strncpy(knl_node_list, d->current_sys.node_group->nidlist, (len + 1));
		} else {
			/* Allocate an extra byte for the "," separation between rangelists. */
			tmp_ptr = realloc(knl_node_list, sizeof(char) * (strlen(knl_node_list) + len + 2));
			if (!tmp_ptr) {
				log_err(errno, __func__, "realloc failure");
				free(knl_node_list);
				knl_node_list = NULL;
				return;
			}
			knl_node_list = tmp_ptr;

			/*
			 * To maintain comma separation between Node rangelists belonging
			 * to each Node Group (in the System XML Response), we append a
			 * "," at the end of the current array e.g. 12,13-15,16,17 is what
			 * we want and not 12,13-1516,17.
			 */
			strcat(knl_node_list, ",");
			strcat(knl_node_list, d->current_sys.node_group->nidlist);
		}
	}
}

/**
 * @brief
 * Function registered to handle character data for XML Elements
 * that utilize it. Skip leading whitespace characters since they
 * may be there for formatting.
 *
 * @param d pointer to user data structure.
 * @param[in] s string.
 * @param[in] len length of string.
 *
 * @return void
 */
static void
allow_char_data(ud_t *d, const XML_Char *s, int len)
{
	int i = 0;
	int j = 0;

	/*
	 * As an example, a string 's' could initially point to a rangelist
	 * "  12-15,18,19,20".  'j' accummulates the leading whitespace count.
	 */
	for (i = 0; i < len; i++) {
		if (!isspace(*(s + i)))
			break;
		j++;
	}
	if (i == len)
		return;

	/*
	 * 's+j' is the location where the 'useful' data starts.
	 * Subtracting the whitespace count from 'len' gives the true length of
	 * the node rangelist string e.g. "12-15,18,19,20".
	 */
	parse_nidlist_char_data(d, s + j, len - j);
}

/**
 * @brief
 * 	Generic method registered to handle the end of an element where
 * 	no post processing needs to take place. Make sure the element end
 * 	is balanced with the element start.
 *
 * The standard Expat end handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el name of end element
 *
 * @return Void
 *
 */
static void
default_element_end(ud_t *d, const XML_Char *el)
{
	if (strcmp(el, handler[d->stack[d->depth]].element) != 0)
		parse_err_illegal_end(d, el);
	return;
}

/**
 * @brief
 * 	Special method registered to handle the end of the inventory element.
 * 	The counts for the roles and states of the nodes are logged here.
 *
 * The standard Expat end handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el name of end element
 *
 * @return Void
 *
 */
static void
inventory_end(ud_t *d, const XML_Char *el)
{
	if (strcmp(el, handler[d->stack[d->depth]].element) != 0)
		parse_err_illegal_end(d, el);

	sprintf(log_buffer, "%d interactive, %d batch, %d unknown",
		d->current.role_int,
		d->current.role_batch,
		d->current.role_unknown);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  "roles", log_buffer);
	sprintf(log_buffer, "%d up, %d down, %d unavailable, %d routing, "
			    "%d suspect, %d admin, %d unknown",
		d->current.state_up,
		d->current.state_down,
		d->current.state_unavail,
		d->current.state_routing,
		d->current.state_suspect,
		d->current.state_admin,
		d->current.state_unknown);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  "state", log_buffer);
	sprintf(log_buffer, "%d gpu, %d unknown",
		d->current.accel_type_gpu,
		d->current.accel_type_unknown);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  "accelerator types", log_buffer);
	sprintf(log_buffer, "%d up, %d down, %d unknown",
		d->current.accel_state_up,
		d->current.accel_state_down,
		d->current.accel_state_unknown);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  "accelerator state", log_buffer);
	sprintf(log_buffer, "%d sockets", d->current.socket_count);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  "inventory", log_buffer);
	return;
}

/**
 * @brief
 * 	Find the element handler function registered for a particular element.
 *
 * @param[in] el name of element to search for
 * @return index of the matching handler array entry
 *
 * @return 		int
 * @retval -1 no 	match
 * @retval  !(-1) 	matched index
 *
 */
int
handler_find_index(const XML_Char *el)
{
	int i = 0;

	for (i = 1; handler[i].element; i++) {
		if (strcmp(handler[i].element, el) == 0)
			return (i);
	}
	return (-1);
}

/**
 * @brief
 * 	Parse the start of any element by looking up its handler and
 * 	calling it.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return Void
 *
 */
static void
parse_element_start(void *ud, const XML_Char *el, const XML_Char **atts)
{
	int i = 0;
	ud_t *d;

	if (!ud)
		return;
	d = (ud_t *) ud;
	xml_dbg("parse_element_start: ELEMENT = %s", el);
	i = handler_find_index(el);
	if (i < 0) {
		sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
		sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
		snprintf(d->message, sizeof(d->message),
			 "Unrecognized element start at line %d: %s",
			 (int) XML_GetCurrentLineNumber(parser), el);
		return;
	}
	d->depth++;
	d->stack[d->depth] = i;
	handler[i].start(d, el, atts);
	return;
}

/**
 * @brief
 * 	Parse the end of any element by looking up its handler and
 * 	calling it.
 *
 * The standard Expat end handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el name of end element
 *
 * @return Void
 *
 */
static void
parse_element_end(void *ud, const XML_Char *el)
{
	int i = 0;
	ud_t *d;

	if (!ud)
		return;
	d = (ud_t *) ud;
	xml_dbg("parse_element_end: ELEMENT = %s", el);
	i = handler_find_index(el);
	if (i < 0) {
		sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
		sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
		snprintf(d->message, sizeof(d->message),
			 "Unrecognized element end at line %d: %s",
			 (int) XML_GetCurrentLineNumber(parser), el);
		return;
	}
	handler[i].end(d, el);
	d->stack[d->depth] = 0;
	d->depth--;
	return;
}

/**
 * @brief
 * 	Parse the character data for any element by invoking the registered
 *	handler.
 *
 * The standard Expat character handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] s string
 * @param[in] len length of string
 *
 * @return Void
 *
 */
static void
parse_char_data(void *ud, const XML_Char *s, int len)
{
	ud_t *d;

	if (!ud)
		return;
	d = (ud_t *) ud;
	handler[d->stack[d->depth]].char_data(d, s, len);
	return;
}

/**
 * @brief
 *	This function walks all the segments and fills in the information needed to
 * generate the vnodes. It is called directly when PBS is using BASIL 1.2 or
 * prior XML inventories. It is called from within the socket loop when PBS
 * gets BASIL 1.3 and BASIL 1.4 XML inventory.
 * @param[in] node	information about the node
 * @param[in] nv	vnode list information
 * @param[in] arch	the architecture of the vnode
 * @param[in/out] total_seg	latest count of the segments, to increase
 *				across sockets
 * @param[in] order	order number of the vnode
 * @param[in/out] name_buf	upon exiting it contains the name of the vnode
 * @param[in/out] total_cpu	keeps a running count of cpus for the whole node
 * @param[in/out] total_mem	keeps a running count of mem for the whole node
 *
 * These last three parameters are used for the vnode_per_numa_node = 0 case.
 * Where we only create one PBS vnode per Cray compute node
 *
 * @return Void
 */
void
inventory_loop_on_segments(basil_node_t *node, vnl_t *nv, char *arch,
			   int *total_seg, long order, char *name_buf, int *total_cpu, long *total_mem)
{
	basil_node_socket_t *socket = NULL;
	basil_node_segment_t *seg = NULL;
	basil_node_processor_t *proc = NULL;
	basil_node_memory_t *mem = NULL;
	basil_label_t *label = NULL;
	basil_node_accelerator_t *accel = NULL;
	basil_node_computeunit_t *cu = NULL;
	int aflag = READ_WRITE | ATR_DFLAG_CVTSLT;
	long totmem = 0;
	int totcpus = 0;
	int totaccel = 0;
	int first_seg = 0;
	char vname[VNODE_NAME_LEN];
	char *attr;
	int totseg = 0;

	/* Proceed only if we have valid pointers */
	if (node == NULL) {
		sprintf(log_buffer, "Bad pointer to node info");
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE,
			  LOG_ERR, __func__, log_buffer);
		return;
	}
	if (nv == NULL) {
		sprintf(log_buffer, "Bad pointer to node list info");
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE,
			  LOG_ERR, __func__, log_buffer);
		return;
	}

	totseg = *total_seg;
	totcpus = *total_cpu;
	totmem = *total_mem;

	socket = node->sockets;
	do {
		if (socket) {
			seg = socket->segments;
			socket = socket->next;
		} else {
			seg = node->segments;
		}

		for (; seg; seg = seg->next, totseg++) {
			if (totseg == 0) {
				/* The first segment is different and important
				 * because some information is only attached to the
				 * very first segment of a vnode.
				 */
				first_seg = 1;
			}
			if (vnode_per_numa_node) {
				snprintf(vname, sizeof(vname), "%s_%ld_%d",
					 mpphost, node->node_id, totseg);
				vname[sizeof(vname) - 1] = '\0';
			} else if (first_seg) {
				/* When concatenating the segments into
				 * one vnode, we don't put any segment info
				 * in the name.
				 */
				snprintf(vname, sizeof(vname), "%s_%ld",
					 mpphost, node->node_id);
				vname[sizeof(vname) - 1] = '\0';
			}

			attr = "sharing";
			/* already exists so don't define type */
			if (vn_addvnr(nv, vname, attr,
				      ND_Force_Exclhost,
				      0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScrayorder";
			sprintf(utilBuffer, "%ld", order);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
				      ATR_TYPE_LONG, aflag,
				      NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.arch";
			if (vn_addvnr(nv, vname, attr, arch,
				      0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.host";
			sprintf(utilBuffer, "%s_%ld", mpphost, node->node_id);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
				      0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScraynid";
			sprintf(utilBuffer, "%ld", node->node_id);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
				      ATR_TYPE_STR, aflag,
				      NULL) == -1)
				goto bad_vnl;

			if (vnode_per_numa_node) {
				attr = "resources_available.PBScrayseg";
				sprintf(utilBuffer, "%d", totseg);
				if (vn_addvnr(nv, vname, attr, utilBuffer,
					      ATR_TYPE_STR, aflag,
					      NULL) == -1)
					goto bad_vnl;
			}

			attr = "resources_available.vntype";
			if (vn_addvnr(nv, vname, attr, CRAY_COMPUTE,
				      0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScrayhost";
			if (vn_addvnr(nv, vname, attr, mpphost,
				      ATR_TYPE_STR, aflag,
				      NULL) == -1)
				goto bad_vnl;

			if (vnode_per_numa_node) {
				totcpus = 0;
				cu = seg->computeunits;
				if (cu) {
					for (cu = seg->computeunits; cu; cu = cu->next) {
						totcpus++;
					}
				} else {
					for (proc = seg->processors; proc; proc = proc->next)
						totcpus++;
				}

				attr = "resources_available.ncpus";
				sprintf(utilBuffer, "%d", totcpus);
				if (vn_addvnr(nv, vname, attr, utilBuffer,
					      0, 0, NULL) == -1)
					goto bad_vnl;

				attr = "resources_available.mem";
				totmem = 0;
				for (mem = seg->memory; mem; mem = mem->next)
					totmem += (mem->page_size_kb * mem->page_count);
				sprintf(utilBuffer, "%ldkb", totmem);
				if (vn_addvnr(nv, vname, attr, utilBuffer,
					      0, 0, NULL) == -1)
					goto bad_vnl;

				for (label = seg->labels; label; label = label->next) {
					sprintf(utilBuffer,
						"resources_available.PBScraylabel_%s",
						label->name);
					if (vn_addvnr(nv, vname, utilBuffer, "true",
						      ATR_TYPE_BOOL, aflag,
						      NULL) == -1)
						goto bad_vnl;
				}
			} else {
				/*
				 * vnode_per_numa_node is false, which
				 * means we need to compress all the segment info (and
				 * in the case of BASIl 1.3 and higher the socket
				 * info too) into only one vnode. We need to
				 * total up the cpus and memory for each of the
				 * segments and report it as part of the
				 * whole vnode. Add/set labels only once.
				 * All labels are assumed to be the same on
				 * all segments.
				 */
				for (mem = seg->memory; mem; mem = mem->next)
					totmem += mem->page_size_kb * mem->page_count;

				cu = seg->computeunits;
				if (cu) {
					for (cu = seg->computeunits; cu; cu = cu->next) {
						totcpus++;
					}
				} else {
					for (proc = seg->processors; proc; proc = proc->next)
						totcpus++;
				}

				if (totseg == 0) {
					for (label = seg->labels; label; label = label->next) {
						sprintf(utilBuffer,
							"resources_available.PBScraylabel_%s",
							label->name);
						if (vn_addvnr(nv, vname, utilBuffer, "true",
							      ATR_TYPE_BOOL, aflag,
							      NULL) == -1)
							goto bad_vnl;
					}
				}
			}
			/* Only do this for nodes that have accelerators */
			if (node->accelerators) {
				for (accel = node->accelerators, totaccel = 0;
				     accel; accel = accel->next) {
					if (accel->state == basil_accel_state_up)
						/* Only count them if the state is UP */
						totaccel++;
				}
				attr = "resources_available.naccelerators";
				if (totseg == 0) {
					/*
					 * add the naccelerators count only to
					 * the first vnode of a compute node
					 * all other vnodes will share the count
					 */
					snprintf(utilBuffer, sizeof(utilBuffer),
						 "%d", totaccel);
				} else if (vnode_per_numa_node) {
					/*
					 * When there is a vnode being created
					 * per numa node, only the first
					 * (segment 0) vnode gets the accelerator.
					 * The other vnodes must
					 * share the accelerator count with
					 * segment 0 vnodes
					 */
					snprintf(utilBuffer, sizeof(utilBuffer),
						 "@%s_%ld_0",
						 mpphost, node->node_id);
				}

				if (vnode_per_numa_node || totseg == 0) {
					if (vn_addvnr(nv, vname, attr, utilBuffer,
						      0, 0, NULL) == -1)
						goto bad_vnl;
				}

				attr = "resources_available.accelerator";
				if (totaccel > 0) {
					/* set to 'true' if the accelerator
					 * is in state=up, totaccel is only
					 * incremented if state=up
					 */
					snprintf(utilBuffer, sizeof(utilBuffer), "true");
				} else {
					/* set to 'false' to show that the
					 * vnode has accelerator(s) but they
					 * are not currently state=up
					 */
					snprintf(utilBuffer, sizeof(utilBuffer), "false");
				}

				if (vn_addvnr(nv, vname, attr, utilBuffer,
					      0, 0, NULL) == -1)
					goto bad_vnl;

				/*
				 * Only set accelerator_model and
				 * accelerator_memory if the accelerator is UP
				 */
				if (totaccel > 0) {
					accel = node->accelerators;
					if (accel->data.gpu) {
						if (strcmp(accel->data.gpu->family, BASIL_VAL_UNKNOWN) == 0) {
							sprintf(log_buffer, "The GPU family "
									    "value is 'UNKNOWN'. Check "
									    "your Cray GPU inventory.");
							log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__, log_buffer);
						}
						attr = "resources_available.accelerator_model";
						snprintf(utilBuffer, sizeof(utilBuffer),
							 "%s",
							 accel->data.gpu->family);
						if (vn_addvnr(nv, vname, attr,
							      utilBuffer, 0,
							      0, NULL) == -1)
							goto bad_vnl;
						if (accel->data.gpu->memory) {
							attr = "resources_available.accelerator_memory";
							if (totseg == 0) {
								snprintf(utilBuffer,
									 sizeof(utilBuffer),
									 "%umb",
									 accel->data.gpu->memory);
							} else if (vnode_per_numa_node) {
								snprintf(utilBuffer,
									 sizeof(utilBuffer),
									 "@%s_%ld_0",
									 mpphost, node->node_id);
							}

							if (vnode_per_numa_node || totseg == 0) {
								if (vn_addvnr(nv, vname, attr,
									      utilBuffer, 0,
									      0, NULL) == -1)
									goto bad_vnl;
							}
						}
					}
				}
			}
		}

	} while (socket);

	pbs_strncpy(name_buf, vname, VNODE_NAME_LEN);
	*total_cpu = totcpus;
	*total_mem = totmem;
	*total_seg = totseg;

	return;

bad_vnl:
	sprintf(log_buffer, "creation of Cray vnodes failed at %ld, with vname %s", order, vname);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  __func__, log_buffer);
	/*
	 * don't free nv since it might be important in the dump
	 */
	abort();
}

/**
 * @brief
 * 	After the Cray inventory XML response is parsed, use the resulting structures
 * to generate vnodes for the compute nodes and send them to the server.
 *
 * @param brp ALPS inventory response
 *
 * @return	int
 * @retval	0	: success
 * @retval	-1	: failure
 */
static int
inventory_to_vnodes(basil_response_t *brp)
{
	extern int internal_state_update;
	extern int num_acpus;
	extern unsigned long totalmem;
	int aflag = READ_WRITE | ATR_DFLAG_CVTSLT;
	long order = 0;
	char *attr;
	vnl_t *nv = NULL;
	int ret = 0;
	char *xmlbuf;
	int xmllen = 0;
	int seg_num = 0;
	int cpu_ct = 0;
	long *arr_nodes = NULL;
	int node_count = 0;
	int idx = 0;
	int skip_node = 0;
	long mem_ct = 0;
	char name[VNODE_NAME_LEN];
	basil_node_t *node = NULL;
	basil_response_query_inventory_t *inv = NULL;
	hwloc_topology_t topology;

	if (!brp)
		return -1;
	if (brp->method != basil_method_query) {
		snprintf(log_buffer, sizeof(log_buffer), "Wrong method: %d", brp->method);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			  __func__, log_buffer);
		return -1;
	}
	if (brp->data.query.type != basil_query_inventory) {
		snprintf(log_buffer, sizeof(log_buffer), "Wrong query type: %d",
			 brp->data.query.type);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			  __func__, log_buffer);
		return -1;
	}
	if (*brp->error != '\0') {
		snprintf(log_buffer, sizeof(log_buffer), "Error in BASIL response: %s", brp->error);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			  __func__, log_buffer);
		return -1;
	}

	if (vnl_alloc(&nv) == NULL) {
		log_err(errno, __func__, "vnl_alloc failed!");
		return -1;
	}
	pbs_strncpy(mpphost, brp->data.query.data.inventory.mpp_host,
		    sizeof(mpphost));
	nv->vnl_modtime = (long) brp->data.query.data.inventory.timestamp;

	/*
	 * add login node
	 */
	ret = 0;
	if (hwloc_topology_init(&topology) == -1)
		ret = -1;
	else if ((hwloc_topology_set_flags(topology,
					   HWLOC_TOPOLOGY_FLAG_WHOLE_SYSTEM | HWLOC_TOPOLOGY_FLAG_IO_DEVICES) == -1) ||
		 (hwloc_topology_load(topology) == -1) ||
		 (hwloc_topology_export_xmlbuffer(topology, &xmlbuf, &xmllen) == -1)) {
		hwloc_topology_destroy(topology);
		ret = -1;
	}
	if (ret < 0) {
		/* on any failure above, issue log message */
		log_err(PBSE_SYSTEM, __func__, "topology init/load/export failed");
		return -1;
	} else {
		char *lbuf;
		int lbuflen = xmllen + 1024;

		/*
		 *	xmlbuf is almost certain to overflow log_buffer's size,
		 *	so for logging this information, we allocate one large
		 *	enough to hold it
		 */
		if ((lbuf = malloc(lbuflen)) == NULL) {
			snprintf(log_buffer, sizeof(log_buffer), "malloc logbuf (%d) failed",
				 lbuflen);
			hwloc_free_xmlbuffer(topology, xmlbuf);
			hwloc_topology_destroy(topology);
			return -1;
		} else {
			snprintf(lbuf, lbuflen, "allocated log buffer, len %d", lbuflen);
			log_event(PBSEVENT_DEBUG4, PBS_EVENTCLASS_NODE,
				  LOG_DEBUG, __func__, lbuf);
		}
		log_event(PBSEVENT_DEBUG4,
			  PBS_EVENTCLASS_NODE,
			  LOG_DEBUG, __func__, "topology exported");
		snprintf(lbuf, lbuflen, "%s%s", NODE_TOPOLOGY_TYPE_HWLOC, xmlbuf);
		if (vn_addvnr(nv, mom_short_name, ATTR_NODE_TopologyInfo,
			      lbuf, ATR_TYPE_STR, READ_ONLY, NULL) == -1) {
			hwloc_free_xmlbuffer(topology, xmlbuf);
			hwloc_topology_destroy(topology);
			free(lbuf);
			goto bad_vnl;
		} else {
			snprintf(lbuf, lbuflen, "attribute '%s = %s%s' added",
				 ATTR_NODE_TopologyInfo,
				 NODE_TOPOLOGY_TYPE_HWLOC, xmlbuf);
			log_event(PBSEVENT_DEBUG4,
				  PBS_EVENTCLASS_NODE,
				  LOG_DEBUG, __func__, lbuf);
			hwloc_free_xmlbuffer(topology, xmlbuf);
			hwloc_topology_destroy(topology);
			free(lbuf);
		}
	}
	attr = "resources_available.ncpus";
	snprintf(utilBuffer, sizeof(utilBuffer), "%d", num_acpus);
	/* already exists so don't define type */
	if (vn_addvnr(nv, mom_short_name, attr, utilBuffer, 0, 0, NULL) == -1)
		goto bad_vnl;
	attr = "resources_available.mem";
	snprintf(utilBuffer, sizeof(utilBuffer), "%lukb", totalmem);
	/* already exists so don't define type */
	if (vn_addvnr(nv, mom_short_name, attr, utilBuffer, 0, 0, NULL) == -1)
		goto bad_vnl;

	attr = "resources_available.vntype";
	if (vn_addvnr(nv, mom_short_name, attr, CRAY_LOGIN,
		      0, 0, NULL) == -1)
		goto bad_vnl;

	attr = "resources_available.PBScrayhost";
	if (vn_addvnr(nv, mom_short_name, attr, mpphost,
		      ATR_TYPE_STR, aflag, NULL) == -1)
		goto bad_vnl;

	/*
	 * Extract KNL NIDs (Node ID) from 'knl_node_list' ('knl_node_list' is a string
	 * containing a rangelist of KNL Node IDs) and populate 'arr_nodes'.
	 * If BASIL 1.7 is not supported on the Cray system, knl_node_list remains empty,
	 * causing NULL to be returned and node_count to be set to 0.
	 */

	if (basil_1_7_supported)
		arr_nodes = process_nodelist_KNL(knl_node_list, &node_count);
	/*
	 * now create the compute nodes
	 */
	inv = &brp->data.query.data.inventory;
	for (order = 1, node = inv->nodes; node; node = node->next, order++) {
		char *arch;

		/*
		 * We are only interested in creating non-KNL vnodes in this function.
		 * We avoid creating vnodes for KNL Nodes here since they will be
		 * created in system_to_vnodes_KNL(). So, filter them out here.
		 */
		skip_node = 0;
		for (idx = 0; idx < node_count; idx++) {
			if (arr_nodes && node->node_id == arr_nodes[idx]) {
				skip_node = 1;
				break;
			}
		}
		if (skip_node)
			continue;

		(void) memset(name, '\0', VNODE_NAME_LEN);
		if (node->role != basil_node_role_batch)
			continue;
		if (node->state != basil_node_state_up)
			continue;

		switch (node->arch) {
			case basil_node_arch_xt:
				arch = BASIL_VAL_XT;
				break;
			case basil_node_arch_x2:
				arch = BASIL_VAL_X2;
				break;
			default:
				continue;
		}

		if (basil_inventory != NULL) {
			if (first_compute_node) {
				/* Create the name of the very first vnode
				 * so we can attach topology info to it
				 */
				if (vnode_per_numa_node) {
					snprintf(name, VNODE_NAME_LEN, "%s_%ld_0",
						 mpphost, node->node_id);
				} else {
					/* When concatenating the segments into
					 * one vnode, we don't put any segment info
					 * in the name.
					 */
					snprintf(name, VNODE_NAME_LEN, "%s_%ld",
						 mpphost, node->node_id);
				}
				first_compute_node = 0;
				attr = ATTR_NODE_TopologyInfo;
				if (vn_addvnr(nv, name, attr,
					      (char *) basil_inventory,
					      ATR_TYPE_STR, READ_ONLY,
					      NULL) == -1)
					goto bad_vnl;
			}
		} else {
			sprintf(log_buffer, "no saved basil_inventory");
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
				  LOG_DEBUG, __func__, log_buffer);
		}
		seg_num = 0;
		cpu_ct = 0;
		mem_ct = 0;

		inventory_loop_on_segments(node, nv, arch, &seg_num, order, name, &cpu_ct, &mem_ct);

		if (!vnode_per_numa_node) {
			/* Since we're creating one vnode that combines
			 * the info for all the numa nodes,
			 * we've now cycled through all the numa nodes, so
			 * we need to set the total number of cpus and total
			 * memory before moving on to the next node
			 */
			attr = "resources_available.ncpus";
			sprintf(utilBuffer, "%d", cpu_ct);
			if (vn_addvnr(nv, name, attr, utilBuffer,
				      0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.mem";
			snprintf(utilBuffer, sizeof(utilBuffer), "%lukb", mem_ct);
			if (vn_addvnr(nv, name, attr, utilBuffer,
				      0, 0, NULL) == -1)
				goto bad_vnl;
		}
	}
	internal_state_update = UPDATE_MOM_STATE;

	/* merge any existing vnodes into the new set */
	if (vnlp != NULL) {
		if (vn_merge(nv, vnlp, NULL) == NULL)
			goto bad_vnl;
		vnl_free(vnlp);
	}
	vnlp = nv;

	/* We have no further use for this string of KNL node rangelist(s), so free it. */
	if (knl_node_list) {
		free(knl_node_list);
		knl_node_list = NULL;
	}
	/* We have no further use for this array of KNL node ids, so free it. */
	if (arr_nodes) {
		free(arr_nodes);
		arr_nodes = NULL;
	}

	return 0;

bad_vnl:
	snprintf(log_buffer, sizeof(log_buffer), "creation of cray vnodes failed at %ld, with name %s", order, name);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  __func__, log_buffer);
	/*
	 * don't free nv since it might be importaint in the dump
	 */
	abort();
}

/**
 * @brief
 * 	Destructor function for BASIL processor allocation structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_processor_allocation(basil_processor_allocation_t *p)
{
	if (!p)
		return;
	free_basil_processor_allocation(p->next);
	free(p);
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL processor structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_processor(basil_node_processor_t *p)
{
	if (!p)
		return;
	free_basil_processor(p->next);
	free_basil_processor_allocation(p->allocations);
	free(p);
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL memory allocation structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_memory_allocation(basil_memory_allocation_t *p)
{
	if (!p)
		return;
	free_basil_memory_allocation(p->next);
	free(p);
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL memory structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_memory(basil_node_memory_t *p)
{
	if (!p)
		return;
	free_basil_memory(p->next);
	free_basil_memory_allocation(p->allocations);
	free(p);
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL label structure.

 * @param p structure to free
 */
static void
free_basil_label(basil_label_t *p)
{
	if (!p)
		return;
	free_basil_label(p->next);
	free(p);
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL accelerator gpu structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_accelerator_gpu(basil_accelerator_gpu_t *p)
{
	if (!p)
		return;
	if (p->family)
		free(p->family);
	free(p);
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL accelerator allocation structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_accelerator_allocation(basil_accelerator_allocation_t *p)
{
	if (!p)
		return;
	free_basil_accelerator_allocation(p->next);
	free(p);
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL accelerator structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_accelerator(basil_node_accelerator_t *p)
{
	if (!p)
		return;
	free_basil_accelerator(p->next);
	free_basil_accelerator_allocation(p->allocations);
	free_basil_accelerator_gpu(p->data.gpu);
	free(p);
	return;
}

/**
 * @brief
 * Destructor function for BASIL computeunit structure
 * @param p structure to free
 */
static void
free_basil_computeunit(basil_node_computeunit_t *p)
{
	if (!p)
		return;
	free_basil_computeunit(p->next);
	free(p);
}

/**
 * @brief
 *	Destructor function for BASIL node segment structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_segment(basil_node_segment_t *p)
{
	if (!p)
		return;
	free_basil_segment(p->next);
	free_basil_processor(p->processors);
	free_basil_memory(p->memory);
	free_basil_label(p->labels);
	free_basil_computeunit(p->computeunits);
	free(p);
}

/**
 * @brief
 * Destructor function for BASIL socket structure
 * @param p structure to free
 */
static void
free_basil_socket(basil_node_socket_t *p)
{
	if (!p)
		return;
	free_basil_socket(p->next);
	free_basil_segment(p->segments);
	free(p);
}

/**
 * @brief
 * Destructor function for BASIL node structure.
 * @param p structure to free
 */
static void
free_basil_node(basil_node_t *p)
{
	if (!p)
		return;
	free_basil_node(p->next);
	free_basil_segment(p->segments);
	free_basil_accelerator(p->accelerators);
	free_basil_socket(p->sockets);
	free(p);
}

/**
 * @brief
 * Destructor function for BASIL System element structure.
 * @param p linked list of structures to free.
 */
static void
free_basil_elements_KNL(basil_system_element_t *p)
{
	basil_system_element_t *nxtp;
	if (!p)
		return;
	nxtp = p->next;
	if (p->nidlist)
		free(p->nidlist);
	free(p);
	free_basil_elements_KNL(nxtp);
}

/**
 * @brief
 * 	Destructor function for BASIL reservation structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
free_basil_rsvn(basil_rsvn_t *p)
{
	if (!p)
		return;
	free_basil_rsvn(p->next);
	free(p);
}

/**
 * @brief
 * Destructor function for BASIL query status reservation structure.
 * @param p structure to free
 */
static void
free_basil_query_status_res(basil_response_query_status_res_t *p)
{
	if (!p)
		return;
	free_basil_query_status_res(p->next);
	free(p);
}

/**
 * @brief
 * Destructor function for BASIL response structure.

 * @param brp structure to free.
 *
 * @return Void
 */
static void
free_basil_response_data(basil_response_t *brp)
{
	if (!brp)
		return;
	if (brp->method == basil_method_query) {
		if (brp->data.query.type == basil_query_inventory) {
			free_basil_node(brp->data.query.data.inventory.nodes);
			free_basil_rsvn(brp->data.query.data.inventory.rsvns);
		} else if (brp->data.query.type == basil_query_system) {
			free_basil_elements_KNL(brp->data.query.data.system.elements);
		} else if (brp->data.query.type == basil_query_engine) {
			if (brp->data.query.data.engine.name)
				free(brp->data.query.data.engine.name);
			if (brp->data.query.data.engine.version)
				free(brp->data.query.data.engine.version);
			if (brp->data.query.data.engine.basil_support)
				free(brp->data.query.data.engine.basil_support);
		} else if (brp->data.query.type == basil_query_status) {
			free_basil_query_status_res(brp->data.query.data.status.reservation);
		}
	}
	free(brp);
}

/**
 * @brief
 * 	The child side of the request handler that invokes the ALPS client.
 *
 * Setup stdin to map to infd and stdout to map to outfd. Once that is
 * done, call exec to run the ALPS client.
 *
 * @param[in] infd input file descriptor
 * @param[in] outfd output file descriptor
 *
 * @return exit value of ALPS client
 * @retval 127 failure to setup exec of ALPS client
 */
static int
alps_request_child(int infd, int outfd)
{
	char *p;
	int rc = 0;
	int in = 0;
	int out = 0;

	in = infd;
	out = outfd;
	if (in != STDIN_FILENO) {
		if (out == STDIN_FILENO) {
			rc = dup(out);
			if (rc == -1) {
				sprintf(log_buffer, "dup() of out failed: %s",
					strerror(errno));
				log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
					  LOG_NOTICE, __func__, log_buffer);
				_exit(127);
			}
			close(out);
			out = rc;
		}
		rc = dup2(in, STDIN_FILENO);
		if (rc == -1) {
			sprintf(log_buffer, "dup2() of in failed: %s",
				strerror(errno));
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
				  LOG_NOTICE, __func__, log_buffer);
			_exit(127);
		}
		close(in);
	}
	if (out != STDOUT_FILENO) {
		rc = dup2(out, STDOUT_FILENO);
		if (rc == -1) {
			sprintf(log_buffer, "dup2() of out failed: %s",
				strerror(errno));
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
				  LOG_NOTICE, __func__, log_buffer);
			_exit(127);
		}
		close(out);
	}
	rc = open("/dev/null", O_WRONLY);
	if (rc != -1)
		dup2(rc, STDERR_FILENO);

	rc = fcntl(STDIN_FILENO, F_GETFD);
	if (rc == -1)
		_exit(127);
	rc = fcntl(STDIN_FILENO, F_SETFD, (rc & ~(FD_CLOEXEC)));
	if (rc == -1)
		_exit(127);
	rc = fcntl(STDOUT_FILENO, F_GETFD);
	if (rc == -1)
		_exit(127);
	rc = fcntl(STDOUT_FILENO, F_SETFD, (rc & ~(FD_CLOEXEC)));
	if (rc == -1)
		_exit(127);
	rc = fcntl(STDERR_FILENO, F_GETFD);
	if (rc == -1)
		_exit(127);
	rc = fcntl(STDERR_FILENO, F_SETFD, (rc & ~(FD_CLOEXEC)));
	if (rc == -1)
		_exit(127);

	if (!alps_client)
		_exit(127);
	p = strrchr(alps_client, '/');
	if (!p)
		_exit(127);
	p++;
	if (*p == '\0')
		_exit(127);
	log_close(0);
	if (execl(alps_client, p, NULL) < 0)
		_exit(127);
	exit(0);
}

/**
 * @brief
 * 	The parent side of the request handler that reads and parses the
 * 	XML response from the ALPS client (child side).
 *
 * Read the XML from the ALPS client and pass it to XML_Parse.
 * This is where the actual Expat (XML_) functions are called.
 * @param[in] fdin file descriptor to read XML stream from child
 * @param[in] basil_ver BASIL version indicates context i.e. did control
 *	      arrive at this function as a result of processing the
 *	      Inventory Query or System Query
 * @return pointer to filled in response structure
 * @retval NULL no result
 *
 */
static basil_response_t *
alps_request_parent(int fdin, char *basil_ver)
{
	ud_t ud;
	basil_response_t *brp;
	FILE *in = NULL;
	int status = 0;
	int eof = 0;
	int inventory_size = 0;

	in = fdopen(fdin, "r");
	if (!in) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Failed to open read FD.");
		return NULL;
	}
	memset(&ud, 0, sizeof(ud));
	brp = malloc(sizeof(basil_response_t));
	if (!brp) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Failed to allocate response structure.");
		return NULL;
	}
	memset(brp, 0, sizeof(basil_response_t));
	ud.brp = brp;
	parser = XML_ParserCreate(NULL);
	if (!parser) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Failed to create parser.");
		free_basil_response_data(brp);
		return NULL;
	}
	XML_SetUserData(parser, (void *) &ud);
	XML_SetElementHandler(parser, parse_element_start, parse_element_end);
	XML_SetCharacterDataHandler(parser, parse_char_data);

	if (alps_client_out != NULL)
		free(alps_client_out);
	if ((alps_client_out = strdup(NODE_TOPOLOGY_TYPE_CRAY)) == NULL) {
		sprintf(log_buffer, "failed to allocate client output buffer");
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE, LOG_ERR,
			  __func__, log_buffer);
		free_basil_response_data(brp);
		return NULL;
	} else
		inventory_size = strlen(alps_client_out) + 1;

	if (basil_ver != NULL)
		pbs_strncpy(ud.basil_ver, basil_ver, BASIL_STRING_SHORT);
	else
		pbs_strncpy(ud.basil_ver, BASIL_VAL_UNKNOWN, BASIL_STRING_SHORT);
	ud.basil_ver[BASIL_STRING_SHORT - 1] = '\0';

	do {
		int rc = 0;
		int len = 0;
		expatBuffer[0] = '\0';
		len = fread(expatBuffer, sizeof(char),
			    (EXPAT_BUFFER_LEN - 1), in);
		rc = ferror(in);
		if (rc) {
			if (len == 0) {
				clearerr(in);
				usleep(100);
				continue;
			}
			sprintf(log_buffer,
				"Read error on stream: rc=%d, len=%d",
				rc, len);
			log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
				  LOG_NOTICE, __func__, log_buffer);
			break;
		}
		*(expatBuffer + len) = '\0';
		if (pbs_strcat(&alps_client_out, &inventory_size,
			       expatBuffer) == NULL) {
			sprintf(log_buffer, "failed to save client response");
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE, LOG_ERR,
				  __func__, log_buffer);
			free(alps_client_out);
			alps_client_out = NULL;
			break;
		}
		eof = feof(in);
		status = XML_Parse(parser, expatBuffer, len, eof);
		if (status == XML_STATUS_ERROR) {
			sprintf(ud.error_class, "%s", BASIL_VAL_PERMANENT);
			sprintf(ud.error_source, "%s", BASIL_VAL_PARSER);
			sprintf(ud.message, "%s",
				XML_ErrorString(XML_GetErrorCode(parser)));
			break;
		}
	} while (!eof);
	fclose(in);

	if (*ud.error_class || *ud.error_source) {
		sprintf(log_buffer, "%s BASIL error from %s: %s",
			ud.error_class, ud.error_source, ud.message);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE,
			  __func__, log_buffer);
		snprintf(brp->error, BASIL_ERROR_BUFFER_SIZE, ud.message);
		if (strcmp(BASIL_VAL_PARSER, ud.error_source) == 0) {
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__, "XML buffer: ");
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
				  LOG_DEBUG, __func__, expatBuffer);
		}
	}
	XML_ParserFree(parser);
	return (brp);
}

/**
 * @brief
 * 	The front-end function for all ALPS requests that calls the
 * 	appropriate subordinate functions to issue the request (child) and
 * 	parse the response (parent).
 *
 * Setup pipes and call fork so the ALPS client can be run and send its
 * stdout to be read by the parent.
 *
 * @param[in] msg XML message to send to ALPS client
 * @param[in] basil_ver BASIL version indicates context i.e. did control
 *	      arrive at this function as a result of processing the
 *	      Inventory Query or System Query.
 * @return pointer to filled in response structure
 * @retval NULL no result
 *
 */
static basil_response_t *
alps_request(char *msg, char *basil_ver)
{
	int toChild[2];
	int fromChild[2];
	int status = 0;
	pid_t pid;
	pid_t exited;
	size_t msglen = 0;
	size_t wlen = -1;
	basil_response_t *brp = NULL;
	FILE *fp = NULL;

	if (!alps_client) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "No alps_client specified in MOM configuration file.");
		return NULL;
	}
	if (!msg) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			  __func__, "No message parameter for method.");
		return NULL;
	}
	msglen = strlen(msg);
	if (msglen < 32) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			  __func__, "ALPS request too short.");
		return NULL;
	}
	snprintf(log_buffer, sizeof(log_buffer),
		 "Sending ALPS request: %s", msg);
	log_event(PBSEVENT_DEBUG2, 0, LOG_DEBUG, __func__, log_buffer);
	if (pipe(toChild) == -1)
		return NULL;
	if (pipe(fromChild) == -1) {
		(void) close(toChild[0]);
		(void) close(toChild[1]);
		return NULL;
	}

	pid = fork();
	if (pid < 0) {
		log_err(errno, __func__, "fork");
		(void) close(toChild[0]);
		(void) close(toChild[1]);
		(void) close(fromChild[0]);
		(void) close(fromChild[1]);
		return NULL;
	}
	if (pid == 0) {
		close(toChild[1]);
		close(fromChild[0]);
		alps_request_child(toChild[0], fromChild[1]);
		exit(1);
	}
	close(toChild[0]);
	close(fromChild[1]);
	fp = fdopen(toChild[1], "w");
	if (fp == NULL) {
		sprintf(log_buffer, "fdopen() failed: %s", strerror(errno));
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE,
			  __func__, log_buffer);
		kill(pid, SIGKILL); /* don't let child run */
		goto done;
	}

	wlen = fwrite(msg, sizeof(char), msglen, fp);
	if (wlen < msglen) {
		log_err(errno, __func__, "fwrite");
		fclose(fp);
		kill(pid, SIGKILL); /* don't let child run */
		goto done;
	}

	if (fflush(fp) != 0) {
		log_err(errno, __func__, "fflush");
		fclose(fp);
		kill(pid, SIGKILL); /* don't let child run */
		goto done;
	}

	fclose(fp);
	if ((brp = alps_request_parent(fromChild[0], basil_ver)) == NULL) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
			  "No response from ALPS.");
	}

done:
	exited = waitpid(pid, &status, 0);
	/*
	 * If the wait fails or the process did not exit with 0,
	 * generate a message.
	 */
	if ((exited == -1) || (!WIFEXITED(status)) ||
	    (WEXITSTATUS(status) != 0)) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
			  "BASIL query process exited abnormally.");
	}

	close(toChild[1]);
	close(fromChild[0]);
	return (brp);
}

/**
 * @brief
 * 	Destructor function for BASIL memory parameter structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
alps_free_memory_param(basil_memory_param_t *p)
{
	if (!p)
		return;
	alps_free_memory_param(p->next);
	free(p);
}

/**
 * @brief
 * 	Destructor function for BASIL label parameter structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
alps_free_label_param(basil_label_param_t *p)
{
	if (!p)
		return;
	alps_free_label_param(p->next);
	free(p);
}

/**
 * @brief
 * 	Destructor function for BASIL node list parameter structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
alps_free_nodelist_param(basil_nodelist_param_t *p)
{
	if (!p)
		return;
	alps_free_nodelist_param(p->next);
	if (p->nodelist)
		free(p->nodelist);
	free(p);
}

/**
 * @brief
 * 	Destructor function for BASIL accelerator parameter structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
alps_free_accelerator_param(basil_accelerator_param_t *p)
{
	if (!p)
		return;
	alps_free_accelerator_param(p->next);
	free_basil_accelerator_gpu(p->data.gpu);
	free(p);
}

/**
 * @brief
 * 	Destructor function for BASIL parameter structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
static void
alps_free_param(basil_reserve_param_t *p)
{
	if (!p)
		return;
	alps_free_param(p->next);
	alps_free_memory_param(p->memory);
	alps_free_label_param(p->labels);
	alps_free_nodelist_param(p->nodelists);
	alps_free_accelerator_param(p->accelerators);
	free(p);
}

/**
 * @brief
 * 	Destructor function for BASIL reservation request structure.
 *
 * @param p structure to free
 *
 * @return Void
 *
 */
void
alps_free_reserve_request(basil_request_reserve_t *p)
{
	if (!p)
		return;
	alps_free_param(p->params);
	free(p);
	return;
}

/**
 * Information to remember for each vnode in the exec_vnode for a job.
 * The vnode are combined by alps_create_reserve_request() to form
 * the ALPS reservation.
 */
typedef struct nodesum {
	char *name;
	char *vntype;
	char *arch;
	long nid;
	long mpiprocs;
	long ncpus;
	long threads;
	long long mem;
	long chunks;
	long width;
	long depth;
	enum vnode_sharing_state share;
	int naccels;
	int need_accel;
	char *accel_model;
	long long accel_mem;
	int done;
} nodesum_t;

/**
 * @brief
 * Given a pointer to a PBS job (pjob), validate and construct a BASIL
 * reservation request.
 *
 * A loop goes through each element of the ji_vnods array for the job and
 * looks for entries that have cpus, the name matches mpphost, vntype is
 * CRAY_COMPUTE, and has a value for arch. Each of these entries causes
 * an entry to be made in the nodes array. If no vnodes are matched,
 * we can return since no compute nodes are being allocated.
 *
 * An error check is done to be sure no entries in the nodes array have
 * a bad combination of ncpus and mpiprocs. Then, a double loop is
 * entered that goes through each element of the of the nodes array
 * looking for matching entries. A match is when depth, width, mem,
 * share, arch, need_accel, accelerator_model and accelerator_mem are
 * all the same. All matches will be output to
 * a single ReserveParam XML section. Each node array entry that
 * is represented in an ReserveParam section is marked done so it
 * can be skipped as the loops run through the entries.
 *
 * @param[in] job PBS job
 * @param[out] req resulting completed request structure (NULL on error)
 *
 * @retval 0 success
 * @retval 1 failure
 * @retval 2 requeue job
 *
 */
int
alps_create_reserve_request(job *pjob, basil_request_reserve_t **req)
{
	basil_request_reserve_t *basil_req;
	basil_reserve_param_t *pend;
	enum rlplace_value rpv;
	enum vnode_sharing vnsv;
	struct passwd *pwent;
	int i = 0;
	int j = 0;
	int num = 0;
	int err_ret = 1;
	nodesum_t *nodes;
	vmpiprocs *vp;
	size_t len = 0;
	size_t nsize = 0;
	char *cp;
	long pstate = 0;
	char *pgov = NULL;
	char *pname = NULL;
	resource *pres;

	*req = NULL;

	nodes = (nodesum_t *) calloc(pjob->ji_numvnod, sizeof(nodesum_t));
	if (nodes == NULL)
		return 1;

	rpv = getplacesharing(pjob);

	/*
	 * Go through the vnodes to consolidate the mpi ranks onto
	 * the compute nodes. The index into ji_vnods will be
	 * incremented by the value of vn_mpiprocs because the
	 * entries in ji_vnods are replicated for each mpi rank.
	 */
	num = 0;
	len = strlen(mpphost);
	for (i = 0; i < pjob->ji_numvnod; i += vp->vn_mpiprocs) {
		vnal_t *vnp;
		char *vntype, *vnt;
		char *sharing;
		long nid;
		int seg;
		long long mem;
		char *arch;
		enum vnode_sharing_state share;
		vp = &pjob->ji_vnods[i];

		assert(vp->vn_mpiprocs > 0);
		if (vp->vn_cpus == 0)
			continue;

		/*
		 * Only match vnodes that begin with mpphost and have
		 * a following "_<num>_<num>" (when
		 * vnode_per_numa_node is true) otherwise,
		 * just plain "_<num>"..
		 */
		if (strncmp(vp->vn_vname, mpphost, len) != 0)
			continue;
		cp = &vp->vn_vname[len];
		if (vnode_per_numa_node) {
			if (sscanf(cp, "_%ld_%d", &nid, &seg) != 2)
				continue;
		} else {
			if (sscanf(cp, "_%ld", &nid) != 1)
				continue;
		}

		/* check that vnode exists */
		vnp = vn_vnode(vnlp, vp->vn_vname);
		if (vnp == NULL) {
			sprintf(log_buffer, "vnode %s does not exist",
				vp->vn_vname);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
				  LOG_DEBUG, pjob->ji_qs.ji_jobid,
				  log_buffer);
			free(nodes);
			return 2;
		}

		/* see if this is a compute node */
		vntype = attr_exist(vnp, "resources_available.vntype");
		if (vntype == NULL) {
			sprintf(log_buffer, "vnode %s has no vntype value",
				vp->vn_vname);
			log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB,
				  LOG_DEBUG, pjob->ji_qs.ji_jobid,
				  log_buffer);
			continue;
		}
		/*
		 * Check string array to be sure CRAY_COMPUTE is
		 * one of the values.
		 */
		for (vnt = parse_comma_string(vntype); vnt != NULL;
		     vnt = parse_comma_string(NULL)) {
			if (strcmp(vnt, CRAY_COMPUTE) == 0)
				break;
			sprintf(log_buffer, "vnode %s has vntype %s",
				vp->vn_vname, vnt);
			log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB,
				  LOG_DEBUG, pjob->ji_qs.ji_jobid,
				  log_buffer);
		}
		if (vnt == NULL) {
			sprintf(log_buffer, "vnode %s does not have vntype %s",
				vp->vn_vname, CRAY_COMPUTE);
			log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB,
				  LOG_DEBUG, pjob->ji_qs.ji_jobid,
				  log_buffer);
			continue;
		}

		arch = attr_exist(vnp, "resources_available.arch");
		if (arch == NULL) {
			sprintf(log_buffer, "vnode %s has no arch value",
				vp->vn_vname);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
				  LOG_DEBUG, pjob->ji_qs.ji_jobid,
				  log_buffer);
			free(nodes);
			return 2;
		}

		/* check legal values for arch */
		if (strcmp(BASIL_VAL_XT, arch) != 0 &&
		    strcmp(BASIL_VAL_X2, arch) != 0) {
			sprintf(log_buffer, "vnode %s has bad arch value %s",
				vp->vn_vname, arch);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
				  LOG_DEBUG, pjob->ji_qs.ji_jobid,
				  log_buffer);
			free(nodes);
			return 2;
		}

		/* rounded up value for size_mb which is memory per MPI rank */
		mem = (vp->vn_mem + vp->vn_mpiprocs - 1) / vp->vn_mpiprocs;
		sharing = attr_exist(vnp, "sharing");
		vnsv = str_to_vnode_sharing(sharing);
		share = vnss[vnsv][rpv];

		/*
		 ** If the vnode is in the array but is setup to use
		 ** different values for ncpus, mpiprocs etc, we need
		 ** to allocate another slot for it so a separate
		 ** ReserveParam XML section is created.
		 */
		for (j = 0; j < num; j++) {
			nodesum_t *ns = &nodes[j];

			if (ns->nid == nid && ns->share == share &&
			    ns->mpiprocs == vp->vn_mpiprocs &&
			    ns->ncpus == vp->vn_cpus &&
			    ns->threads == vp->vn_threads &&
			    ns->mem == mem &&
			    (strcmp(ns->arch, arch) == 0) &&
			    ns->need_accel == vp->vn_need_accel &&
			    ns->accel_mem == vp->vn_accel_mem) {
				if (ns->need_accel == 1) {
					/* If an accelerator is needed, check to
					 * see if the model has been set.
					 * Need a new XML block when the previous
					 * model doesn't match the current.
					 * Or if prev was set and current isn't,
					 * or vice versa.
					 */
					if (vp->vn_accel_model &&
					    ns->accel_model) {
						if (strcmp(ns->accel_model, vp->vn_accel_model) != 0) {
							continue;
						}
					} else if (!(vp->vn_accel_model == NULL &&
						     ns->accel_model == NULL)) {
						/* if both are NULL they match
						 * otherwise keep looking
						 */
						continue;
					}
				}
				ns->chunks++;
				break;
			}
		}
		if (j == num) { /* need a new entry */
			nodes[num].nid = nid;
			nodes[num].name = vp->vn_vname;
			nodes[num].mpiprocs = vp->vn_mpiprocs;
			nodes[num].ncpus = vp->vn_cpus;
			nodes[num].threads = vp->vn_threads;
			nodes[num].mem = mem;
			nodes[num].naccels = vp->vn_naccels;
			nodes[num].need_accel = vp->vn_need_accel;
			if (nodes[num].need_accel) {
				if (vp->vn_accel_mem) {
					nodes[num].accel_mem = vp->vn_accel_mem;
				}
				if (vp->vn_accel_model) {
					nodes[num].accel_model = vp->vn_accel_model;
				}
			}
			nodes[num].vntype = vntype;
			nodes[num].arch = arch;
			nodes[num].share = share;
			nodes[num++].chunks = 1;
		}
	}
	if (num == 0) { /* no compute nodes -> no reservation */
		free(nodes);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
			  LOG_DEBUG, pjob->ji_qs.ji_jobid,
			  "no ALPS reservation created: "
			  "no compute nodes allocated");
		return 0;
	}

	basil_req = malloc(sizeof(basil_request_reserve_t));
	if (!basil_req)
		return 1;
	memset(basil_req, 0, sizeof(basil_request_reserve_t));

	pwent = getpwuid(pjob->ji_qs.ji_un.ji_momt.ji_exuid);
	if (!pwent)
		goto err;
	sprintf(basil_req->user_name, "%s", pwent->pw_name);

	pbs_strncpy(basil_req->batch_id, pjob->ji_qs.ji_jobid,
		    sizeof(basil_req->batch_id));

	/* check for pstate or pgov */
	for (pres = (resource *) GET_NEXT(get_jattr_list(pjob, JOB_ATR_resource));
	     pres != NULL;
	     pres = (resource *) GET_NEXT(pres->rs_link)) {

		if ((pstate > 0) && (pgov != NULL))
			break;

		if (pres->rs_defin == NULL)
			continue;
		pname = pres->rs_defin->rs_name;
		if (pname == NULL)
			continue;

		if (strcmp(pname, "pstate") == 0) {
			pstate = atol(pres->rs_value.at_val.at_str);
			if (pstate <= 0) {
				snprintf(log_buffer, sizeof(log_buffer),
					 "pstate value \"%s\" could not be used for the reservation",
					 pres->rs_value.at_val.at_str);
				log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
					  LOG_DEBUG, pjob->ji_qs.ji_jobid, log_buffer);
				pstate = 0;
			}
			continue;
		}
		if (strcmp(pname, "pgov") == 0) {
			pgov = pres->rs_value.at_val.at_str;
			continue;
		}
	}

	for (i = 0; i < num; i++) {
		nodesum_t *ns = &nodes[i];

		/*
		 * ALPS cannot represent situations where a thread
		 * or process does not have a cpu allocated.
		 */
		if ((ns->ncpus % ns->mpiprocs) != 0)
			goto err;

		ns->width = ns->mpiprocs * ns->chunks;
		ns->depth = ns->ncpus / ns->mpiprocs;
	}

	pend = NULL;

	for (i = 0; i < num; i++) {
		basil_reserve_param_t *p;
		basil_nodelist_param_t *n;
		basil_accelerator_param_t *a;
		basil_accelerator_gpu_t *gpu;
		nodesum_t *ns = &nodes[i];
		char *arch = ns->arch;
		long long mem = ns->mem;
		char *accel_model = ns->accel_model;
		long long accel_mem = ns->accel_mem;
		long width;
		long last_nid, prev_nid;

		if (ns->done) /* already output */
			continue;

		p = malloc(sizeof(basil_reserve_param_t));
		if (p == NULL)
			goto err;

		memset(p, 0, sizeof(*p));
		if (pend == NULL)
			basil_req->params = p;
		else
			pend->next = p;
		pend = p;

		n = malloc(sizeof(basil_nodelist_param_t));
		if (n == NULL)
			goto err;

		memset(n, 0, sizeof(*n));
		p->nodelists = n;

		nsize = BASIL_STRING_LONG;
		n->nodelist = malloc(nsize);
		if (n->nodelist == NULL)
			goto err;

		sprintf(n->nodelist, "%ld", ns->nid);
		last_nid = prev_nid = ns->nid;

		p->depth = ns->depth;
		p->nppn = width = ns->width;

		/*
		 * If the user requested place=excl then we need to pass
		 * that information into the ALPS reservation.
		 */
		p->rsvn_mode = basil_rsvn_mode_none; /* initialize it */
		if (rpv == rlplace_excl) {
			/*
			 * The user asked for the node exclusively.
			 * Set it in the ALPS reservation.
			 */
			p->rsvn_mode = basil_rsvn_mode_exclusive;
		}
		if (ns->ncpus != ns->threads) {
			sprintf(log_buffer, "ompthreads %ld does not match"
					    " ncpus %ld",
				ns->threads, ns->ncpus);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
				  LOG_DEBUG, pjob->ji_qs.ji_jobid,
				  log_buffer);
		}

		/*
		 * Collapse matching entries.
		 */
		for (j = i + 1; j < num; j++) {
			nodesum_t *ns2 = &nodes[j];

			/* Look for matching nid entries that have not
			 * yet been output.
			 */
			if (ns2->done)
				continue;

			/* If everthing matches, add in this entry
			 * and mark it done.
			 */
			if (ns2->depth != ns->depth)
				continue;
			if (ns2->width != ns->width)
				continue;
			if (ns2->mem != ns->mem)
				continue;
			if (ns2->share != ns->share)
				continue;
			if (strcmp(ns2->arch, arch) != 0)
				continue;
			if (ns2->need_accel != ns->need_accel)
				continue;
			if (ns2->accel_mem != accel_mem)
				continue;
			if (ns->need_accel == 1) {
				if (accel_model &&
				    ns2->accel_model) {
					if (strcmp(ns2->accel_model, accel_model) != 0) {
						continue;
					}
				} else if (!(accel_model == NULL &&
					     ns2->accel_model == NULL)) {
					continue;
				}
			}

			width += ns2->width;
			ns2->done = 1;

			/*
			 * See if we can use a range of nid numbers.
			 */
			if (ns2->nid == (prev_nid + 1)) {
				prev_nid = ns2->nid;
				continue;
			}

			if (last_nid == prev_nid) /* no range */
				sprintf(utilBuffer, ",%ld", ns2->nid);
			else {
				sprintf(utilBuffer, "-%ld,%ld",
					prev_nid, ns2->nid);
			}
			prev_nid = last_nid = ns2->nid;

			/* check to see if we need to get a new nodelist */
			if (strlen(utilBuffer) + 1 >
			    nsize - strlen(n->nodelist)) {
				char *hold;

				nsize *= 2; /* double size */
				hold = realloc(n->nodelist, nsize);
				if (hold == NULL)
					goto err;
				n->nodelist = hold;
			}
			/* this is safe since we checked for overflow */
			strcat(n->nodelist, utilBuffer);
		}
		p->width = width;
		if (last_nid < prev_nid) { /* last range */
			size_t slen;

			sprintf(utilBuffer, "-%ld", prev_nid);
			slen = strlen(utilBuffer) + 1;

			/* check to see if we need to get a new nodelist */
			if (slen > nsize - strlen(n->nodelist)) {
				char *hold;

				nsize += slen + 1;
				hold = realloc(n->nodelist, nsize);
				if (hold == NULL)
					goto err;
				n->nodelist = hold;
			}
			/* this is safe since we checked for overflow */
			strcat(n->nodelist, utilBuffer);
		}

		if (mem > 0) {
			p->memory = malloc(sizeof(basil_memory_param_t));
			if (p->memory == NULL)
				goto err;
			memset(p->memory, 0, sizeof(basil_memory_param_t));
			p->memory->size_mb = (long) ((mem + 1023) / 1024);
			p->memory->type = basil_memory_type_os;
		}
		/*
		 * We don't include checking for ns->naccels here because
		 * ALPS is currently unable to accept a specified count
		 * of accelerators. Also ALPS currently needs a width
		 * to be requested on every node, so an accelerator cannot
		 * be the only thing requested on a node.
		 */
		if (ns->need_accel) {
			a = malloc(sizeof(basil_accelerator_param_t));
			if (a == NULL)
				goto err;
			memset(a, 0, sizeof(*a));
			a->type = basil_accel_gpu;
			p->accelerators = a;
			if (accel_model || (accel_mem > 0)) {
				gpu = malloc(sizeof(basil_accelerator_gpu_t));
				if (gpu == NULL)
					goto err;
				memset(gpu, 0, sizeof(basil_accelerator_gpu_t));
				a->data.gpu = gpu;
				if (accel_model) {
					gpu->family = strdup(accel_model);
					if (gpu->family == NULL)
						goto err;
				}
				if (accel_mem > 0) {
					/* ALPS expects MB */
					gpu->memory = (unsigned int) ((accel_mem + 1023) / 1024);
				}
			}
		}
		if (strcmp(BASIL_VAL_XT, arch) == 0) {
			p->arch = basil_node_arch_xt;
		} else if (strcmp(BASIL_VAL_X2, arch) == 0) {
			p->arch = basil_node_arch_x2;
		}
		if (pstate > 0) {
			p->pstate = pstate;
		}
		if (pgov != NULL) {
			if (strlen(pgov) < sizeof(p->pgovernor)) {
				pbs_strncpy(p->pgovernor, pgov, sizeof(p->pgovernor));
			} else {
				sprintf(log_buffer, "pgov value %s is too long,"
						    " length must be less than %ld",
					pgov, sizeof(p->pgovernor));
				log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
					  LOG_DEBUG, pjob->ji_qs.ji_jobid,
					  log_buffer);
			}
		}
	}
	*req = basil_req;
	free(nodes);
	return 0;

err:
	free(nodes);
	alps_free_reserve_request(basil_req);
	return err_ret;
}

/**
 * @brief
 * 	Issue a request to create a reservation on behalf of a user.
 *
 * Called during job initialization.
 *
 * @param[in] bresvp - pointer to the reserve request
 * @param[out] rsvn_id - reservation ID
 * @param pagg - unused
 *
 * @retval 0 success
 * @retval 1 transient error (retry)
 * @retval -1 fatal error
 *
 */
int
alps_create_reservation(basil_request_reserve_t *bresvp, long *rsvn_id,
			unsigned long long *pagg)
{
	basil_reserve_param_t *param;
	basil_memory_param_t *mem;
	basil_label_param_t *label;
	basil_nodelist_param_t *nl;
	basil_accelerator_param_t *accel;
	basil_response_t *brp;

	if (!bresvp) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Cannot create ALPS reservation, missing data.");
		return (-1);
	}
	if (*bresvp->user_name == '\0') {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Cannot create ALPS reservation, missing user name.");
		return (-1);
	}
	if (!bresvp->params) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Cannot create ALPS reservation, missing parameters.");
		return (-1);
	}
	new_alps_req();
	sprintf(utilBuffer, "<?xml version=\"1.0\"?>\n"
			    "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_RESERVE "\">\n",
		basilversion_inventory);
	add_alps_req(utilBuffer);
	sprintf(utilBuffer,
		" <" BASIL_ELM_RESVPARAMARRAY " " BASIL_ATR_USER_NAME "=\"%s\" " BASIL_ATR_BATCH_ID "=\"%s\"",
		bresvp->user_name, bresvp->batch_id);
	add_alps_req(utilBuffer);
	if (*bresvp->account_name != '\0') {
		sprintf(utilBuffer, " " BASIL_ATR_ACCOUNT_NAME "=\"%s\"",
			bresvp->account_name);
		add_alps_req(utilBuffer);
	}
	add_alps_req(">\n");
	for (param = bresvp->params; param; param = param->next) {
		add_alps_req("  <" BASIL_ELM_RESERVEPARAM);
		switch (param->arch) {
			case basil_node_arch_x2:
				add_alps_req(" " BASIL_ATR_ARCH "=\"" BASIL_VAL_X2 "\"");
				break;
			default:
				add_alps_req(" " BASIL_ATR_ARCH "=\"" BASIL_VAL_XT "\"");
				break;
		}
		if (param->width >= 0) {
			sprintf(utilBuffer, " " BASIL_ATR_WIDTH "=\"%ld\"",
				param->width);
			add_alps_req(utilBuffer);
		}
		/*
		 * Only output BASIL_ATR_RSVN_MODE if we are not talking
		 * to basil 1.1 orig.
		 */
		if (!basil11orig) {
			if (param->rsvn_mode == basil_rsvn_mode_exclusive) {
				add_alps_req(" " BASIL_ATR_RSVN_MODE "=\"" BASIL_VAL_EXCLUSIVE "\"");
			} else if (param->rsvn_mode == basil_rsvn_mode_shared) {
				add_alps_req(" " BASIL_ATR_RSVN_MODE "=\"" BASIL_VAL_SHARED "\"");
			}
		}
		if (param->depth >= 0) {
			sprintf(utilBuffer, " " BASIL_ATR_DEPTH "=\"%ld\"",
				param->depth);
			add_alps_req(utilBuffer);
		}
		if (param->nppn > 0) {
			sprintf(utilBuffer, " " BASIL_ATR_NPPN "=\"%ld\"",
				param->nppn);
			add_alps_req(utilBuffer);
		}
		if (param->pstate > 0) {
			sprintf(utilBuffer, " " BASIL_ATR_PSTATE "=\"%ld\"",
				param->pstate);
			add_alps_req(utilBuffer);
		}
		if (param->nppcu > 0) {
			sprintf(utilBuffer, " " BASIL_ATR_NPPCU "=\"0\"");
			add_alps_req(utilBuffer);
		}
		if (param->pgovernor[0] != '\0') {
			sprintf(utilBuffer, " " BASIL_ATR_PGOVERNOR "=\"%s\"",
				param->pgovernor);
			add_alps_req(utilBuffer);
		}
		if (vnode_per_numa_node && param->segments[0] != '\0') {
			sprintf(utilBuffer, " " BASIL_ATR_SEGMENTS "=\"%s\"",
				param->segments);
			add_alps_req(utilBuffer);
		}
		if (!param->memory && !param->labels && !param->nodelists) {
			add_alps_req("/>\n");
			continue;
		}
		add_alps_req(">\n");
		if (param->memory) {
			add_alps_req("   <" BASIL_ELM_MEMPARAMARRAY ">\n");
			for (mem = param->memory; mem; mem = mem->next) {
				add_alps_req("    <" BASIL_ELM_MEMPARAM " " BASIL_ATR_TYPE "=\"");
				switch (mem->type) {
					case basil_memory_type_hugepage:
						add_alps_req(BASIL_VAL_HUGEPAGE);
						break;
					case basil_memory_type_virtual:
						add_alps_req(BASIL_VAL_VIRTUAL);
						break;
					default:
						add_alps_req(BASIL_VAL_OS);
				}
				add_alps_req("\"");
				sprintf(utilBuffer,
					" " BASIL_ATR_SIZE_MB "=\"%ld\"",
					mem->size_mb);
				add_alps_req(utilBuffer);
				add_alps_req("/>\n");
			}
			add_alps_req("   </" BASIL_ELM_MEMPARAMARRAY ">\n");
		}
		if (param->labels) {
			add_alps_req("   <" BASIL_ELM_LABELPARAMARRAY ">\n");
			for (label = param->labels; label && *label->name;
			     label = label->next) {
				add_alps_req("    <" BASIL_ELM_LABELPARAM " " BASIL_ATR_NAME "=");
				sprintf(utilBuffer, "\"%s\"", label->name);
				add_alps_req(utilBuffer);
				add_alps_req(" " BASIL_ATR_TYPE "=");
				switch (label->type) {
					case basil_label_type_soft:
						sprintf(utilBuffer, "\"%s\"",
							BASIL_VAL_SOFT);
						break;
					default:
						sprintf(utilBuffer, "\"%s\"",
							BASIL_VAL_HARD);
				}
				add_alps_req(utilBuffer);
				add_alps_req(" " BASIL_ATR_DISPOSITION "=");
				switch (label->disposition) {
					case basil_label_disposition_repel:
						sprintf(utilBuffer, "\"%s\"",
							BASIL_VAL_REPEL);
						break;
					default:
						sprintf(utilBuffer, "\"%s\"",
							BASIL_VAL_ATTRACT);
				}
				add_alps_req(utilBuffer);
				add_alps_req("/>\n");
			}
			add_alps_req("   </" BASIL_ELM_LABELPARAMARRAY ">\n");
		}
		if (param->nodelists) {
			add_alps_req("   <" BASIL_ELM_NODEPARMARRAY ">\n");
			for (nl = param->nodelists;
			     nl && nl->nodelist && *nl->nodelist;
			     nl = nl->next) {
				add_alps_req("    <" BASIL_ELM_NODEPARAM ">");
				add_alps_req(nl->nodelist);
				add_alps_req("</" BASIL_ELM_NODEPARAM ">\n");
			}
			add_alps_req("   </" BASIL_ELM_NODEPARMARRAY ">\n");
		}
		if (param->accelerators) {
			add_alps_req("   <" BASIL_ELM_ACCELPARAMARRAY ">\n");
			for (accel = param->accelerators; accel;
			     accel = accel->next) {
				add_alps_req("    <" BASIL_ELM_ACCELPARAM " " BASIL_ATR_TYPE "=\"" BASIL_VAL_GPU "\"");
				if (accel->data.gpu) {
					if (accel->data.gpu->family) {
						sprintf(utilBuffer, " " BASIL_ATR_FAMILY "=\"%s\"",
							accel->data.gpu->family);
						add_alps_req(utilBuffer);
					}
					if (accel->data.gpu->memory > 0) {
						sprintf(utilBuffer, " " BASIL_ATR_MEMORY_MB "=\"%d\"",
							accel->data.gpu->memory);
						add_alps_req(utilBuffer);
					}
				}
				add_alps_req("/>\n");
			}
			add_alps_req("   </" BASIL_ELM_ACCELPARAMARRAY ">\n");
		}
		add_alps_req("  </" BASIL_ELM_RESERVEPARAM ">\n");
	}
	add_alps_req(" </" BASIL_ELM_RESVPARAMARRAY ">\n");
	add_alps_req("</" BASIL_ELM_REQUEST ">");
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
		  "Creating ALPS reservation for job.");
	if ((brp = alps_request(requestBuffer, basilversion_inventory)) == NULL) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Failed to create ALPS reservation.");
		return (-1);
	}
	if (*brp->error != '\0') {
		if (brp->error_flags & BASIL_ERR_TRANSIENT) {
			free_basil_response_data(brp);
			return (1);
		} else {
			free_basil_response_data(brp);
			return (-1);
		}
	}
	sprintf(log_buffer, "Created ALPS reservation %ld.",
		brp->data.reserve.rsvn_id);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  __func__, log_buffer);
	*rsvn_id = brp->data.reserve.rsvn_id;
	free_basil_response_data(brp);
	return (0);
}

/**
 * @brief
 * 	Issue a request to confirm an existing reservation.
 *
 * Called during job initialization.
 * Change from basil 1.0: admin_cookie is renamed to pagg_id
 * and alloc_cookie is deprecated as of 1.1.
 *
 * @param[in] pjob - pointer to job structure
 *
 * @retval 0 success
 * @retval 1 transient error (retry)
 * @retval -1 fatal error
 *
 */
int
alps_confirm_reservation(job *pjob)
{
	basil_response_t *brp;

	if (!pjob) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Cannot confirm ALPS reservation, invalid job.");
		return (-1);
	}
	/* Return success if no reservation present. */
	if (pjob->ji_extended.ji_ext.ji_reservation < 0) {
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid,
			  "No MPP reservation to confirm.");
		return (0);
	}
	if (pjob->ji_extended.ji_ext.ji_pagg == 0) {
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid,
			  "No PAGG to confirm MPP reservation.");
		return (1);
	}
	sprintf(log_buffer, "Confirming ALPS reservation %ld.",
		pjob->ji_extended.ji_ext.ji_reservation);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, log_buffer);
	new_alps_req();
	sprintf(requestBuffer, "<?xml version=\"1.0\"?>\n"
			       "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_CONFIRM "\" " BASIL_ATR_RSVN_ID "=\"%ld\" "
			       "%s =\"%llu\"/>",
		basilversion_inventory,
		pjob->ji_extended.ji_ext.ji_reservation,
		basil11orig ? BASIL_ATR_ADMIN_COOKIE : BASIL_ATR_PAGG_ID,
		pjob->ji_extended.ji_ext.ji_pagg);
	if ((brp = alps_request(requestBuffer, basilversion_inventory)) == NULL) {
		sprintf(log_buffer, "Failed to confirm ALPS reservation %ld.",
			pjob->ji_extended.ji_ext.ji_reservation);
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_NOTICE,
			  pjob->ji_qs.ji_jobid, log_buffer);
		return (-1);
	}
	if (*brp->error != '\0') {
		if (brp->error_flags & BASIL_ERR_TRANSIENT) {
			free_basil_response_data(brp);
			return (1);
		} else {
			free_basil_response_data(brp);
			return (-1);
		}
	}
	sprintf(log_buffer, "ALPS reservation confirmed.");
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, log_buffer);
	free_basil_response_data(brp);
	return (0);
}

/**
 * @brief
 * 	Issue a request to cancel an existing reservation.
 *
 * Called during job exit/cleanup.
 *
 * @param[in] pjob - pointer to job structure
 * @retval 0 success
 * @retval 1 transient error (retry)
 * @retval -1 fatal error
 *
 */
int
alps_cancel_reservation(job *pjob)
{
	char buf[1024];
	basil_response_t *brp;

	if (!pjob) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "Cannot cancel ALPS reservation, invalid job.");
		return (-1);
	}
	/* Return success if no reservation present. */
	if (pjob->ji_extended.ji_ext.ji_reservation < 0 ||
	    pjob->ji_extended.ji_ext.ji_pagg == 0) {
		return (0);
	}
	sprintf(log_buffer, "Canceling ALPS reservation %ld with PAGG %llu.",
		pjob->ji_extended.ji_ext.ji_reservation,
		pjob->ji_extended.ji_ext.ji_pagg);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, log_buffer);
	new_alps_req();
	sprintf(requestBuffer, "<?xml version=\"1.0\"?>\n"
			       "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_RELEASE "\" " BASIL_ATR_RSVN_ID "=\"%ld\" "
			       "%s =\"%llu\"/>",
		basilversion_inventory,
		pjob->ji_extended.ji_ext.ji_reservation,
		basil11orig ? BASIL_ATR_ADMIN_COOKIE : BASIL_ATR_PAGG_ID,
		pjob->ji_extended.ji_ext.ji_pagg);
	if ((brp = alps_request(requestBuffer, basilversion_inventory)) == NULL) {
		sprintf(log_buffer, "Failed to cancel ALPS reservation %ld.",
			pjob->ji_extended.ji_ext.ji_reservation);
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_NOTICE,
			  pjob->ji_qs.ji_jobid, log_buffer);
		return (-1);
	}
	if (*brp->error != '\0') {
		if (brp->error_flags & BASIL_ERR_TRANSIENT) {
			free_basil_response_data(brp);
			return (1);
		} else {
			/*
			 * check if it's a "No entry for resID"
			 * error message. If so, we will assume the ALPS
			 * reservation went away due to a prior release
			 * request and fall through to the successful exit
			 * If for some reason Cray changes this error string
			 * the behavior of PBS will be to continue to try to
			 * cancel the reservation (even though ALPS does not
			 * know about this reservation) and the job will
			 * remain in the "E" state until the
			 * alps_release_timeout time has elapsed.
			 */
			bzero(buf, sizeof(buf));
			snprintf(buf, sizeof(buf), "No entry for resId %ld",
				 pjob->ji_extended.ji_ext.ji_reservation);
			if (strstr(brp->error, buf) == NULL) {
				sprintf(log_buffer, "Failed to cancel ALPS "
						    "reservation %ld. BASIL response error: %s",
					pjob->ji_extended.ji_ext.ji_reservation,
					brp->error);
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB,
					  LOG_NOTICE, pjob->ji_qs.ji_jobid, log_buffer);
				free_basil_response_data(brp);
				return (-1);
			}
		}
	}

	/*
	 * There are still claims on the ALPS reservation, so just
	 * treat it like a transient error so we keep trying to
	 * release the ALPS reservation.
	 */
	if (brp->data.release.claims > 0) {
		sprintf(log_buffer, "ALPS reservation %ld has %u claims "
				    "against it",
			pjob->ji_extended.ji_ext.ji_reservation,
			brp->data.release.claims);
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, log_buffer);
		free_basil_response_data(brp);
		return (1);
	}

	sprintf(log_buffer, "ALPS reservation cancelled.");
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, log_buffer);
	free_basil_response_data(brp);
	return (0);
}

/**
 * @brief
 * Issue a request to switch an existing reservation "OUT" (suspend it)
 * or "IN" (resume it).
 *
 * Called by mother superior when a job needs to be suspended or resumed.
 *
 * @retval 0 success
 * @retval 1 transient error (retry)
 * @retval -1 fatal error
 */
int
alps_suspend_resume_reservation(job *pjob, basil_switch_action_t switchval)
{
	basil_response_t *brp;
	char actionstring[10] = "";
	char switch_buf[10] = "";

	if (switchval == basil_switch_action_out) {
		strcpy(switch_buf, "suspend");
		strcpy(actionstring, BASIL_VAL_OUT);
	} else if (switchval == basil_switch_action_in) {
		strcpy(switch_buf, "resume");
		strcpy(actionstring, BASIL_VAL_IN);
	} else {
		snprintf(log_buffer, sizeof(log_buffer),
			 "Invalid switch action %d.", switchval);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE,
			  (char *) __func__, log_buffer);
		return (-1);
	}

	if (!pjob) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "Cannot %s (%d), invalid job.", switch_buf, switchval);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE,
			  (char *) __func__, log_buffer);
		return (-1);
	}
	snprintf(log_buffer, sizeof(log_buffer),
		 "Switching ALPS reservation %ld to %s",
		 pjob->ji_extended.ji_ext.ji_reservation, switch_buf);
	log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, log_buffer);
	new_alps_req();
	snprintf(utilBuffer, sizeof(utilBuffer), "<?xml version=\"1.0\"?>\n"
						 "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_SWITCH "\">\n",
		 basilversion_inventory);
	add_alps_req(utilBuffer);
	add_alps_req(" <" BASIL_ELM_RSVNARRAY ">\n");
	snprintf(utilBuffer, sizeof(utilBuffer),
		 "  <" BASIL_ELM_RESERVATION " " BASIL_ATR_RSVN_ID "=\"%ld\" " BASIL_ATR_ACTION "=\"%s\"/>\n",
		 pjob->ji_extended.ji_ext.ji_reservation,
		 actionstring);
	add_alps_req(utilBuffer);
	add_alps_req(" </" BASIL_ELM_RSVNARRAY ">\n");
	add_alps_req("</" BASIL_ELM_REQUEST ">");
	if ((brp = alps_request(requestBuffer, basilversion_inventory)) == NULL) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "Failed to switch %s ALPS reservation.", actionstring);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE,
			  (char *) __func__, log_buffer);
		return (-1);
	}
	if (*brp->error != '\0') {
		/* A TRANSIENT error would mean the previous switch
		 * method had not completed
		 */
		if (brp->error_flags & BASIL_ERR_TRANSIENT) {
			free_basil_response_data(brp);
			brp = NULL;
			return (1);
		} else {
			free_basil_response_data(brp);
			brp = NULL;
			return (-1);
		}
	}
	log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_NODE, LOG_DEBUG,
		  (char *) __func__, "Made the ALPS SWITCH request.");
	free_basil_response_data(brp);
	return (0);
}

/**
 * @brief
 * Confirm that an ALPS reservation has been switched to either "SUSPEND"
 * or "RUN" status.
 * Confirm that an ALPS reservation has successfully finished switching in/out.
 *
 * @retval 0 success
 * @retval 1 transient error (retry)
 * @retval 2 transient error (retry) - When reservation is empty
 * @retval -1 fatal error
 */
int
alps_confirm_suspend_resume(job *pjob, basil_switch_action_t switchval)
{
	basil_response_t *brp = NULL;
	basil_response_query_status_res_t *res = NULL;

	if (!pjob) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_JOB, LOG_ERR, (char *) __func__,
			  "Cannot confirm ALPS reservation, invalid job.");
		return (-1);
	}
	/* If no reservation ID return an error */
	if (pjob->ji_extended.ji_ext.ji_reservation < 0) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_JOB, LOG_ERR,
			  pjob->ji_qs.ji_jobid,
			  "No ALPS reservation ID provided.  Can't confirm SWITCH status.");
		return (-1);
	}

	if ((switchval != basil_switch_action_out) &&
	    (switchval != basil_switch_action_in)) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "Invalid switch action %d.", switchval);
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_ERR,
			  (char *) __func__, log_buffer);
		return (-1);
	}

	sprintf(log_buffer, "Confirming ALPS reservation %ld SWITCH status.",
		pjob->ji_extended.ji_ext.ji_reservation);
	log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
		  pjob->ji_qs.ji_jobid, log_buffer);
	new_alps_req();
	sprintf(utilBuffer, "<?xml version=\"1.0\"?>\n"
			    "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" " BASIL_ATR_TYPE "=\"" BASIL_VAL_STATUS "\">\n",
		basilversion_inventory);
	add_alps_req(utilBuffer);
	add_alps_req(" <" BASIL_ELM_RSVNARRAY ">\n");
	sprintf(utilBuffer,
		"  <" BASIL_ELM_RESERVATION " " BASIL_ATR_RSVN_ID "=\"%ld\"/>\n",
		pjob->ji_extended.ji_ext.ji_reservation);
	add_alps_req(utilBuffer);
	add_alps_req(" </" BASIL_ELM_RSVNARRAY ">\n");
	add_alps_req("</" BASIL_ELM_REQUEST ">");

	if ((brp = alps_request(requestBuffer, basilversion_inventory)) == NULL) {
		sprintf(log_buffer, "Failed to confirm ALPS reservation %ld has been switched.",
			pjob->ji_extended.ji_ext.ji_reservation);
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_NOTICE,
			  pjob->ji_qs.ji_jobid, log_buffer);
		return (-1);
	}
	if (*brp->error != '\0') {
		if (brp->error_flags & BASIL_ERR_TRANSIENT) {
			free_basil_response_data(brp);
			return (1);
		} else {
			free_basil_response_data(brp);
			return (-1);
		}
	}

	/*
	 * Now check for status of the suspend/resume
	 * INVALID is considered a permanent error, just error out
	 */
	res = brp->data.query.data.status.reservation;
	if (res->status == basil_reservation_status_invalid) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "ALPS SWITCH status is = 'INVALID'");
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_NOTICE,
			  pjob->ji_qs.ji_jobid, log_buffer);
		free_basil_response_data(brp);
		return (-1);
	}

	/*
	 * The MIX, SWITCH and UNKNOWN status response types are considered
	 * transient, we will need to check the status again.
	 */
	if (res->status == basil_reservation_status_mix) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "ALPS SWITCH status is = 'MIX', keep checking "
			 "ALPS status.");
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, log_buffer);
		free_basil_response_data(brp);
		return (1);
	}
	if (res->status == basil_reservation_status_switch) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "ALPS SWITCH status is = 'SWITCH', keep checking "
			 "ALPS status.");
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, log_buffer);
		free_basil_response_data(brp);
		return (1);
	}
	if (res->status == basil_reservation_status_unknown) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "ALPS SWITCH status is = 'UNKNOWN', keep checking "
			 "ALPS status.");
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, log_buffer);
		free_basil_response_data(brp);
		return (1);
	}

	/* What we expect for status depends on whether we are trying to SWITCH IN or OUT */
	if (res->status == basil_reservation_status_run) {
		if (switchval == basil_switch_action_out) {
			/* We want to suspend the reservation's applications, so we
			 * need to keep checking status
			 */
			snprintf(log_buffer, sizeof(log_buffer),
				 "ALPS SWITCH status is 'RUN', and "
				 "'SUSPEND' was requested, keep checking "
				 "ALPS status.");
			log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
				  pjob->ji_qs.ji_jobid, log_buffer);
			free_basil_response_data(brp);
			return (1);
		} else {
			/* We are trying to run the application again, and it is running! */
			snprintf(log_buffer, sizeof(log_buffer),
				 "ALPS reservation %ld has been successfully "
				 "switched to 'RUN'.",
				 pjob->ji_extended.ji_ext.ji_reservation);
			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
				  pjob->ji_qs.ji_jobid, log_buffer);
			free_basil_response_data(brp);
			return (0);
		}
	}
	if (res->status == basil_reservation_status_suspend) {
		if (switchval == basil_switch_action_in) {
			/* We want to run the reservation's applications, so we
			 * need to keep checking status
			 */
			snprintf(log_buffer, sizeof(log_buffer),
				 "ALPS SWITCH status is 'SUSPEND', "
				 "and 'RUN' was requested, keep checking "
				 "ALPS status.");
			log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG,
				  pjob->ji_qs.ji_jobid, log_buffer);
			free_basil_response_data(brp);
			return (1);
		} else {
			/* We are trying to suspend the application, and it is! */
			snprintf(log_buffer, sizeof(log_buffer),
				 "ALPS reservation %ld has been successfully "
				 "switched to 'SUSPEND'.",
				 pjob->ji_extended.ji_ext.ji_reservation);
			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
				  pjob->ji_qs.ji_jobid, log_buffer);
			free_basil_response_data(brp);
			return (0);
		}
	}
	/*
	 * Due to a race condition in ALPS where ALPS wrongly returns "EMPTY"
	 * (which means no claim on the ALPS resv) when there may be a claim
	 * on the reservation, PBS must work around this by polling for status
	 * again when we get "EMPTY". Thus we will print at DEBUG2 level so
	 * we can be aware of how often the race condition is encountered.
	 */
	if ((res->status == basil_reservation_status_empty) &&
	    (switchval == basil_switch_action_out)) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "ALPS reservation %ld SWITCH status is = 'EMPTY'.",
			 pjob->ji_extended.ji_ext.ji_reservation);
		log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, log_buffer);
		free_basil_response_data(brp);
		return (2);
	}
	/* Getting the status of EMPTY while SWITCH IN (resume) means
	 * there was nothing to do, so consider the SWITCH done.
	 */
	if ((res->status == basil_reservation_status_empty) &&
	    (switchval == basil_switch_action_in)) {
		snprintf(log_buffer, sizeof(log_buffer),
			 "ALPS reservation %ld has been successfully switched.",
			 pjob->ji_extended.ji_ext.ji_reservation);
		log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
			  pjob->ji_qs.ji_jobid, log_buffer);
	}
	free_basil_response_data(brp);
	return (0);
}

/**
 * Issue an ENGINE query and determine which version of BASIL
 * we should use.
 */
static void
alps_engine_query(void)
{
	basil_response_t *brp = NULL;
	char *ver = NULL;
	char *tmp = NULL;
	int i = 0;
	int found_ver = 0;

	new_alps_req();
	for (i = 0; (pbs_supported_basil_versions[i] != NULL); i++) {
		sprintf(basilversion_inventory, pbs_supported_basil_versions[i]);
		sprintf(requestBuffer, "<?xml version=\"1.0\"?>\n"
				       "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" " BASIL_ATR_TYPE "=\"" BASIL_VAL_ENGINE "\"/>",
			basilversion_inventory);
		if ((brp = alps_request(requestBuffer, basilversion_inventory)) != NULL) {
			if (*brp->error == '\0') {
				/*
				 * There are no errors in the response data.
				 * Check the response method to ensure we have
				 * the correct response.
				 */
				if (brp->method == basil_method_query) {
					/* Check if 'basil_support' is set before trying to strdup.
					 * If basil_support is not set, it's likely
					 * CLE 2.2 which doesn't have 'basil_support' but we'll
					 * check that later.
					 */
					if (brp->data.query.data.engine.basil_support != NULL) {
						ver = strdup(brp->data.query.data.engine.basil_support);
						if (ver != NULL) {
							tmp = strtok(ver, ",");
							while (tmp) {
								if ((strcmp(basilversion_inventory, tmp)) == 0) {
									/* Success! We found a version to speak */
									sprintf(log_buffer, "The basilversion is "
											    "set to %s",
										basilversion_inventory);
									log_event(PBSEVENT_DEBUG,
										  PBS_EVENTCLASS_NODE,
										  LOG_DEBUG, __func__, log_buffer);
									found_ver = 1;
									break;
								}
								tmp = strtok(NULL, ",");
							}
							/* We didn't find the version we were looking for
							 * in basil_support, even though the engine query
	 						 * itself succeeded. Something is wrong.
	 						 */
							if (found_ver == 0) {
								sprintf(log_buffer, "ALPS ENGINE query failed. "
										    "Supported BASIL versions returned: "
										    "'%s'",
									ver);
								log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
									  LOG_NOTICE, __func__, log_buffer);
							}
						} else {
							/* No memory */
							sprintf(log_buffer, "ALPS ENGINE query failed. No "
									    "memory");
							log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE,
								  LOG_NOTICE, __func__, log_buffer);
						}
					} else {
						if ((strcmp(basilversion_inventory, BASIL_VAL_VERSION_1_1)) == 0) {
							/* basil_support isn't in the XML response
							 * and the XML wasn't junk, so
							 * assume CLE 2.2 is running.
							 */
							sprintf(log_buffer, "Assuming CLE 2.2 is running, "
									    "setting the basilversion to %s",
								basilversion_inventory);
							log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE,
								  LOG_DEBUG, __func__, log_buffer);
							sprintf(log_buffer, "The basilversion is "
									    "set to %s",
								basilversion_inventory);
							log_event(PBSEVENT_DEBUG,
								  PBS_EVENTCLASS_NODE,
								  LOG_DEBUG, __func__, log_buffer);
							found_ver = 1;
						}
					}
				} else {
					/* wrong method in the response */
					sprintf(log_buffer, "Wrong method, expected: %d but "
							    "got: %d",
						basil_method_query, brp->method);
					log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
						  LOG_DEBUG, __func__, log_buffer);
				}
			} else {
				/* There was an error in the BASIL response */
				sprintf(log_buffer, "Error in BASIL response: %s", brp->error);
				log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
					  __func__, log_buffer);
			}
		} else {
			sprintf(log_buffer, "ALPS ENGINE query failed with BASIL "
					    "version %s.",
				basilversion_inventory);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
				  LOG_NOTICE, __func__, log_buffer);
		}
		free(ver);
		ver = NULL;
		free_basil_response_data(brp);
		brp = NULL;
		if (found_ver != 0) {
			/* Found it, let's get outta here. */
			break;
		}
	}

	/*
	 * We didn't find the right BASIL version.
	 * Set basilversion to "UNDEFINED"
	 */
	if (found_ver == 0) {
		sprintf(basilversion_inventory, BASIL_VAL_UNDEFINED);
		sprintf(log_buffer, "No BASIL versions are understood.");
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
			  LOG_NOTICE, __func__, log_buffer);
	} else {
		/* we found a BASIL version that works
		 * Set basilver so the rest of the code can use switch
		 * statements to choose the appropriate code path
		 */
		if ((strcmp(basilversion_inventory, BASIL_VAL_VERSION_1_4)) == 0) {
			basilver = basil_1_4;
		} else if ((strcmp(basilversion_inventory, BASIL_VAL_VERSION_1_3)) == 0) {
			basilver = basil_1_3;
		} else if ((strcmp(basilversion_inventory, BASIL_VAL_VERSION_1_2)) == 0) {
			basilver = basil_1_2;
		} else if ((strcmp(basilversion_inventory, BASIL_VAL_VERSION_1_1)) == 0) {
			basilver = basil_1_1;
		}
	}
}

/**
 * @brief
 *	 Issue a request for a system inventory including nodes, CPUs, and
 * 	assigned applications.
 *
 * @return	int
 * @retval  0   : success
 * @retval  -1  : failure
 */
int
alps_inventory(void)
{
	int rc = 0;
	basil_response_t *brp;
	first_compute_node = 1;

	/* Determine what BASIL version we should speak */
	alps_engine_query();
	new_alps_req();
	sprintf(requestBuffer, "<?xml version=\"1.0\"?>\n"
			       "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" " BASIL_ATR_TYPE "=\"" BASIL_VAL_INVENTORY "\"/>",
		basilversion_inventory);
	if ((brp = alps_request(requestBuffer, basilversion_inventory)) == NULL) {
		sprintf(log_buffer, "ALPS inventory request failed.");
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
			  LOG_NOTICE, __func__, log_buffer);
		return -1;
	}
	if (basil_inventory != NULL)
		free(basil_inventory);
	basil_inventory = strdup(alps_client_out);
	if (basil_inventory == NULL) {
		sprintf(log_buffer, "failed to save inventory response");
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE, LOG_ERR,
			  __func__, log_buffer);
	}
	rc = inventory_to_vnodes(brp);
	free_basil_response_data(brp);
	return rc;
}

/**
 *
 * @brief System Query handling (for KNL Nodes).
 * 	  Invoked from dep_topology() in mom_mach.c before alps_inventory()
 * 	  (which handles processing for non-KNL Cray Compute Nodes) is called.
 *	  Checks if BASIL 1.7 is supported, then makes a System Query request and
 *	  populates System Query related structures.
 *
 * @return void
 *
 */
void
alps_system_KNL(void)
{
	/*
	 * Determine if ALPS supports the BASIL 1.7 protocol. We are only
	 * partially supporting the BASIL 1.7 protocol (for the System Query).
	 */
	alps_engine_query_KNL();

	if (basil_1_7_supported)
		log_event(PBSEVENT_DEBUG4, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
			  "This Cray system supports the BASIL 1.7 protocol.");
	else {
		log_event(PBSEVENT_DEBUG4, PBS_EVENTCLASS_NODE, LOG_ERR, __func__,
			  "This Cray system does not support the BASIL 1.7 protocol.");
		return;
	}

	/*
	 * Allocate a buffer (requestBuffer_knl) for a new ALPS request (System Query).
	 * A nonzero return value indicates failure; return at this point without proceeding
	 * with System Query processing.
	 */
	if (init_KNL_alps_req_buf() != 0)
		return;

	/* Create a System (BASIL 1.7) Query request to fetch KNL information. */
	snprintf(requestBuffer_knl, UTIL_BUFFER_LEN, "<?xml version=\"1.0\"?>\n"
						     "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" " BASIL_ATR_TYPE "=\"" BASIL_VAL_SYSTEM "\"/>",
		 basilversion_system);

	/*
	 * The 'basil_ver' argument is checked in response_start() (a callback
	 * function invoked during alps_request() processing). Flow of control can
	 * arrive at response_start() from either alps_system_KNL() or alps_inventory().
	 * This argument helps make the distinction.
	 */
	if ((brp_knl = alps_request(requestBuffer_knl, basilversion_system)) == NULL) {

		/* Failure to get KNL Node information from ALPS. */
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			  "ALPS System Query request failed.");
		return;
	}
}

/**
 * @brief Issue an ENGINE query to determine if BASIL 1.7 is supported.
 * 	  We are partially supporting the BASIL 1.7 protocol (for the System Query).
 *	  If the BASIL 1.7 protocol is found in the query response, set a flag
 *	  that will be checked in alps_system_KNL().
 *
 * @return void
 */
static void
alps_engine_query_KNL(void)
{
	basil_response_t *brp_eng;

	/*
	 * Allocate a buffer (requestBuffer_knl) for a new ALPS request (Engine Query).
	 * A nonzero return value indicates failure.
	 */
	if (init_KNL_alps_req_buf() != 0)
		return;

	/* This is set to "1.1", since PBS may be running on a system that may or */
	/* may not support BASIL 1.7. BASIL 1.1 is the lowest version that supports */
	/* the ENGINE Query. */

	sprintf(requestBuffer_knl, "<?xml version=\"1.0\"?>\n"
				   "<" BASIL_ELM_REQUEST " " BASIL_ATR_PROTOCOL "=\"%s\" " BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" " BASIL_ATR_TYPE "=\"" BASIL_VAL_ENGINE "\"/>",
		BASIL_VAL_VERSION_1_1);
	if ((brp_eng = alps_request(requestBuffer_knl, BASIL_VAL_VERSION_1_1)) != NULL) {
		/* Proceed if no errors in the response data. */
		if (*brp_eng->error == '\0') {
			/* Ensure we have the correct response. */
			if (brp_eng->method == basil_method_query) {
				/* Check if 'basil_support' is set before trying to strdup. */
				if (brp_eng->data.query.data.engine.basil_support != NULL) {

					if (strstr(brp_eng->data.query.data.engine.basil_support,
						   BASIL_VAL_VERSION_1_7) != NULL) {
						basil_1_7_supported = 1;
						snprintf(basilversion_system, sizeof(basilversion_system),
							 BASIL_VAL_VERSION_1_7);
					} else
						basil_1_7_supported = 0;
				}
			} else {
				/* Wrong method in the response. */
				sprintf(log_buffer, "Wrong method, expected: %d but "
						    "got: %d",
					basil_method_query, brp_eng->method);
				log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
					  LOG_DEBUG, __func__, log_buffer);
			}
		} else {
			/* There was an error in the BASIL response. */
			sprintf(log_buffer, "Error in BASIL response: %s", brp_eng->error);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
				  __func__, log_buffer);
		}
	}

	free_basil_response_data(brp_eng);
}

/**
 * @brief Process the System (BASIL 1.7) Query Response. This includes creation
 *	  of KNL vnodes.
 *
 * @return void
 */
void
system_to_vnodes_KNL(void)
{
	basil_response_query_system_t *sys_knl;

	if (!basil_1_7_supported)
		return;

	/* System 1.7 Query failed to get KNL Node information from ALPS. */
	if (!brp_knl)
		return;

	if (brp_knl->method != basil_method_query) {
		snprintf(log_buffer, sizeof(log_buffer), "Wrong method: %d",
			 brp_knl->method);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
			  log_buffer);
		return;
	}

	if (brp_knl->data.query.type != basil_query_system) {
		snprintf(log_buffer, sizeof(log_buffer), "Wrong query type: %d",
			 brp_knl->data.query.type);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
			  log_buffer);
		return;
	}

	if (*brp_knl->error != '\0') {
		snprintf(log_buffer, sizeof(log_buffer), "Error in BASIL response: %s",
			 brp_knl->error);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__,
			  log_buffer);
		return;
	}

	sys_knl = &brp_knl->data.query.data.system;

	create_vnodes_KNL(sys_knl);

	free_basil_response_data(brp_knl);
}

/**
 *
 * @brief Create KNL vnodes.
 * 	  'vnlp' is a global pointer that gets freed in process_hup() (mom_main.c)
 * 	  during a MoM restart. The vnode state gets cleared and we repeat the vnode
 *	  creation cycle i.e. creation of non-KNL vnodes (in inventory_to_vnodes())
 *	  followed by KNL vnodes in this function.
 *
 * @param[in] sys_knl ALPS BASIL System Query response.
 *
 * @return void
 */
static void
create_vnodes_KNL(basil_response_query_system_t *sys_knl)
{
	char *attr, *arch;
	char vname[VNODE_NAME_LEN];
	char utilBuffer_knl[(UTIL_BUFFER_LEN * sizeof(char))];
	int ncpus_per_knl;
	int node_idx = 0;
	int node_count = 0;
	long node_id = 0;
	long *nid_arr = NULL;
	int atype = READ_WRITE | ATR_DFLAG_CVTSLT;
	char mpphost_knl[BASIL_STRING_LONG];

	basil_system_element_t *node_group;

	if (sys_knl == NULL)
		return;

	snprintf(mpphost_knl, sizeof(mpphost_knl), "%s", sys_knl->mpp_host);

	/*
	 * Iterate through all the Node groups in the System Query Response. Each
	 * Node group may contain information about multiple (a 'range list') of KNL Nodes.
	 * Each XML Element <Nodes ...> </Nodes> encapsulates information about a group of Nodes.
	 */
	for (node_group = sys_knl->elements; node_group; node_group = node_group->next) {

		/*
		 * The System Query XML Response contains information about KNL and
		 * non-KNL Nodes. We are only interested in KNL nodes that are in
		 * "batch" mode and in the "up" state.
		 */
		if (exclude_from_KNL_processing(node_group, 1))
			continue;

		/*
		 * Extract NIDs (Node ID) from node_group->nidlist.
		 * If nidlist is empty, node_count gets set to 0 and vnode
		 * creation in the inner for() is bypassed.
		 */
		nid_arr = process_nodelist_KNL(node_group->nidlist, &node_count);

		/*
		 * Create vnodes for each of the KNL Nodes listed in this Node group.
		 * All KNL Nodes within a Node Group will have similar vnode attributes,
		 * since all attributes in each <Nodes ...> XML element apply to all
		 * Nodes listed in the 'rangelist'.
		 */
		for (node_idx = 0; node_idx < node_count; node_idx++) {

			node_id = nid_arr[node_idx];
			snprintf(vname, VNODE_NAME_LEN, "%s_%ld", mpphost_knl, node_id);

			if (first_compute_node) {
				/*
				 * Create the name of the very first vnode so we
				 * can attach topology info to it.
				 */

				attr = ATTR_NODE_TopologyInfo;
				if (vn_addvnr(vnlp, vname, attr, (char *) basil_inventory,
					      ATR_TYPE_STR, READ_ONLY, NULL) == -1)
					goto bad_vnl;
				first_compute_node = 0;
			}

			attr = "sharing";
			if (vn_addvnr(vnlp, vname, attr, ND_Force_Exclhost, 0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.vntype";
			if (vn_addvnr(vnlp, vname, attr, CRAY_COMPUTE, 0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScrayhost";
			if (vn_addvnr(vnlp, vname, attr, mpphost_knl, ATR_TYPE_STR, atype, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.arch";
			arch = BASIL_VAL_XT;
			if (vn_addvnr(vnlp, vname, attr, arch, ATR_TYPE_STR, atype, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.host";
			snprintf(utilBuffer_knl, sizeof(utilBuffer_knl), "%s_%ld", mpphost_knl, node_id);
			if (vn_addvnr(vnlp, vname, attr, utilBuffer_knl, 0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScraynid";
			snprintf(utilBuffer_knl, sizeof(utilBuffer_knl), "%ld", node_id);
			if (vn_addvnr(vnlp, vname, attr, utilBuffer_knl, ATR_TYPE_STR, atype, NULL) == -1)
				goto bad_vnl;

			if (vnode_per_numa_node) {
				attr = "resources_available.PBScrayseg";
				if (vn_addvnr(vnlp, vname, attr, "0", ATR_TYPE_STR, atype, NULL) == -1)
					goto bad_vnl;
			}
			attr = "resources_available.ncpus";
			ncpus_per_knl = atoi(node_group->compute_units);
			snprintf(utilBuffer_knl, sizeof(utilBuffer_knl), "%d", ncpus_per_knl);
			if (vn_addvnr(vnlp, vname, attr, utilBuffer_knl, 0, 0, NULL) == -1)
				goto bad_vnl;

			/* avlmem is conventional DRAM mem. avlmem = page_size_kb * page_count. */
			attr = "resources_available.mem";
			snprintf(utilBuffer_knl, sizeof(utilBuffer_knl), "%skb", node_group->avlmem);
			if (vn_addvnr(vnlp, vname, attr, utilBuffer_knl, 0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "current_aoe";
			snprintf(utilBuffer_knl, sizeof(utilBuffer_knl), "%s_%s",
				 node_group->numa_cfg, node_group->hbm_cfg);
			if (vn_addvnr(vnlp, vname, attr, utilBuffer_knl, 0, 0, NULL) == -1)
				goto bad_vnl;

			/* hbmem is high bandwidth mem (MCDRAM) in megabytes. */
			attr = "resources_available.hbmem";
			snprintf(utilBuffer_knl, sizeof(utilBuffer_knl), "%smb", node_group->hbmsize);
			if (vn_addvnr(vnlp, vname, attr, utilBuffer_knl, 0, 0, NULL) == -1)
				goto bad_vnl;
		}
		/* We have no further use for this array of KNL node ids. */
		if (nid_arr) {
			free(nid_arr);
			nid_arr = NULL;
		}
	}

	return;

bad_vnl:
	snprintf(log_buffer, sizeof(log_buffer), "Creation of Cray KNL vnodes failed with name %s", vname);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__, log_buffer);
	/*
	 * Don't free nv since it might be important in the dump.
	 */
	abort();
}

/**
 *
 * @brief Check if this Node Group needs to be considered for KNL processing.
 *        We are only interested in KNL Nodes that have "role" set to "batch" and
 *	  "state" set to "up".
 *	  The attributes "numa_cfg", "hbmsize", "hbm_cfg" not being empty ("") implies
 *	  they pertain to KNL Nodes.
 *
 * @param[in] ptrNodeGrp Pointer to the current Node Group in the System XML Response.
 * @param[in] check_state Indicates wheather this function to look for the KNL node state.
 *
 * @return int
 * @retval 1 Indicates that the Node Group should not be considered.
 * @retval 0 Indicates that the Node Group should be considered.
 *
 */
static int
exclude_from_KNL_processing(basil_system_element_t *ptrNodeGrp,
			    short int check_state)
{
	if ((strcmp(ptrNodeGrp->role, BASIL_VAL_BATCH_SYS) != 0) ||
	    (check_state ? (strcmp(ptrNodeGrp->state,
				   BASIL_VAL_UP_SYS) != 0)
			 : 0) ||
	    ((strcmp(ptrNodeGrp->numa_cfg, "") == 0) &&
	     (strcmp(ptrNodeGrp->hbmsize, "") == 0) &&
	     (strcmp(ptrNodeGrp->hbm_cfg, "") == 0)))
		return 1;
	else
		return 0;
}

/**
 *
 * @brief KNL Nodes are specified in 'Rangelist' format in a string e.g. "12,13,14-18,21".
 * 	  Extract Node IDs from this string and store them in an integer array.
 *
 * @param[in] nidlist String containing rangelist of Nodes.
 * @param[out] ptr_count Total number of Nodes in this list.
 *
 * @return int *
 * @retval This is an long integer array containing Node IDs.
 *	   nid_arr returned here is freed in the calling function after use.
 */
static long *
process_nodelist_KNL(char *nidlist, int *ptr_count)
{
	char delim[] = ",";
	char *token, *nidlist_array, *endptr;
	int nid_count = 0;
	long *nid_arr = NULL;

	if (nidlist == NULL) {
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG, __func__, "No KNL nodes.");
		*ptr_count = 0;
		return NULL;
	}

	if ((nidlist_array = strdup(nidlist)) == NULL) {
		log_err(errno, __func__, "malloc failure");
		*ptr_count = 0;
		return NULL;
	}

	endptr = NULL;
	/* 'token' points to a null terminated string containing the token e.g. "12\0", "14-18\0". */
	token = strtok(nidlist_array, delim);
	while (token != NULL) {
		int nid_num;
		/*
		 * Each token (e.g. "12" or "14-18") is converted to an int and sent as
		 * an argument to store_nids(). In case of tokens such as "14-18", nid_num=14
		 * and 'endptr' points to the first invalid character i.e. "-".
		 */
		nid_num = (int) strtol(token, &endptr, 10);
		/* Checking for invalid data in the Node rangelist. */
		if ((*endptr != '\0') && (*endptr != '-')) {
			snprintf(log_buffer, sizeof(log_buffer), "Bad KNL Rangelist: \"%s\"", nidlist_array);
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE, LOG_ERR, __func__, log_buffer);
			free(nid_arr);
			nid_arr = NULL;
			nid_count = 0;
			break;
		}

		store_nids(nid_num, endptr, &nid_arr, &nid_count);
		if (nid_arr == NULL) {
			nid_count = 0;
			break;
		}

		token = strtok(NULL, delim);
	}

	*ptr_count = nid_count;
	free(nidlist_array);
	return nid_arr;
}

/**
 *
 * @brief Helper function for process_nodelist_KNL().
 *	  It stores the tokenized Node IDs in an integer array.
 * @example For the token "14-18", nid_num = 14, *endptr = "-" and endptr = "-18\0".
 *	  The Node IDs 14 and 18 are extracted and stored in 'nid_arr'.
 *
 * @param[in] nid_num Node ID to be stored.
 * @param[in] endptr Ptr to invalid character (set by strtol()).
 *
 * @param[out] nid_arr Array to hold all Node IDs.
 * @param[out] nid_count Node count.
 *
 * @return void
 */
static void
store_nids(int nid_num, char *endptr, long **nid_arr, int *nid_count)
{
	int count = *nid_count;
	int range_len = 1;
	int i = 0;
	long *tmp_ptr = NULL;
	char *ptr = NULL;

	if (*endptr == '-') {
		int nid_num_last;
		nid_num_last = (int) strtol(endptr + 1, &ptr, 10);
		/* Checking for invalid data in the Node rangelist. */
		if ((*ptr != '\0') && (*ptr != '-')) {
			snprintf(log_buffer, sizeof(log_buffer), "Bad KNL Rangelist: \"%s\"", endptr);
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE, LOG_ERR, __func__, log_buffer);
			free(*nid_arr);
			*nid_arr = NULL;
			return;
		}

		range_len = (nid_num_last - nid_num) + 1;
	}

	tmp_ptr = (long *) realloc(*nid_arr, (count + range_len) * sizeof(long));
	if (!tmp_ptr) {
		log_err(errno, __func__, "realloc failure");
		free(*nid_arr);
		*nid_arr = NULL;
		return;
	}
	*nid_arr = tmp_ptr;

	for (i = 0; i < range_len; i++) {
		*(*nid_arr + count) = nid_num + i;
		count++;
	}

	*nid_count = count;
}

/**
 * @brief
 * This function is registered to handle the System element in
 * the System XML response.
 *
 * The standard Expat start handler function prototype is used.
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return void
 */
static void
system_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_response_t *brp;
	basil_response_query_system_t *sys;

	if (++(d->count_sys.system) > 1) {
		parse_err_multiple_elements(d);
		return;
	}

	brp = d->brp;
	brp->data.query.type = basil_query_system;
	sys = &brp->data.query.data.system;

	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_TIMESTAMP, *np) == 0) {
			if (sys->timestamp != 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			sys->timestamp = atoll(*vp);
		} else if (strcmp(BASIL_ATR_MPPHOST, *np) == 0) {
			if (sys->mpp_host[0] != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(sys->mpp_host, BASIL_STRING_LONG, "%s", *vp);
		} else if (strcmp(BASIL_ATR_CPCU, *np) == 0) {
			if (sys->cpcu_val != 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			sys->cpcu_val = atoi(*vp);
			if (sys->cpcu_val < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
}

/**
 * @brief
 * This function is registered to handle the 'Nodes' element within a System XML
 * response.
 * This element handler is called each time a new <Nodes ...> element is encountered
 * in the XML response currently being parsed. It populates the user data structure
 * (ud_t *d) with the current <Nodes ...> element attribute/value pairs.
 *
 * The standard Expat start handler function prototype is used.
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return void
 */
static void
node_group_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_system_element_t *node_group;
	basil_response_t *brp;
	int page_size_KB = 0;
	int shift_count = 0;
	int res = 0;
	long page_count, avail_mem;
	char *invalid_char_ptr;

	brp = d->brp;
	node_group = (basil_system_element_t *) calloc(1, sizeof(basil_system_element_t));
	if (!node_group) {
		parse_err_out_of_memory(d);
		return;
	}

	if (d->current_sys.node_group)
		(d->current_sys.node_group)->next = node_group;
	else
		brp->data.query.data.system.elements = node_group;

	d->current_sys.node_group = node_group;

	/*
	 * Iterate through the attribute name/value pairs. Update the name and
	 * value pointers with each loop. If the XML attributes ("role", "state",
	 * "speed", "numa_nodes", "dies", "compute_units", "cpus_per_cu",
	 * "page_size_kb", "page_count", "accels", "accel_state", "numa_cfg",
	 * "hbm_size_mb", "hbm_cache_pct") are repeated within each "Nodes"
	 * element under consideration, invoke parse_err_multiple_attrs().
	 */
	for (np = vp = atts, vp++; np && *np && vp && *vp; np = ++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_ROLE, *np) == 0) {
			if (*node_group->role != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			if ((strcmp(BASIL_VAL_BATCH_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_INTERACTIVE_SYS, *vp) == 0))
				pbs_strncpy(node_group->role, *vp, sizeof(node_group->role));
			else
				strcpy(node_group->role, BASIL_VAL_UNKNOWN);
		} else if (strcmp(BASIL_ATR_STATE, *np) == 0) {
			if (*node_group->state != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			if ((strcmp(BASIL_VAL_UP_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_DOWN_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_UNAVAILABLE_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_ROUTING_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_SUSPECT_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_ADMIN_SYS, *vp) == 0))
				pbs_strncpy(node_group->state, *vp, sizeof(node_group->state));
			else
				strcpy(node_group->state, BASIL_VAL_UNKNOWN);
		} else if (strcmp(BASIL_ATR_SPEED, *np) == 0) {
			if (*node_group->speed != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/**
			 * The speed attribute is not used elsewhere in PBS. Setting
			 * it to -1 to catch the multiple instances scenario (i.e.
			 * multiple speed attributes occurring in the XML response).
 			 */
			strncpy(node_group->speed, "-1", sizeof(node_group->speed) - 1);
		} else if (strcmp(BASIL_ATR_NUMA_NODES, *np) == 0) {
			if (*node_group->numa_nodes != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be empty (""), "0" nor negative. */
			if (strtol(*vp, &invalid_char_ptr, 10) <= 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
			pbs_strncpy(node_group->numa_nodes, *vp, sizeof(node_group->numa_nodes));
		} else if (strcmp(BASIL_ATR_DIES, *np) == 0) {
			if (*node_group->n_dies != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be empty ("") nor negative. Can be "0". */
			if ((strcmp(*vp, "") == 0) || (strtol(*vp, &invalid_char_ptr, 10) < 0)) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
			pbs_strncpy(node_group->n_dies, *vp, sizeof(node_group->n_dies));
		} else if (strcmp(BASIL_ATR_COMPUTE_UNITS, *np) == 0) {
			if (*node_group->compute_units != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be empty ("") nor negative. Can be "0". */
			if ((strcmp(*vp, "") == 0) || (strtol(*vp, &invalid_char_ptr, 10) < 0)) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
			pbs_strncpy(node_group->compute_units, *vp, sizeof(node_group->compute_units));
		} else if (strcmp(BASIL_ATR_CPUS_PER_CU, *np) == 0) {
			if (*node_group->cpus_per_cu != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be empty (""), "0" nor negative. */
			if (strtol(*vp, &invalid_char_ptr, 10) <= 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
			pbs_strncpy(node_group->cpus_per_cu, *vp, sizeof(node_group->cpus_per_cu));
		} else if (strcmp(BASIL_ATR_PAGE_SIZE_KB, *np) == 0) {
			if (*node_group->pgszl2 != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be empty (""), "0" nor negative. */
			page_size_KB = strtol(*vp, &invalid_char_ptr, 10);
			if (page_size_KB <= 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}

			shift_count = 0;
			while (1) {
				/* Computing log base 2 of page_size_KB. */
				/* e.g. if page_size_kb = 1 KB (i.e. 1024 Bytes), */
				/* then pgszl2 = 10 (since 2 ^ 10 = 1024). */
				res = 1 << shift_count;
				if (res == page_size_KB)
					break;
				else
					shift_count++;
			}
			/* Adding log base 2 of 1024. */
			shift_count += 10;
			snprintf(node_group->pgszl2, BASIL_STRING_SHORT, "%d", shift_count);
		} else if (strcmp(BASIL_ATR_PAGE_COUNT, *np) == 0) {
			if (*node_group->avlmem != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be empty ("") nor negative. Can be "0". */
			page_count = strtol(*vp, &invalid_char_ptr, 10);
			if ((strcmp(*vp, "") == 0) || (page_count < 0)) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}

			avail_mem = page_size_KB * page_count;
			snprintf(node_group->avlmem, BASIL_STRING_SHORT, "%ld", avail_mem);
		} else if (strcmp(BASIL_ATR_ACCELS, *np) == 0) {
			if (*node_group->accel_name != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be empty (""). */
			if (strcmp(*vp, "") == 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
			pbs_strncpy(node_group->accel_name, *vp, sizeof(node_group->accel_name));
		} else if (strcmp(BASIL_ATR_ACCEL_STATE, *np) == 0) {
			if (*node_group->accel_state != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			if ((strcmp(BASIL_VAL_UP_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_DOWN_SYS, *vp) == 0))
				pbs_strncpy(node_group->accel_state, *vp, sizeof(node_group->accel_state));
			else
				strcpy(node_group->accel_state, BASIL_VAL_UNKNOWN);
		} else if (strcmp(BASIL_ATR_NUMA_CFG, *np) == 0) {
			if (*node_group->numa_cfg != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			if ((strcmp(BASIL_VAL_EMPTY_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_A2A_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_SNC2_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_SNC4_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_HEMI_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_QUAD_SYS, *vp) == 0))
				pbs_strncpy(node_group->numa_cfg, *vp, sizeof(node_group->numa_cfg));
			else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_HBMSIZE, *np) == 0) {
			if (*node_group->hbmsize != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}

			/* *vp cannot be negative. */
			if (strtol(*vp, &invalid_char_ptr, 10) < 0) {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
			pbs_strncpy(node_group->hbmsize, *vp, sizeof(node_group->hbmsize));
		} else if (strcmp(BASIL_ATR_HBM_CFG, *np) == 0) {
			if (*node_group->hbm_cfg != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if ((strcmp(BASIL_VAL_EMPTY_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_0_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_25_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_50_SYS, *vp) == 0) ||
			    (strcmp(BASIL_VAL_100_SYS, *vp) == 0))
				pbs_strncpy(node_group->hbm_cfg, *vp, sizeof(node_group->hbm_cfg));
			else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}
}

/**
 * Define the array that is used to register the expat element handlers.
 * See parse_element_start, parse_element_end, and parse_char_data for
 * further information.
 * The definition of element_handler_t above explains the different
 * structure elements.
 */

// clang-format off

static element_handler_t handler[] =
{
	{
		"UNDEFINED",
		NULL,
		NULL,
		NULL
	},
	{
		BASIL_ELM_MESSAGE,
		message_start,
		message_end,
		message_char_data
	},
	{
		BASIL_ELM_RESPONSE,
		response_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RESPONSEDATA,
		response_data_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RESERVED,
		reserved_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_CONFIRMED,
		confirmed_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RELEASED,
		released_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_INVENTORY,
		inventory_start,
		inventory_end,
		disallow_char_data
	},
	{
		BASIL_ELM_ENGINE,
		engine_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_NODEARRAY,
		node_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_NODE,
		node_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_SOCKETARRAY,
		socket_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_SOCKET,
		socket_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_SEGMENTARRAY,
		segment_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_SEGMENT,
		segment_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_CUARRAY,
		computeunit_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_COMPUTEUNIT,
		computeunit_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_PROCESSORARRAY,
		processor_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_PROCESSOR,
		processor_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_PROCESSORALLOC,
		processor_allocation_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_MEMORYARRAY,
		memory_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_MEMORY,
		memory_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_MEMORYALLOC,
		memory_allocation_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_LABELARRAY,
		label_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_LABEL,
		label_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVNARRAY,
		reservation_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RESERVATION,
		reservation_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_APPARRAY,
		application_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_APPLICATION,
		application_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_CMDARRAY,
		command_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_COMMAND,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_ACCELERATORARRAY,
		accelerator_array_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_ACCELERATOR,
		accelerator_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_ACCELERATORALLOC,
		accelerator_allocation_start,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_NODEARRAY,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_NODE,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_SGMTARRAY,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_SGMT,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_SGMT,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_PROCARRAY,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_PROCESSOR,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_PROCESSOR,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_MEMARRAY,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_RSVD_MEMORY,
		ignore_element,
		default_element_end,
		disallow_char_data
	},
	{
		BASIL_ELM_SYSTEM,
		system_start,
		default_element_end,
		disallow_char_data,
	},
	{
		BASIL_ELM_NODES,
		node_group_start,
		default_element_end,
		allow_char_data
	},
	{
		NULL,
		NULL,
		NULL,
		NULL
	}
};
#endif /* MOM_ALPS */

// clang-format on
