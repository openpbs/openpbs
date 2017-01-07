/*
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
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

#if	MOM_ALPS /* Defined when --enable-alps is passed to configure. */

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

#ifndef	_XOPEN_SOURCE
extern pid_t getsid(pid_t);
#endif	/* _XOPEN_SOURCE */

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
 */
char	mpphost[BASIL_STRING_LONG];

/*
 * Data types to support interaction with the Cray ALPS implementation.
 */

extern char *alps_client;
extern int vnode_per_numa_node;
extern char *ret_string;
extern vnl_t	*vnlp;

/**
 * Define a sane BASIL stack limit.
 * This specifies the how many levels deep the BASIL can go.
 * Need to increase this for each XML level indentation addition.
 */
#define MAX_BASIL_STACK (14)

/**
 * Maintain counts on elements that are limited to one instance per context.
 * These counters help keep track of the XML structure that is imposed
 * by ALPS.  The counter is checked to be sure they are not nested or
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
	int segment_array;
	int processor_array;
	int memory_array;
	int label_array;
	int reservation_array;
	int application_array;
	int command_array;
	int accelerator_array;
	/*
	 The following entries are not needed now because we are just
	 ignoring the corresponding XML tags.  If they become nesessary
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
 * Pointers for node data used when parsing inventory.
 * These provide a place to hang lists of any possible result from an
 * ALPS inventory.  Additionally, counters for node states are kept here.
 */
typedef struct inventory_data {
	basil_node_t *node;
	basil_node_segment_t *segment;
	basil_node_processor_t *processor;
	basil_processor_allocation_t *processor_allocation;
	basil_node_memory_t *memory;
	basil_memory_allocation_t *memory_allocation;
	basil_label_t *label;
	basil_rsvn_t *reservation;
	int	role_int;
	int	role_batch;
	int	role_unknown;
	int	state_up;
	int	state_down;
	int	state_unavail;
	int	state_routing;
	int	state_suspect;
	int	state_admin;
	int	state_unknown;
	basil_node_accelerator_t *accelerator;
	basil_accelerator_allocation_t *accelerator_allocation;
	int	accel_type_gpu;
	int	accel_type_unknown;
	int	accel_state_up;
	int	accel_state_down;
	int	accel_state_unknown;
} inventory_data_t;

/**
 * The user data structure for expat.
 */
typedef struct ud {
	int depth;
	int stack[MAX_BASIL_STACK + 1];
	char status[BASIL_STRING_SHORT];
	char message[BASIL_ERROR_BUFFER_SIZE];
	char error_class[BASIL_STRING_SHORT];
	char error_source[BASIL_STRING_SHORT];
	element_counts_t count;
	inventory_data_t current;
	basil_response_t *brp;
} ud_t;

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

static char	*requestBuffer;
static size_t	requestCurr = 0;
static size_t	requestSize = 0;

#define UTIL_BUFFER_LEN (4096)
static char utilBuffer[(UTIL_BUFFER_LEN * sizeof(char))];

#define BASIL_ERR_ID "BASIL"

/**
 * Flag set to true when talking to Basil 1.1 original.
 */
static	int	basil11orig	= 0;

/**
 * Variable that keeps track of which basil version to speak
 */
static char	basilversion[BASIL_STRING_SHORT];

/**
 * String to use for mpp_host in vnode names when basil11orig
 * is true.
 */
#define	FAKE_MPP_HOST	"default"

/**
 * @brief
 * 	When DEBUG is defined, log XML parsing messages to MOM log file.
 *
 * @param[in] fmt - format of msg
 *
 * @return Void
 *
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
	size_t	len = strlen(new);

	if (requestCurr + len >= requestSize) {
		size_t	num = (UTIL_BUFFER_LEN + len)/UTIL_BUFFER_LEN;
		requestSize += num*UTIL_BUFFER_LEN;
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
 * Check that the depth is okay then look at the top element.  Make
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
		} else if (strcmp(BASIL_ELM_SEGMENTARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_NODE, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_SEGMENT, top) == 0) {
			if (strcmp(BASIL_ELM_SEGMENTARRAY, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
			}
		} else if (strcmp(BASIL_ELM_PROCESSORARRAY, top) == 0) {
			if (strcmp(BASIL_ELM_SEGMENT, prev) != 0) {
				parse_err_illegal_start(d);
				return (1);
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
				parse_err_illegal_start(d);
				return (1);
			}
			if (brp->data.query.type != basil_query_inventory) {
				parse_err_illegal_start(d);
				return (1);
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
 * Note: basilversion is set in alps_engine_query(), before response_start
 * is called.
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
	basil_response_t *brp;
	char protocol[BASIL_STRING_SHORT];

	if (stack_busted(d))
		return;
	brp = d->brp;
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_PROTOCOL, *np) == 0) {
			BASIL_STRSET_SHORT(protocol, *vp);
			if ((strcmp(BASIL_VAL_VERSION_1_2, *vp) != 0) &&
				(strcmp(BASIL_VAL_VERSION_1_1, *vp) != 0)) {
				parse_err_version_mismatch(d, *vp,
					basilversion);
				return;
			}
		}
	}
	if (protocol[0] == '\0') {
		parse_err_unspecified_attr(d, BASIL_ATR_PROTOCOL);
		return;
	}
	return;
}

/**
 * @brief
 * 	This funtion is registered to handle the start of the BASIL data.
 * 	It checks to make sure there is a valid method type so we know
 * 	what elements to expect later on.
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
				brp->data.query.type = basil_query_none;
			} else {
				parse_err_illegal_attr_val(d, *np, *vp);
				return;
			}
		} else if (strcmp(BASIL_ATR_STATUS, *np) == 0) {
			strcpy(d->status, *vp);
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
			strcpy(d->error_class, *vp);
			/*
			 * The existence of a PERMENENT error used to
			 * reset the BASIL_ERR_TRANSIENT flag.  This
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
			strcpy(d->error_source, *vp);
			/*
			 * Consider "BACKEND" errors TRANSIENT when trying
			 * to create an ALPS reservation.
			 * It was found that a node being changed from
			 * batch to interactive would cause a PERMANENT,
			 * BACKEND error when a job was run on it.  We
			 * want this to not result in the job being deleted.
			 */
			if (brp->method == basil_method_reserve) {
				if (strcmp(BASIL_VAL_BACKEND, *vp) == 0) {
					brp->error_flags |= (BASIL_ERR_TRANSIENT);
				}
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
	return;
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
 *
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
 * 	The standard Expat start handler function prototype is used.
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			brp->data.reserve.rsvn_id = strtol(*vp, NULL, 10);
		} else if (!basil11orig) {
			/*
			 * Basil 1.1+ doesn't have any other elements
			 * but Basil 1.1 orig has dummy entries for
			 * "admin_cookie" and "alloc_cookie".  Just
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		/*
		 * These keywords do not need to be saved.  The CONFIRM
		 * reply is just sending back the same values given in
		 * the CONFIRM request.
		 */
		if (strcmp(BASIL_ATR_RSVN_ID, *np) == 0) {
			xml_dbg("%s: %s = %s", __func__, *np, *vp);
		}
		else if (strcmp(BASIL_ATR_PAGG_ID, *np) == 0) {
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

	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		/*
		 * This keyword does not need to be saved.  The
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
	basil_response_query_engine_t        *eng;
	int	len = 0;

	if (stack_busted(d))
		return;

	brp = d->brp;
	brp->data.query.type = basil_query_engine;
	eng = &brp->data.query.data.engine;

	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
	basil_response_query_inventory_t	*inv;

	if (stack_busted(d))
		return;
	if (++(d->count.inventory) > 1) {
		parse_err_multiple_elements(d);
		return;
	}

	brp = d->brp;
	brp->data.query.type = basil_query_inventory;
	inv = &brp->data.query.data.inventory;

	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
				BASIL_STRING_SHORT, "%s", *vp);
		} else {
			parse_err_unrecognized_attr(d, *np);
			return;
		}
	}

	/*
	 * The mpp_host and timestamp fields will be filled in
	 * for BASIL_VAL_VERSION_1_1 "plus" and higher.  There is no other
	 * way to tell BASIL_VAL_VERSION_1_1 from 1.1+.
	 */
	if (inv->timestamp == 0) {
		inv->timestamp = time(NULL);
		basil11orig = 1;
	}
	if (inv->mpp_host[0] == '\0') {
		strncpy(inv->mpp_host, FAKE_MPP_HOST, sizeof(inv->mpp_host));
		inv->mpp_host[sizeof(inv->mpp_host)-1] = '\0';
		basil11orig = 1;
	}

	d->count.node_array = 0;
	d->count.reservation_array = 0;
	d->count.accelerator_array = 0;

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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_CHANGECOUNT, *np) == 0) {
			/*
			 * Currently unused.
			 * We could save changecount if we ever started
			 * requesting inventory more frequently.
			 * changecount could help reduce the amount of data
			 * returned if the inventory has not changed.
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_NODE_ID, *np) == 0) {
			if (node->node_id >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			node->node_id = atol(*vp);
			if (*vp < 0) {
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
	d->count.segment_array = 0;
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
 *
 * @retval Void
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.segment = NULL;
	return;
}

/**
 * @brief
 *	 This function is registered to handle the segment element within an
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
segment_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_segment_t *segment;
	basil_response_t *brp;

	if (stack_busted(d))
		return;
	brp = d->brp;
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
			return;
		}
		(d->current.node)->segments = segment;
	}
	d->current.segment = segment;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_ORDINAL, *np) == 0) {
			if (segment->ordinal >= 0) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			segment->ordinal = atol(*vp);
			if (*vp < 0) {
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
	d->count.processor_array = 0;
	d->count.memory_array = 0;
	d->count.label_array = 0;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the processor array element
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.processor = NULL;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the processor element within an
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
processor_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_node_processor_t *processor;

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
			return;
		}
		(d->current.segment)->processors = processor;
	}
	d->current.processor = processor;
	/*
	 * Work through the attribute pairs updating the name pointer and
	 * value pointer with each loop. The somewhat complex loop control
	 * syntax is just a fancy way of stepping through the pairs.
	 */
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
		} else if (strcmp(BASIL_ATR_ARCH, *np) == 0) {
			if (processor->arch) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			if (strcmp(BASIL_VAL_X86_64, *vp) == 0) {
				processor->arch = basil_processor_x86_64;
			} else if (strcmp(BASIL_VAL_CRAY_X2, *vp) == 0) {
				processor->arch = basil_processor_cray_x2;
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
	if (!processor->arch) {
		parse_err_unspecified_attr(d, BASIL_ATR_ARCH);
		return;
	}
	if (processor->clock_mhz < 0) {
		parse_err_unspecified_attr(d, BASIL_ATR_CLOCK_MHZ);
		return;
	}
	d->current.processor_allocation = NULL;
	return;
}

/**
 * @brief
 *	 This function is registered to handle the processor allocation element
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
 * 	an inventory response.
 *
 * The standard Expat start handler function prototype is used.
 *
 * @param d pointer to user data structure
 * @param[in] el unused in this function
 * @param[in] atts array of name/value pairs
 *
 * @return  Void
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.memory = NULL;
	return;
}

/**
 * @brief
 *	 This function is registered to handle the memory element within an
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		xml_dbg("%s: %s = %s", __func__, *np, *vp);
		if (strcmp(BASIL_ATR_NAME, *np) == 0) {
			if (*label->name) {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(label->name, BASIL_STRING_SHORT, "%s", *vp);
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
		return;
	}
	memset(gpu, 0, sizeof(basil_accelerator_gpu_t));
	accelerator->data.gpu = gpu;
	if (d->current.accelerator) {
		(d->current.accelerator)->next = accelerator;
	} else {
		if (!d->current.node) {
			parse_err_internal(d);
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
			len = strlen(*vp)+1;
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
	if (gpu->family == '\0') {
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		parse_err_unrecognized_attr(d, *np);
		return;
	}
	d->current.reservation = NULL;
	return;
}

/**
 * @brief
 * 	This function is registered to handle the reservation element within an
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
reservation_start(ud_t *d, const XML_Char *el, const XML_Char **atts)
{
	const XML_Char **np;
	const XML_Char **vp;
	basil_rsvn_t *rsvn;
	basil_response_t *brp;

	if (stack_busted(d))
		return;
	brp = d->brp;
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
			snprintf(rsvn->user_name, BASIL_STRING_SHORT,
				"%s", *vp);
		} else if (strcmp(BASIL_ATR_ACCOUNT_NAME, *np) == 0) {
			if (*rsvn->account_name != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(rsvn->account_name, BASIL_STRING_SHORT,
				"%s", *vp);
		} else if (strcmp(BASIL_ATR_TIME_STAMP, *np) == 0) {
			if (*rsvn->time_stamp != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(rsvn->time_stamp, BASIL_STRING_SHORT,
				"%s", *vp);
		} else if (strcmp(BASIL_ATR_BATCH_ID, *np) == 0) {
			if (*rsvn->batch_id != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(rsvn->batch_id, BASIL_STRING_SHORT,
				"%s", *vp);
		} else if (strcmp(BASIL_ATR_RSVN_MODE, *np) == 0) {
			if (*rsvn->rsvn_mode != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(rsvn->rsvn_mode, BASIL_STRING_SHORT,
				"%s", *vp);
		} else if (strcmp(BASIL_ATR_GPC_MODE, *np) == 0) {
			if (*rsvn->gpc_mode != '\0') {
				parse_err_multiple_attrs(d, *np);
				return;
			}
			snprintf(rsvn->gpc_mode, BASIL_STRING_SHORT,
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
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
	char	*id;

	if (stack_busted(d))
		return;

	id = handler[d->stack[d->depth]].element;
	for (np=vp=atts, vp++; np && *np && vp && *vp; np=++vp, vp++) {
		xml_dbg("%s: %s = %s", id, *np, *vp);
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

	for (i=0; i<len; i++) {
		if (!isspace(*(s+i)))
			break;
	}
	if (i == len)
		return;
	parse_err_illegal_char_data(d, s);
	return;
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
	int i;

	for (i=1; handler[i].element; i++) {
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
	int i;
	ud_t *d;

	if (!ud)
		return;
	d = (ud_t *)ud;
	xml_dbg("parse_element_start: ELEMENT = %s", el);
	i = handler_find_index(el);
	if (i < 0) {
		sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
		sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
		snprintf(d->message, sizeof(d->message),
			"Unrecognized element start at line %d: %s",
			(int)XML_GetCurrentLineNumber(parser), el);
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
	int i;
	ud_t *d;

	if (!ud)
		return;
	d = (ud_t *)ud;
	xml_dbg("parse_element_end: ELEMENT = %s", el);
	i = handler_find_index(el);
	if (i < 0) {
		sprintf(d->error_class, "%s", BASIL_VAL_PERMANENT);
		sprintf(d->error_source, "%s", BASIL_VAL_SYNTAX);
		snprintf(d->message, sizeof(d->message),
			"Unrecognized element end at line %d: %s",
			(int)XML_GetCurrentLineNumber(parser), el);
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
	d = (ud_t *)ud;
	handler[d->stack[d->depth]].char_data(d, s, len);
	return;
}

/**
 * @brief
 * 	After the Cray inventory XML is parsed, use the resulting structures
 * 	to generate vnodes for the compute nodes and send them to the server.
 *
 * @param brp ALPS inventory responce
 *
 * @return Void
 *
 */
static void
inventory_to_vnodes(basil_response_t *brp)
{
	basil_response_query_inventory_t *inv;
	basil_node_t *node;
	basil_node_segment_t *seg;
	basil_node_processor_t *proc;
	basil_node_memory_t *mem;
	basil_label_t *label;
	basil_node_accelerator_t *accel;
	extern	int	internal_state_update;
	extern  int	num_acpus;
	extern	ulong	totalmem;
	int	atype = READ_WRITE | ATR_DFLAG_CVTSLT;
	int	totaccel = 0;
	int	totcpus;
	long	totmem;
	long	order = 0;
	char	*attr;
	vnl_t	*nv = NULL;
	int	ret;
	char	vname[128];
	hwloc_topology_t	topology;
	char			*xmlbuf;
	int			xmllen;

	if (!brp)
		return;
	if (brp->method != basil_method_query) {
		snprintf(log_buffer, sizeof(log_buffer), "Wrong method: %d", brp->method);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			__func__, log_buffer);
		return;
	}
	if (brp->data.query.type != basil_query_inventory) {
		snprintf(log_buffer, sizeof(log_buffer), "Wrong query type: %d",
			brp->data.query.type);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			__func__, log_buffer);
		return;
	}
	if (*brp->error != '\0') {
		snprintf(log_buffer, sizeof(log_buffer), "Error in BASIL response: %s", brp->error);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			__func__, log_buffer);
		return;
	}

	if (vnl_alloc(&nv) == NULL) {
		log_err(errno, __func__, "vnl_alloc failed!");
		return;
	}
	strncpy(mpphost, brp->data.query.data.inventory.mpp_host,
		sizeof(mpphost)-1);
	mpphost[sizeof(mpphost) - 1] = '\0';
	nv->vnl_modtime = (long)brp->data.query.data.inventory.timestamp;

	/*
	 * add login node
	 */
	ret = 0;
	if (hwloc_topology_init(&topology) == -1)
		ret = -1;
	else if ((hwloc_topology_load(topology) == -1) ||
	         (hwloc_topology_export_xmlbuffer(topology, &xmlbuf, &xmllen) == -1)) {
		hwloc_topology_destroy(topology);
		ret = -1;
	}
	if (ret < 0) {
		/* on any failure above, issue log message */
		log_err(PBSE_SYSTEM, __func__, "topology init/load/export failed");
		return;
	} else {
		char	*lbuf;
		int	lbuflen = xmllen + 1024;

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
			return;
		} else {
			snprintf(lbuf, sizeof(lbuf), "allocated log buffer, len %d", lbuflen);
			log_event(PBSEVENT_DEBUG4, PBS_EVENTCLASS_NODE,
				LOG_DEBUG, __func__, lbuf);
		}
		log_event(PBSEVENT_DEBUG4,
			PBS_EVENTCLASS_NODE,
			LOG_DEBUG, __func__, "topology exported");
		snprintf(lbuf, sizeof(lbuf), "%s%s", NODE_TOPOLOGY_TYPE_HWLOC, xmlbuf);
		if (vn_addvnr(nv, mom_short_name, ATTR_NODE_TopologyInfo,
			lbuf, ATR_TYPE_STR, READ_ONLY, NULL) == -1) {
			hwloc_free_xmlbuffer(topology, xmlbuf);
			hwloc_topology_destroy(topology);
			free(lbuf);
			goto bad_vnl;
		} else {
			snprintf(lbuf, sizeof(lbuf), "attribute '%s = %s%s' added",
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
	snprintf(utilBuffer, sizeof(utilBuffer), "%lu", totalmem);
	/* already exists so don't define type */
	if (vn_addvnr(nv, mom_short_name, attr, utilBuffer, 0, 0, NULL) == -1)
		goto bad_vnl;

	attr = "resources_available.vntype";
	if (vn_addvnr(nv, mom_short_name, attr, CRAY_LOGIN,
		0, 0, NULL) == -1)
		goto bad_vnl;

	attr = "resources_available.PBScrayhost";
	if (vn_addvnr(nv, mom_short_name, attr, mpphost,
		ATR_TYPE_STR, atype, NULL) == -1)
		goto bad_vnl;

	/*
	 * now create the compute nodes
	 */
	inv = &brp->data.query.data.inventory;
	for (order=1, node=inv->nodes; node; node=node->next, order++) {
		char		*arch;
		static int	first_compute_node = 1;

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

		/* Only do this for nodes that have accelerators. */
		if (node->accelerators) {
			for (accel=node->accelerators, totaccel=0;
				accel; accel=accel->next) {
				if (accel->state == basil_accel_state_up)
					/* Only count them if the state is UP */
					totaccel++;
			}
		}

		/*
		 * Initializing these outside the loop for the normal case where
		 * vnode_per_numa_node is not set (or is False)
		 */
		totcpus = 0;
		totmem = 0;

		for (seg=node->segments; seg; seg=seg->next) {
			if (vnode_per_numa_node) {
				snprintf(vname, sizeof(vname), "%s_%ld_%d",
					mpphost, node->node_id, seg->ordinal);
			} else if (seg->ordinal == 0) {
				snprintf(vname, sizeof(vname), "%s_%ld",
					mpphost, node->node_id);
			}

			if (basil_inventory != NULL) {
				if (first_compute_node) {
					first_compute_node = 0;
					attr = ATTR_NODE_TopologyInfo;
					snprintf(utilBuffer, sizeof(utilBuffer), "%ld", order);
					if (vn_addvnr(nv, vname, attr,
						(char *) basil_inventory,
						ATR_TYPE_STR, READ_ONLY,
						NULL) == -1)
						goto bad_vnl;
				}
			} else {
				snprintf(log_buffer, sizeof(log_buffer), "no saved basil_inventory");
				log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
					LOG_DEBUG, __func__, log_buffer);
			}

			attr = "sharing";
			/* already exists so don't define type */
			if (vn_addvnr(nv, vname, attr,
				ND_Force_Exclhost,
				0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScrayorder";
			snprintf(utilBuffer, sizeof(utilBuffer), "%ld", order);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
				ATR_TYPE_LONG, atype,
				NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.arch";
			if (vn_addvnr(nv, vname, attr, arch,
				0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.host";
			snprintf(utilBuffer, sizeof(utilBuffer), "%s_%ld", mpphost, node->node_id);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
				0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScraynid";
			snprintf(utilBuffer, sizeof(utilBuffer), "%ld", node->node_id);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
				ATR_TYPE_STR, atype,
				NULL) == -1)
				goto bad_vnl;

			if (vnode_per_numa_node) {
				attr = "resources_available.PBScrayseg";
				snprintf(utilBuffer, sizeof(utilBuffer), "%d",
					seg->ordinal);
				if (vn_addvnr(nv, vname, attr, utilBuffer,
					ATR_TYPE_STR, atype, NULL) == -1)
					goto bad_vnl;
			}

			attr = "resources_available.vntype";
			if (vn_addvnr(nv, vname, attr, CRAY_COMPUTE,
				0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.PBScrayhost";
			if (vn_addvnr(nv, vname, attr, mpphost,
				ATR_TYPE_STR, atype,
				NULL) == -1)
				goto bad_vnl;

			if (vnode_per_numa_node) {
				attr = "resources_available.ncpus";
				totcpus = 0;
				for (proc=seg->processors; proc; proc=proc->next)
					totcpus++;
				snprintf(utilBuffer, sizeof(utilBuffer), "%d",
					totcpus);
				if (vn_addvnr(nv, vname, attr, utilBuffer,
					0, 0, NULL) == -1)
					goto bad_vnl;

				attr = "resources_available.mem";
				totmem = 0;
				for (mem=seg->memory; mem; mem=mem->next)
					totmem += mem->page_size_kb * mem->page_count;
				snprintf(utilBuffer, sizeof(utilBuffer), "%ldkb",
					totmem);
				if (vn_addvnr(nv, vname, attr, utilBuffer,
					0, 0, NULL) == -1)
					goto bad_vnl;

				for (label=seg->labels; label; label=label->next) {
					snprintf(utilBuffer, sizeof(utilBuffer),
						"resources_available.PBScraylabel_%s",
						label->name);
					if (vn_addvnr(nv, vname, utilBuffer, "true",
						ATR_TYPE_BOOL, atype,
						NULL) == -1)
						goto bad_vnl;
				}
			} else {
				/*
 				 * vnode_per_numa_node is false, which
 				 * means we need to compress all the segment info
 				 * into only one vnode.  We need to 
 				 * total up the cpus and memory for each of the
 				 * segments and report it as part of the
 				 * whole vnode. Add/set labels only once.
 				 * All labels are assumed to be the same on
 				 * all segments.
 				 */
				for (proc=seg->processors; proc; proc=proc->next)
					totcpus++;
				for (mem=seg->memory; mem; mem=mem->next)
					totmem += mem->page_size_kb * mem->page_count;
				if (seg->ordinal == 0) {
					for (label=seg->labels; label; label=label->next) {
						snprintf(utilBuffer, sizeof(utilBuffer),
							"resources_available.PBScraylabel_%s",
							label->name);
						if (vn_addvnr(nv, vname, utilBuffer, "true",
							ATR_TYPE_BOOL, atype,
							NULL) == -1)
							goto bad_vnl;
					}
				}
			}

			/* Only do this for nodes that have accelerators */
			if (node->accelerators) {
				attr = "resources_available.naccelerators";
				if (seg->ordinal == 0) {
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
 					 * The other vnodes must share the
 					 * accelerator count with segment 0 vnodes.
					 */
					snprintf(utilBuffer, sizeof(utilBuffer),
						"@%s_%ld_0",
						mpphost, node->node_id);
				}

				/*
 				 * Avoid calling vn_addvnr() repeatedly when
 				 * creating only one vnode per compute node.
 				 */
				if (vnode_per_numa_node || (seg->ordinal == 0)) {
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
					accel=node->accelerators;
					if (accel->data.gpu) {
						if (strcmp(accel->data.gpu->family, BASIL_VAL_UNKNOWN) == 0) {
							snprintf(log_buffer, sizeof(log_buffer), "The GPU family "
								"value is 'UNKNOWN'.  Check "
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
							if (seg->ordinal == 0) {
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
							if (vn_addvnr(nv, vname, attr,
								utilBuffer, 0,
								0, NULL) == -1)
								goto bad_vnl;
						}
					}
				}
			}
		}
		if (!vnode_per_numa_node) {
			/*
 			 * Since we're creating one vnode that combines
 			 * the info for all the numa nodes,
 			 * we've now cycled through all the numa nodes, so
 			 * we need to set the total number of cpus and total
 			 * memory before moving on to the next node 
 			 */
			attr = "resources_available.ncpus";
			snprintf(utilBuffer, sizeof(utilBuffer), "%d", totcpus);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
				0, 0, NULL) == -1)
				goto bad_vnl;

			attr = "resources_available.mem";
			snprintf(utilBuffer, sizeof(utilBuffer), "%ldkb",
				totmem);
			if (vn_addvnr(nv, vname, attr, utilBuffer,
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

	return;

bad_vnl:
	snprintf(log_buffer, sizeof(log_buffer), "creation of cray vnodes failed at %ld", order);
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
	free(p);
	return;
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
	free(p);
	return;
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
	return;
}

/**
 * @brief
 * 	Destructor function for BASIL response structure.
 *
 * @param brp structure to free
 *
 * @return Void
 * 
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
		} else if (brp->data.query.type == basil_query_engine) {
			if (brp->data.query.data.engine.name)
				free(brp->data.query.data.engine.name);
			if (brp->data.query.data.engine.version)
				free(brp->data.query.data.engine.version);
			if (brp->data.query.data.engine.basil_support)
				free(brp->data.query.data.engine.basil_support);
		}
	}
	free(brp);
	return;
}

/**
 * @brief
 * 	The child side of the request handler that invokes the ALPS client.
 *
 * Setup stdin to map to infd and stdout to map to outfd.  Once that is
 * done, call exec to run the ALPS client.
 *
 * @param[in] infd input file descriptor
 * @param[in] outfd output file descriptor
 *
 * @return exit value of ALPS client
 * @retval 127 failure to setup exec of ALPS client
 *
 * @return  Void
 *
 */
static int
alps_request_child(int infd, int outfd)
{
	char *p;
	int rc;
	int in, out;

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
	if (execl(alps_client, p, (char *)0) < 0)
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
 *
 * @param[in] fdin file descriptor to read XML stream from child
 *
 * @return pointer to filled in response structure
 * @retval NULL no result
 *
 */
static basil_response_t *
alps_request_parent(int fdin)
{
	ud_t ud;
	basil_response_t *brp;
	FILE *in = NULL;
	int status;
	int len, eof;
	int rc;
	int inventory_size = 0;

	in = fdopen(fdin, "r");
	if (!in) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			"Failed to open read FD.");
		return (NULL);
	}
	memset(&ud, 0, sizeof(ud));
	brp = malloc(sizeof(basil_response_t));
	if (!brp) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			"Failed to allocate response structure.");
		return (NULL);
	}
	memset(brp, 0, sizeof(basil_response_t));
	ud.brp = brp;
	parser = XML_ParserCreate(NULL);
	if (!parser) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			"Failed to create parser.");
		free_basil_response_data(brp);
		return (NULL);
	}
	XML_SetUserData(parser, (void *)&ud);
	XML_SetElementHandler(parser, parse_element_start, parse_element_end);
	XML_SetCharacterDataHandler(parser, parse_char_data);

	if (alps_client_out != NULL)
		free(alps_client_out);
	if ((alps_client_out = strdup(NODE_TOPOLOGY_TYPE_CRAY)) == NULL) {
		sprintf(log_buffer, "failed to allocate client output buffer");
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE, LOG_ERR,
			__func__, log_buffer);
		free_basil_response_data(brp);
		return (NULL);
	} else
		inventory_size = strlen(alps_client_out) + 1;
	do {
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
			sprintf(log_buffer, "XML buffer: %s", expatBuffer);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
				LOG_DEBUG, __func__, log_buffer);
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
 *
 * @return pointer to filled in response structure
 * @retval NULL no result
 *
 */
static basil_response_t *
alps_request(char *msg)
{
	int toChild[2];
	int fromChild[2];
	int status;
	pid_t pid;
	pid_t exited;
	size_t msglen, wlen = -1;
	basil_response_t *brp = NULL;
	FILE *fp = NULL;

	if (!alps_client) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_NOTICE, __func__,
			"No alps_client specified in MOM configuration file.");
		return (NULL);
	}
	if (!msg) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			__func__, "No message parameter for method.");
		return (NULL);
	}
	msglen = strlen(msg);
	if (msglen < 32) {
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE, LOG_DEBUG,
			__func__, "ALPS request too short.");
		return (NULL);
	}
	snprintf(log_buffer, sizeof(log_buffer),
		"Sending ALPS request: %s", msg);
	log_event(PBSEVENT_DEBUG2, 0, LOG_DEBUG, __func__, log_buffer);
	if (pipe(toChild) == -1)
		return (NULL);
	if (pipe(fromChild) == -1) {
		(void)close(toChild[0]);
		(void)close(toChild[1]);
		return (NULL);
	}

	pid = fork();
	if (pid < 0) {
		log_err(errno, __func__, "fork");
		(void)close(toChild[0]);
		(void)close(toChild[1]);
		(void)close(fromChild[0]);
		(void)close(fromChild[1]);
		return (NULL);
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
		kill(pid, SIGKILL);	/* don't let child run */
		goto done;
	}

	wlen = fwrite(msg, sizeof(char), msglen, fp);
	if (wlen < msglen) {
		log_err(errno, __func__, "fwrite");
		fclose(fp);
		kill(pid, SIGKILL);	/* don't let child run */
		goto done;
	}

	if (fflush(fp) != 0) {
		log_err(errno, __func__, "fflush");
		fclose(fp);
		kill(pid, SIGKILL);	/* don't let child run */
		goto done;
	}

	fclose(fp);
	brp = alps_request_parent(fromChild[0]);
	if (!brp) {
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
	return;
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
	return;
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
	return;
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
	return;
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
	return;
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
typedef	struct	nodesum {
	char		*name;
	char		*vntype;
	char		*arch;
	long		nid;
	long		mpiprocs;
	long		ncpus;
	long		threads;
	long long	mem;
	long		chunks;
	long		width;
	long		depth;
	enum vnode_sharing_state	share;
	int		naccels;
	int		need_accel;
	char		*accel_model;
	long long	accel_mem;
	int		done;
} nodesum_t;

/**
 * @brief
 * Given a pointer to a PBS job (pjob), validate and construct a BASIL
 * reservation request.
 *
 * A loop goes through each element of the ji_vnods array for the job and
 * looks for entries that have cpus, the name matches mpphost, vntype is
 * CRAY_COMPUTE, and has a value for arch.  Each of these entries causes
 * an entry to be made in the nodes array.  If no vnodes are matched,
 * we can return since no compute nodes are being allocated.
 *
 * An error check is done to be sure no entries in the nodes array have
 * a bad combination of ncpus and mpiprocs.  Then, a double loop is
 * entered that goes through each element of the of the nodes array
 * looking for matching entries.  A match is when depth, width, mem,
 * share, arch, need_accel, accelerator_model and accelerator_mem are
 * all the same.  All matches will be output to
 * a single ReserveParam XML section.  Each node array entry that
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
	basil_reserve_param_t	*pend;
	enum rlplace_value	rpv;
	enum vnode_sharing	vnsv;
	struct passwd *pwent;
	int		i, j, num;
	int		err_ret = 1;
	nodesum_t	*nodes;
	vmpiprocs	*vp;
	size_t		len, nsize;
	char		*cp;

	*req = NULL;

	nodes = (nodesum_t *)calloc(pjob->ji_numvnod, sizeof(nodesum_t));
	if (nodes == NULL)
		return 1;

	rpv = getplacesharing(pjob);

	/*
	 * Go through the vnodes to consolidate the mpi ranks onto
	 * the compute nodes.  The index into ji_vnods will be
	 * incremented by the value of vn_mpiprocs because the
	 * entries in ji_vnods are replicated for each mpi rank.
	 */
	num = 0;
	len = strlen(mpphost);
	for (i=0; i<pjob->ji_numvnod; i += vp->vn_mpiprocs) {
		vnal_t		*vnp;
		char		*vntype, *vnt;
		char		*sharing;
		long		nid;
		int		seg;
		long long	mem;
		char		*arch;
		enum vnode_sharing_state	share;
		vp = &pjob->ji_vnods[i];

		assert(vp->vn_mpiprocs > 0);
		if (vp->vn_cpus == 0)
			continue;

		/*
		 * Skip over vnodes where the name does not begin with the
		 * expected mpphost string
		 */
		if (strncmp(vp->vn_vname, mpphost, len) != 0)
			continue;
		cp = &vp->vn_vname[len];

		/*
		 * The remainder of the vnode name must match "_<num>_<num>"
		 * (when vnode_per_numa_node is enabled) otherwise,
		 * "_<num>" when disabled.
		 */

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
		mem = (vp->vn_mem + vp->vn_mpiprocs - 1)/vp->vn_mpiprocs;
		sharing = attr_exist(vnp, "sharing");
		vnsv = str_to_vnode_sharing(sharing);
		share = vnss[vnsv][rpv];

		/*
		 ** If the vnode is in the array but is setup to use
		 ** different values for ncpus, mpiprocs etc, we need
		 ** to allocate another slot for it so a separate
		 ** ReserveParam XML section is created.
		 */
		for (j=0; j<num; j++) {
			nodesum_t	*ns = &nodes[j];

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
		if (j == num) {		/* need a new entry */
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
	if (num == 0) {	/* no compute nodes -> no reservation */
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

	strncpy(basil_req->batch_id, pjob->ji_qs.ji_jobid,
		sizeof(basil_req->batch_id)-1);
	basil_req->batch_id[sizeof(basil_req->batch_id)-1] = '\0';

	for (i=0; i<num; i++) {
		nodesum_t	*ns = &nodes[i];

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

	for (i=0; i<num ; i++) {
		basil_reserve_param_t		*p;
		basil_nodelist_param_t		*n;
		basil_accelerator_param_t	*a;
		basil_accelerator_gpu_t		*gpu;
		nodesum_t	*ns = &nodes[i];
		char		*arch = ns->arch;
		long long	mem = ns->mem;
		char		*accel_model = ns->accel_model;
		long long	accel_mem = ns->accel_mem;
		long		width;
		long		last_nid, prev_nid;

		if (ns->done)		/* already output */
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
		p->rsvn_mode = (ns->share == isexcl) ?
			basil_rsvn_mode_exclusive : basil_rsvn_mode_shared;

		if (ns->ncpus != ns->threads) {
			sprintf(log_buffer, "ompthreads %ld does not match"
				" ncpus %ld", ns->threads, ns->ncpus);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
				LOG_DEBUG, pjob->ji_qs.ji_jobid,
				log_buffer);
		}

		/*
		 ** Collapse matching entries.
		 */
		for (j=i+1; j<num; j++) {
			nodesum_t	*ns2 = &nodes[j];

			/* Look for matching nid entries that have not
			 *  yet been output.
			 */
			if (ns2->done)
				continue;

			/* If everthing matches, add in this entry
			 *  and mark it done.
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

			if (last_nid == prev_nid)	/* no range */
				sprintf(utilBuffer, ",%ld", ns2->nid);
			else {
				sprintf(utilBuffer, "-%ld,%ld",
					prev_nid, ns2->nid);
			}
			prev_nid = last_nid = ns2->nid;

			/* check to see if we need to get a new nodelist */
			if (strlen(utilBuffer) + 1 >
				nsize - strlen(n->nodelist)) {
				char	*hold;

				nsize *= 2;	/* double size */
				hold = realloc(n->nodelist, nsize);
				if (hold == NULL)
					goto err;
				n->nodelist = hold;
			}
			/* this is safe since we checked for overflow */
			strcat(n->nodelist, utilBuffer);
		}
		p->width = width;
		if (last_nid < prev_nid) {	/* last range */
			size_t	slen;

			sprintf(utilBuffer, "-%ld", prev_nid);
			slen = strlen(utilBuffer) + 1;

			/* check to see if we need to get a new nodelist */
			if (slen > nsize - strlen(n->nodelist)) {
				char	*hold;

				nsize += slen+1;
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
			p->memory->size_mb = (long)((mem+1023)/1024);
			p->memory->type = basil_memory_type_os;
		}
		/*
		 * We don't include checking for ns->naccels here because
		 * ALPS is currently unable to accept a specified count
		 * of accelerators.  Also ALPS currently needs a width
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
					gpu->memory = (unsigned int)((accel_mem+1023)/1024);
				}
			}
		}
		if (strcmp(BASIL_VAL_XT, arch) == 0) {
			p->arch = basil_node_arch_xt;
		} else if (strcmp(BASIL_VAL_X2, arch) == 0) {
			p->arch = basil_node_arch_x2;
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
		"<" BASIL_ELM_REQUEST " "
		BASIL_ATR_PROTOCOL "=\"%s\" "
		BASIL_ATR_METHOD "=\"" BASIL_VAL_RESERVE "\">\n", basilversion);
	add_alps_req(utilBuffer);
	sprintf(utilBuffer,
		" <" BASIL_ELM_RESVPARAMARRAY " "
		BASIL_ATR_USER_NAME "=\"%s\" "
		BASIL_ATR_BATCH_ID "=\"%s\"",
		bresvp->user_name, bresvp->batch_id);
	add_alps_req(utilBuffer);
	if (*bresvp->account_name != '\0') {
		sprintf(utilBuffer, " " BASIL_ATR_ACCOUNT_NAME "=\"%s\"",
			bresvp->account_name);
		add_alps_req(utilBuffer);
	}
	add_alps_req(">\n");
	for (param=bresvp->params; param; param=param->next) {
		add_alps_req("  <" BASIL_ELM_RESERVEPARAM);
		switch (param->arch) {
			case basil_node_arch_x2:
				add_alps_req(" " BASIL_ATR_ARCH "=\""
					BASIL_VAL_X2 "\"");
				break;
			default:
				add_alps_req(" " BASIL_ATR_ARCH "=\""
					BASIL_VAL_XT "\"");
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
				add_alps_req(" " BASIL_ATR_RSVN_MODE "=\""
					BASIL_VAL_EXCLUSIVE "\"");
			} else if (param->rsvn_mode == basil_rsvn_mode_shared) {
				add_alps_req(" " BASIL_ATR_RSVN_MODE "=\""
					BASIL_VAL_SHARED "\"");
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
		if (vnode_per_numa_node && (param->segments[0] != '\0')) {
			snprintf(utilBuffer, sizeof(utilBuffer),
				" " BASIL_ATR_SEGMENTS "=\"%s\"",
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
			for (mem=param->memory; mem; mem=mem->next) {
				add_alps_req("    <" BASIL_ELM_MEMPARAM " "
					BASIL_ATR_TYPE "=\"");
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
			for (label=param->labels; label && *label->name;
				label=label->next) {
				add_alps_req("    <" BASIL_ELM_LABELPARAM " "
					BASIL_ATR_NAME "=");
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
			for (nl=param->nodelists;
				nl && nl->nodelist && *nl->nodelist;
				nl=nl->next) {
				add_alps_req("    <" BASIL_ELM_NODEPARAM ">");
				add_alps_req(nl->nodelist);
				add_alps_req("</" BASIL_ELM_NODEPARAM ">\n");
			}
			add_alps_req("   </" BASIL_ELM_NODEPARMARRAY ">\n");
		}
		if (param->accelerators) {
			add_alps_req("   <" BASIL_ELM_ACCELPARAMARRAY ">\n");
			for (accel = param->accelerators; accel;
				accel=accel->next) {
				add_alps_req("    <" BASIL_ELM_ACCELPARAM " "
					BASIL_ATR_TYPE "=\"" BASIL_VAL_GPU "\"");
				if (accel->data.gpu) {
					if (accel->data.gpu->family) {
						sprintf(utilBuffer, " "
							BASIL_ATR_FAMILY "=\"%s\"",
							accel->data.gpu->family);
						add_alps_req(utilBuffer);
					}
					if (accel->data.gpu->memory > 0) {
						sprintf(utilBuffer, " "
							BASIL_ATR_MEMORY_MB "=\"%d\"",
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
	brp = alps_request(requestBuffer);
	if (!brp) {
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
		"<" BASIL_ELM_REQUEST " "
		BASIL_ATR_PROTOCOL "=\"%s\" "
		BASIL_ATR_METHOD "=\"" BASIL_VAL_CONFIRM "\" "
		BASIL_ATR_RSVN_ID "=\"%ld\" "
		"%s =\"%llu\"/>", basilversion,
		pjob->ji_extended.ji_ext.ji_reservation,
		basil11orig ? BASIL_ATR_ADMIN_COOKIE : BASIL_ATR_PAGG_ID,
		pjob->ji_extended.ji_ext.ji_pagg);
	brp = alps_request(requestBuffer);
	if (!brp) {
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
 *
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
		"<" BASIL_ELM_REQUEST " "
		BASIL_ATR_PROTOCOL "=\"%s\" "
		BASIL_ATR_METHOD "=\"" BASIL_VAL_RELEASE "\" "
		BASIL_ATR_RSVN_ID "=\"%ld\" "
		"%s =\"%llu\"/>", basilversion,
		pjob->ji_extended.ji_ext.ji_reservation,
		basil11orig ? BASIL_ATR_ADMIN_COOKIE : BASIL_ATR_PAGG_ID,
		pjob->ji_extended.ji_ext.ji_pagg);
	brp = alps_request(requestBuffer);
	if (!brp) {
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
			 * error message.  If so, we will assume the ALPS
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
					"reservation %ld.  BASIL response error: %s",
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
 *	 Issue an ENGINE query and determine which version of BASIL
 * 	we should use.
 *
 * @return Void
 *
 */
static void
alps_engine_query(void)
{
	basil_response_t *brp;
	char *ver = NULL;
	char *tmp = NULL;

	new_alps_req();
	/* Try BASIL 1.2 first - it's the most recent BASIL version we understand */
	sprintf(basilversion, BASIL_VAL_VERSION_1_2);
	sprintf(requestBuffer, "<?xml version=\"1.0\"?>\n"
		"<" BASIL_ELM_REQUEST " "
		BASIL_ATR_PROTOCOL "=\"%s\" "
		BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" "
		BASIL_ATR_TYPE "=\"" BASIL_VAL_ENGINE "\"/>", basilversion);
	brp = alps_request(requestBuffer);
	if (brp != NULL) {
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
							if ((strcmp(basilversion, tmp)) == 0) {
								/* Success!  ALPS and PBS speak BASIL 1.2 */
								sprintf(log_buffer, "The basilversion is "
									"set to %s", basilversion);
								log_event(PBSEVENT_DEBUG,
									PBS_EVENTCLASS_NODE,
									LOG_DEBUG, __func__, log_buffer);
								free(ver);
								free_basil_response_data(brp);
								return;
							}
							tmp = strtok(NULL, ",");
						}
						/* We didn't find "1.2" as a supported version  */
						sprintf(log_buffer, "ALPS ENGINE query failed. "
							"Supported BASIL versions returned: "
							"'%s'", ver);
						log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE,
							LOG_NOTICE, __func__, log_buffer);
					} else {
						/* No memory */
						sprintf(log_buffer, "ALPS ENGINE query failed.  No "
							"memory");
						log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE,
							LOG_NOTICE, __func__, log_buffer);
					}
				} /* basil_support isn't in the response fall through
				   * to try the next basil version
				   */
			} else {
				/* wrong method in the response */
				sprintf(log_buffer, "Wrong method, expected: %d but "
					"got: %d", basil_method_query, brp->method);
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
			"version %s.", basilversion);
		/*
		 * We log this a DEBUG3 because BASIL 1.2 may be too new
		 * for this ALPS, and we'll try other BASIL versions next
		 */
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE,
			LOG_NOTICE, __func__, log_buffer);
	}

	if (ver) {
		free(ver);
		ver = NULL;
	}
	free_basil_response_data(brp);

	/* BASIL 1.2 didn't work, Try BASIL 1.1 */
	sprintf(basilversion, BASIL_VAL_VERSION_1_1);
	sprintf(requestBuffer, "<?xml version=\"1.0\"?>\n"
		"<" BASIL_ELM_REQUEST " "
		BASIL_ATR_PROTOCOL "=\"%s\" "
		BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" "
		BASIL_ATR_TYPE "=\"" BASIL_VAL_ENGINE "\"/>",
		basilversion);
	brp = alps_request(requestBuffer);
	if (brp != NULL) {
		if (*brp->error == '\0') {
			/*
			 * There are no errors in the response data.
			 * Check the response method to ensure we have
			 * the correct response.
			 */
			if (brp->method == basil_method_query) {
				/* Check if 'basil_support' is set before doing strdup.
				 * If basil_support is not set, it's likely
				 * CLE 2.2 which doesn't have 'basil_support'
				 */
				if (brp->data.query.data.engine.basil_support != NULL) {
					ver = strdup(brp->data.query.data.engine.basil_support);
					if (ver != NULL) {
						tmp = strtok(ver, ",");
						while (tmp) {
							if ((strcmp(basilversion, tmp)) == 0) {
								/* Success!  ALPS and PBS speak BASIL 1.1 */
								sprintf(log_buffer, "The basilversion is "
									"set to %s", basilversion);
								log_event(PBSEVENT_DEBUG,
									PBS_EVENTCLASS_NODE,
									LOG_DEBUG, __func__, log_buffer);
								free(ver);
								free_basil_response_data(brp);
								return;
							}
							tmp = strtok(NULL, ",");
						}
						/* We didn't find "1.1" as a supported version  */
						sprintf(log_buffer, "ALPS ENGINE query failed. "
							"Supported BASIL versions returned: "
							"'%s'", ver);
						/*
						 * Log this at PBSEVENT_DEBUG level because it
						 * is the last attempt to find a match and we
						 * want to give as much info as we can
						 */
						log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
							LOG_NOTICE, __func__, log_buffer);
					} else {
						/* No memory */
						sprintf(log_buffer, "ALPS ENGINE query failed.  No "
							"memory");
						log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE,
							LOG_NOTICE, __func__, log_buffer);
					}
				} else {
					/* basil_support isn't in the XML response
					 * and the XML wasn't junk, so
					 * assume CLE 2.2 is running.
					 */
					sprintf(log_buffer, "Assuming CLE 2.2 is running, "
						"setting the basilversion to %s", basilversion);
					log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE,
						LOG_DEBUG, __func__, log_buffer);
					sprintf(log_buffer, "The basilversion is "
						"set to %s", basilversion);
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_NODE,
						LOG_DEBUG, __func__, log_buffer);
					free(ver);
					free_basil_response_data(brp);
					return;

				}
			} else {
				/* wrong method in the response */
				sprintf(log_buffer, "Wrong method, expected: %d but "
					"got: %d", basil_method_query, brp->method);
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
			"version %s.", basilversion);
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
			LOG_NOTICE, __func__, log_buffer);
	}

	/*
	 * If we are here, no other BASIL versions have worked
	 * set basilversion to "UNDEFINED"
	 */
	sprintf(basilversion, BASIL_VAL_UNDEFINED);
	sprintf(log_buffer, "No BASIL versions are understood.");
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
		LOG_NOTICE, __func__, log_buffer);

	if (ver)
		free(ver);
	free_basil_response_data(brp);
}

/**
 * @brief
 *	 Issue a request for a system inventory including nodes, CPUs, and
 * 	assigned applications.
 *
 * @return Void
 *
 */
void
alps_inventory(void)
{
	basil_response_t *brp;

	/* Determine what BASIL version we should speak */
	alps_engine_query();
	new_alps_req();
	sprintf(requestBuffer, "<?xml version=\"1.0\"?>\n"
		"<" BASIL_ELM_REQUEST " "
		BASIL_ATR_PROTOCOL "=\"%s\" "
		BASIL_ATR_METHOD "=\"" BASIL_VAL_QUERY "\" "
		BASIL_ATR_TYPE "=\"" BASIL_VAL_INVENTORY "\"/>", basilversion);
	brp = alps_request(requestBuffer);
	if (!brp) {
		sprintf(log_buffer, "ALPS inventory request failed.");
		log_event(PBSEVENT_SYSTEM, PBS_EVENTCLASS_NODE,
			LOG_NOTICE, __func__, log_buffer);
		return;
	}
	if (basil_inventory != NULL)
		free(basil_inventory);
	basil_inventory = strdup(alps_client_out);
	if (basil_inventory == NULL) {
		sprintf(log_buffer, "failed to save inventory response");
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_NODE, LOG_ERR,
			__func__, log_buffer);
	}
	inventory_to_vnodes(brp);
	free_basil_response_data(brp);
	return;
}

/**
 * Define the array that is used to register the expat element handlers.
 * See parse_element_start, parse_element_end, and parse_char_data for
 * further information.
 * The definition of element_handler_t above explains the different
 * structure elements.
 */
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
		NULL,
		NULL,
		NULL,
		NULL
	}
};
#endif /* MOM_ALPS */
