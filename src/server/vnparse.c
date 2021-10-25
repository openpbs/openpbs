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
 *
 *@brief
 * 		Functions which provide basic operation on the parsing of vnl files.
 *
 */
#include	<sys/types.h>
#include	<sys/stat.h>
#include	<assert.h>
#include	<ctype.h>
#include	<errno.h>
#include	<stdio.h>
#include	<string.h>
#include	<stdlib.h>
#include	<unistd.h>
#include	<time.h>
#include	"dis.h"
#include	"pbs_error.h"
#include	"log.h"
#include	"placementsets.h"
#include	"pbs_config.h"
#include	"list_link.h"
#include	"attribute.h"
#include	"pbs_nodes.h"
#include	"cmds.h"
#include	"server.h"
#include	"queue.h"
#include	"pbs_reliable.h"

static vnal_t	*vnal_alloc(vnal_t **);
static vnal_t	*id2vnrl(vnl_t *, char *);
static vna_t	*attr2vnr(vnal_t *, char *);

static const char	iddelim = ':';
static const char	attrdelim = '=';

extern char	*msg_err_malloc;

/**
 * @brief
 *		Exported interfaces responsible for opening and reading the given file
 *		(which should contain vnode-specific data in the form described in the
 *		design document), parsing it into a vnl_t (see "placementsets.h").
 *		On error, NULL is returned;  on success, a pointer to the resulting
 *		vnl_t structure is returned.  Space allocated by the parse functions
 *		should be freed with vnl_free() below.
 *
 *		In order to allow the user to effect actions based on the attributes
 *		or vnode IDs, a callback function may be supplied.  It will be called
 *		before inserting a new name/value pair, and supplied the vnode ID,
 *		attribute name and value;  if it returns zero, the insertion of the
 *		given <ID, name, value> tuple will not occur but processing of the
 *		file will continue normally.
 *
 * @param[in]	file	-	file which should contain vnode-specific data
 * 							in the form described in the design document.
 * @param[in]	callback	-	callback function which will be called
 * 								before inserting a new name/value pair.
 *
 * @return	vnl_t structure
 */
vnl_t *
vn_parse(const char *file, callfunc_t callback)
{
	FILE	*fp;
	vnl_t	*vnlp;

	if ((fp = fopen(file, "r")) == NULL) {
		sprintf(log_buffer, "%s", file);
		log_err(errno, __func__, log_buffer);
		return NULL;
	}

	vnlp = vn_parse_stream(fp, callback);

	(void) fclose(fp);
	return (vnlp);
}

/**
 * @brief
 * 		Read a configuration file.  The lines of the file have the form:
 * @par
 * 		@verbatim
 * 		<ID><IDDELIM><ATTRNAME><ATTRDELIM><ATTRVAL> [<TYPE> <ATTRDELIM> <TYPEVAL>]
 * @par
 * 		For example:
 * 		fred: thing = blue   type = string_array
 * 		@endverbatim
 * @par
 * 		where <ID>, <ATTRNAME>, <ATTRVAL> and <TYPEVAL>
 * 		are all strings; <IDDELIM> and <ATTRDELIM> are
 * 		characters (':' and '=' respectively - see iddelim,
 * 		attrdelim above); <TYPE> is the literal string "type" and
 * 		begins an optional section used to define the data type for <ATTRNAME>.
 *
 * @param[in]	file	-	file which should contain vnode-specific data
 * 							in the form described in the design document.
 * @param[in]	callback	-	callback function which will be called
 * 								before inserting a new name/value pair.
 *
 * @return	vnl_t structure
 */
vnl_t *
vn_parse_stream(FILE *fp, callfunc_t callback)
{
	int		linenum;
	char		linebuf[BUFSIZ];
	vnl_t		*vnlp = NULL;
	struct stat	sb;
	static	char	type[] = "type";

	if (vnl_alloc(&vnlp) == NULL) {
		return NULL;
	}

	if (fstat(fileno(fp), &sb) == -1) {
		log_err(errno, __func__, "fstat");
		vnl_free(vnlp);
		return NULL;
	} else
		vnlp->vnl_modtime = sb.st_mtime;

	/*
	 *	linenum begins at 1, not 0, because of the implicit assumption
	 *	that each file we're asked to parse must have begun with a line
	 *	of the form
	 *
	 *		$configversion	...
	 */
	linenum = 1;
	while (fgets(linebuf, sizeof(linebuf), fp) != NULL) {
		char	*p, *opt;
		char	*tokbegin, *tokend;
		char	*pdelim;
		char	*vnid;		/* vnode ID */
		char	*attrname;	/* attribute name */
		char	*attrval;	/* attribute value */
		char	*vnp;		/* vnode ID ptr*/
		int	 typecode = 0;	/* internal attribute type */
		/* internal attribute flag, default */
		int	 typeflag = READ_WRITE | ATR_DFLAG_CVTSLT;
		struct resc_type_map *ptmap;

		/* cost of using fgets() - have to remove trailing newline */
		if ((p = strrchr(linebuf, '\n')) != NULL) {
			*p = '\0';
			linenum++;
		} else {
			sprintf(log_buffer, "line %d not newline-terminated",
				linenum);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		}

		/* ignore initial white space;  skip blank lines */
		p = linebuf;
		while ((*p != '\0') && isspace(*p))
			p++;
		if (*p == '\0')
			continue;

		/* <ID> <IDDELIM> */
		if ((pdelim = strchr(linebuf, iddelim)) == NULL) {
			sprintf(log_buffer, "line %d:  missing '%c'", linenum,
				iddelim);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		}
		while ((p < pdelim) && isspace(*p))
			p++;
		if (p == pdelim) {
			sprintf(log_buffer, "line %d:  no vnode id",
				linenum);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		} else {
			tokbegin = p;
			while ((p < pdelim) && !isspace(*p))
				p++;
			tokend = p;
			*tokend = '\0';
			vnid = tokbegin;
		}

		/*
		 * Validate the vnode name here in MOM before sending UPDATE2
		 * command to SERVER (is_request()->update2_to_vnode()->
		 * create_pbs_node()) to create the vnode. MOM does not allow
		 * any invalid character in vnode name which is not supported
		 * by PBS server.
		 */
		for (vnp = vnid; *vnp && legal_vnode_char(*vnp, 1); vnp++)
			;
		if (*vnp) {
			log_errf(PBSE_SYSTEM, __func__, "invalid character in vnode name \"%s\"", vnid);
			vnl_free(vnlp);
			return NULL;
		}
		/* Condition to make sure that vnode name should not exceed
		 * PBS_MAXHOSTNAME i.e. 64 characters. This is because the
		 * corresponding column nd_name in the database table pbs.node
		 * is defined as string of length 64.
		 */
		if (strlen(vnid) > PBS_MAXHOSTNAME) {
			log_errf(PBSE_SYSTEM, __func__, "Node name \"%s\" is too big", vnid);
			return NULL;
		}
		/* <ATTRNAME> <ATTRDELIM> */
		p = pdelim + 1;		/* advance past iddelim */
		if ((pdelim = strchr(p, attrdelim)) == NULL) {
			sprintf(log_buffer, "line %d:  missing '%c'", linenum,
				attrdelim);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		}
		while ((p < pdelim) && isspace(*p))
			p++;
		if (p == pdelim) {
			sprintf(log_buffer, "line %d:  no attribute name",
				linenum);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		} else {
			tokbegin = p;
			while ((p < pdelim) && !isspace(*p))
				p++;
			tokend = p;
			*tokend = '\0';
			attrname = tokbegin;
		}

		/* <ATTRVAL> */
		p = pdelim + 1;		/* advance past attrdelim */
		while (isspace(*p))
			p++;
		if (*p == '\0') {
			sprintf(log_buffer, "line %d:  no attribute value",
				linenum);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		}

		/*
		 * Check to see if the optional "type" section exists.
		 */
		tokbegin = NULL;
		opt = strchr(p, attrdelim);
		if (opt != NULL) {	/* found one */
			opt--;		/* skip backward from '=' */
			while ((p < opt) && isspace(*opt))
				opt--;
			if (p < opt) {	/* check for "type" */
				/*
				 * We want to see if the string value
				 * of "type" exists.  opt is pointing to
				 * the first non-space char so back up
				 * enough to get to the beginning of "type".
				 * The sizeof(type) is the same as strlen+1
				 * so we need to backup sizeof(type)-2 to
				 * get to the beginning of "type".
				 */
				opt -= (sizeof(type)-2);
				if ((p < opt) && (strncmp(opt, type,
					sizeof(type)-1) == 0)) {
					tokend = opt-1;
					/* must have a space before "type" */
					if (isspace(*tokend)) {
						tokbegin = p;
						*tokend = '\0';
						p = opt;
					}
				}
			}
		}
		if (tokbegin == NULL) {	/* no optional section */
			tokbegin = p;
			while (*p != '\0')
				p++;
			tokend = p;
		}

		/*
		 * The attribute value needs to be checked for
		 * bad chars.  The only one is attrdelim '='.
		 */
		attrval = tokbegin;
		if (strchr(attrval, attrdelim) != NULL) {
			sprintf(log_buffer,
				"line %d:  illegal char '%c' in value",
				linenum, attrdelim);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		}

		/* look for optional "keyword = typeval" */
		while ((*p != '\0') && isspace(*p))
			++p;
		if (*p != '\0') {
			/* there is a keyword ("type") */
			if ((pdelim = strchr(p, attrdelim)) == NULL) {
				sprintf(log_buffer, "line %d:  missing '%c'",
					linenum, attrdelim);
				log_err(PBSE_SYSTEM, __func__, log_buffer);
				vnl_free(vnlp);
				return NULL;
			}
			tokbegin = p;
			while ((p < pdelim) && !isspace(*p))
				p++;
			tokend = p;
			*tokend = '\0';
			p = pdelim + 1;
			if (strcmp(tokbegin, type) == 0) {
				while (isspace(*p))
					++p;
				if (*p == '\0') {
					sprintf(log_buffer,
						"line %d:  no keyword value",
						linenum);
					log_err(PBSE_SYSTEM, __func__, log_buffer);
					vnl_free(vnlp);
					return NULL;
				}
				tokbegin = p;
				while ((*p != '\0') && !isspace(*p))
					++p;
				tokend = p;
				*tokend = '\0';
				ptmap = find_resc_type_map_by_typest(tokbegin);
				if (ptmap == NULL) {
					sprintf(log_buffer,
						"line %d: invalid type '%s'",
						linenum, tokbegin);
					log_err(PBSE_SYSTEM, __func__,
						log_buffer);
					vnl_free(vnlp);
					return NULL;
				}
				typecode = ptmap->rtm_type;

			} else {
				sprintf(log_buffer,
					"line %d:  invalid keyword '%s'",
					linenum, tokbegin);
				log_err(PBSE_SYSTEM, __func__, log_buffer);
				vnl_free(vnlp);
				return NULL;
			}


		}

		if (vn_addvnr(vnlp, vnid, attrname, attrval, typecode,
			typeflag, callback) == -1) {
			sprintf(log_buffer,
				"line %d:  vn_addvnr failed", linenum);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		}
	}

	return ((vnl_t *) vnlp);
}

/**
 * @brief
 *		Merge data from the newly-parse vnode list (new) into a previously-
 *		parsed one (cur) adding any attribute/value pairs found in new to
 *		cur, and overwriting any duplicate attributes with new's values.
 *		If successful, cur is returned, otherwise NULL.
 *
 * @param[in,out]	cur	-	previously-parsed one (cur)
 * @param[in]	new	-	newly-parse vnode list (new)
 * @param[in]	callback	-	callback function which will be called
 * 								before inserting a new name/value pair.
 */
vnl_t *
vn_merge(vnl_t *cur, vnl_t *new, callfunc_t callback)
{
	unsigned long	i, j;

	for (i = 0; i < new->vnl_used; i++) {
		vnal_t	*newreslist = VNL_NODENUM(new, i);

		for (j = 0; j < newreslist->vnal_used; j++) {
			vna_t	*newres = VNAL_NODENUM(newreslist, j);

			if (vn_addvnr(cur, newreslist->vnal_id,
				newres->vna_name, newres->vna_val,
				newres->vna_type, newres->vna_flag,
				callback) == -1)
				return NULL;
		}
	}

	cur->vnl_modtime = (cur->vnl_modtime > new->vnl_modtime) ?
		cur->vnl_modtime : new->vnl_modtime;
	return (cur);
}

/**
 * @brief
 *		Merge data from the newly-parse vnode list (new) into a previously-
 *		parsed one (cur) adding any attribute/value pairs of those attribute
 *		names listed in the 'allow_attribs'.
 *		This overwrites any duplicate attributes with new's values.
 * @note
 *		An entry in 'new' will be matched just before a dot (.) in the name
 *		if one exists.
 *		For example, a 'new' entry of "resources_available.ncpus" will
 *		match with 'allow_attribs' entry of "resources_available".
 *
 * @param[in]	cur - previously parsed vnode list
 * @param[in]	new - newly parsed vnode list
 * @param[in]	allow_attribs - list of attribute names to to match
 *
 * @return	vnl_t *
 * @retval	cur	- if successful
 * @retval	NULL	- if not successful.
 */
vnl_t *
vn_merge2(vnl_t *cur, vnl_t *new, char **allow_attribs, callfunc_t callback)
{
	unsigned long i, j;
	char *vna_name, *dot;
	int match;

	for (i = 0; i < new->vnl_used; i++) {
		vnal_t *newreslist = VNL_NODENUM(new, i);

		for (j = 0; j < newreslist->vnal_used; j++) {
			vna_t *newres = VNAL_NODENUM(newreslist, j);

			vna_name = newres->vna_name;
			dot = strchr(vna_name, (int) '.');
			if (dot)
				*dot = '\0';

			/* match up to but not including dot */
			match = is_string_in_arr(allow_attribs, vna_name);
			if (dot)
				*dot = '.'; /* restore */
			if (!match)
				continue;

			if (vn_addvnr(cur, newreslist->vnal_id,
				      newres->vna_name, newres->vna_val,
				      newres->vna_type, newres->vna_flag,
				      callback) == -1)
				return NULL;
		}
	}

	cur->vnl_modtime = cur->vnl_modtime > new->vnl_modtime ? cur->vnl_modtime : new->vnl_modtime;
	return cur;
}

/**
 * @brief
 * 		Search for an attribute in a vnode.
 *
 * @param[in]	vnrlp	-	vnode to check
 * @param[in]	attr	-	check for the existence of the given attribute
 *
 * @return	atrribute value
 * @retval	NULL	: not found
 */
char *
attr_exist(vnal_t *vnrlp, char *attr)
{
	vna_t	*vnrp;

	if (vnrlp == NULL)
		return NULL;

	if ((vnrp = attr2vnr(vnrlp, attr)) == NULL)
		return NULL;

	return vnrp->vna_val;
}

/**
 * @brief
 * 		Check if a vnode exists.
 *
 * @param[in]	vnlp	-	vnode to check
 * @param[in]	id	-	vnode name to look for
 *
 * @return	vnal_t *
 */
vnal_t *
vn_vnode(vnl_t *vnlp, char *id)
{
	if (vnlp == NULL)
		return NULL;
	return id2vnrl(vnlp, id);
}

/**
 * @brief
 * 		Search for a named vnode, then search for an attribute in that vnode.
 *
 * @param[in]	vnlp	-	vnode list to search
 * @param[in]	id	-	vnode name to look for
 * @param[in]	attr	-	check for the existence of the given attribute
 *
 * @return	atrribute value
 * @retval	NULL	: not found
 */
char *
vn_exist(vnl_t *vnlp, char *id, char *attr)
{
	vnal_t	*vnrlp;

	if (vnlp == NULL)
		return NULL;
	if ((vnrlp = id2vnrl(vnlp, id)) == NULL)
		return NULL;

	return attr_exist(vnrlp, attr);
}

/**
 * @brief
 *		Add the given attribute (attr) and value (attrval) to the vnode with
 *		ID id;  if no vnode with the given ID is found, one is created.
 *
 * @param[in,out]	vnlp	-	vnode list to search
 * @param[in]	id	-	vnode name to look for
 * @param[in]	attr	-	check for the existence of the given attribute
 * @param[in]	attrval	-	attribute value
 * @param[in]	attrtype	-	attribute type
 * @param[in]	attrflags	-	attribute flags
 * @param[in]	callback	-	callback function which will be called
 * 								before inserting a new name/value pair.
 *
 * @return	int
 * @retval	-1	: error
 * @retval	0	: success
 */
int
vn_addvnr(vnl_t *vnlp, char *id, char *attr, char *attrval,
	int attrtype, int attrflags, callfunc_t callback)
{
	vnal_t	*vnrlp;
	vna_t	*vnrp;
	char	*newid, *newname, *newval;

	if ((callback != NULL) && (callback(id, attr, attrval) == 0))
		return (0);

	if ((newname = strdup(attr)) == NULL) {
		return (-1);
	} else if ((newval = strdup(attrval)) == NULL) {
		free(newname);
		return (-1);
	}

	if ((vnrlp = id2vnrl(vnlp, id)) == NULL) {
		if ((newid = strdup(id)) == NULL) {
			free(newval);
			free(newname);
			return (-1);
		}

		/*
		 *	No vnode_attrlist with this ID - add one.
		 */
		if ((vnlp->vnl_used >= vnlp->vnl_nelem) &&
			(vnl_alloc(&vnlp) == NULL)) {
			free(newid);
			free(newval);
			free(newname);
			return (-1);
		}
		vnlp->vnl_cur = vnlp->vnl_used++;
		if (pbs_idx_insert(vnlp->vnl_ix, id, (void *)vnlp->vnl_dl.dl_cur) != PBS_IDX_RET_OK) {
			free(newid);
			free(newval);
			free(newname);
			return (-1);
		}
		vnrlp = CURVNLNODE(vnlp);
		vnrlp->vnal_id = newid;
	}

	if ((vnrp = attr2vnr(vnrlp, attr)) == NULL) {
		/*
		 *	No vnode_attr for this attribute - add one.
		 */
		if ((vnrlp->vnal_used >= vnrlp->vnal_nelem) &&
			(vnal_alloc(&vnrlp) == NULL)) {
			free(newval);
			free(newname);
			return (-1);
		}
		vnrlp->vnal_cur = vnrlp->vnal_used++;
		vnrp = CURVNRLNODE(vnrlp);
	} else {
		free(vnrp->vna_name);
		free(vnrp->vna_val);
	}

	vnrp->vna_name = newname;
	vnrp->vna_val = newval;
	vnrp->vna_type = attrtype;
	vnrp->vna_flag = attrflags;
	return (0);
}

/**
 * @brief
 *		If a vnal_t entry with the given ID (id) exists, return a pointer
 *		to it;  otherwise NULL is returned.
 *
 * @param[in,out]	vnlp	-	vnode list to search
 * @param[in]	id	-	vnode name to look for
 *
 * @return	vnal_t *
 * @retval	a pointer to vnal_t	: entry with the given ID (id) exists
 * @retval	NULL	: does not exists.
 */
static vnal_t *
id2vnrl(vnl_t *vnlp, char *id)
{
	unsigned long i = 0;
	if (vnlp != NULL && pbs_idx_find(vnlp->vnl_ix, (void **)&id, (void **)&i, NULL) == PBS_IDX_RET_OK) {
		vnal_t	*vnrlp = VNL_NODENUM(vnlp, i);

		return (vnrlp);
	}

	return NULL;
}

/**
 * @brief
 *		If a vna_t entry with the given ID attribute (attr), return a pointer
 *		to it;  otherwise NULL is returned.
 *
 * @param[in]	vnrlp	-	vnode list to search
 * @param[in]	attr	-	check for the existence of the given attribute
 *
 * @return	vnal_t *
 * @retval	a pointer to vnal_t	: entry with the given ID (attr) exists
 * @retval	NULL	: does not exists.
 */
static vna_t *
attr2vnr(vnal_t *vnrlp, char *attr)
{
	unsigned long	i;

	if (vnrlp == NULL || attr == NULL)
		return NULL;

	for (i = 0; i < vnrlp->vnal_used; i ++) {
		vna_t	*vnrp = VNAL_NODENUM(vnrlp, i);

		if (strcmp(vnrp->vna_name, attr) == 0)
			return vnrp;
	}

	return NULL;
}

/**
 * @brief
 * 		free the given vnl_t
 *
 * @param[in]	vnlp	-	vnl_t which needs to be freed.
 */
void
vnl_free(vnl_t *vnlp)
{
	unsigned long	i, j;

	if (vnlp) {
		assert(vnlp->vnl_list != NULL);
		if (vnlp->vnl_used == 0 && vnlp->vnl_nelem && vnlp->vnl_list) {
			vnal_t *vnrlp = (vnal_t *) vnlp->vnl_list;
			free(vnrlp->vnal_list);
		}
		for (i = 0; i < vnlp->vnl_used; i++) {
			vnal_t *vnrlp = VNL_NODENUM(vnlp, i);

			assert(vnrlp->vnal_list != NULL);
			for (j = 0; j < vnrlp->vnal_used; j++) {
				vna_t *vnrp = VNAL_NODENUM(vnrlp, j);

				free(vnrp->vna_name);
				free(vnrp->vna_val);
			}
			free(vnrlp->vnal_list);
			free(vnrlp->vnal_id);
		}
		free(vnlp->vnl_list);
#ifdef PBS_MOM
		pbs_idx_destroy(vnlp->vnl_ix);
#endif /* PBS_MOM */
		free(vnlp);
	}
}

/**
 * @brief
 *		Check character in a vnode name.
 *
 * @param[in]	c	-	character in a vnode name.
 * @param[in]	extra	-	extra should be non-zero if a period, '.', is to be accepted
 *
 * @return	int
 * @retval	1	: character is legal in a vnode name
 * @retval	0	: character is not legal in a vnode name
 */
int
legal_vnode_char(char c, int extra)
{
	if (isalnum((int)c) ||
		(c == '-') || (c == '_') || (c == '@') ||
		(c == '[') || (c == ']') || (c == '#') || (c == '^') ||
		(c == '/') || (c == '\\'))
		return 1;	/* ok */
	if (extra == 1) {
		/* extra character, the period,  allowed */
		if (c == '.')
			return 1;
	} else if (extra == 2) {
		/* extra characters, the period and comma,  allowed */
		if ((c == '.') || (c == ','))
			return 1;
	} else {
		if (c == ',')
			return 1;
	}
	return 0;
}


/**
 *
 * @brief
 * 		Parse tokens in the nodes file
 *
 * @par
 *		Token is returned, if null then there was none.
 *		If there is an error, then "err" is set non-zero.
 *		On following call, with argument "start" as null pointer, then
 *		resume where it left off.
 *
 * @param[in]	start	-	where the parsing last left off. If start is NULL,
 *							then restart where the function last left off.
 * @param[in]	cok	-	states if certain characters are legal, separaters,
 *						or are illegal.   If cok is
 *						0: '.' and '=' are separators, and ',' is ok:
 *		   	   			'=' as separator between "keyword" and "value", and
 *		   	   			'.' between attribute and resource.
 *						1: '.' is allowed as character and '=' is illegal
 *						2: use quoted string parsing rules
 *						Typically "cok" is 1 when parsing what should be the
 *						vnode name:
 *			   				0 when parsing attribute/resource names
 *			   				2 when parsing (resource) values
 * @param[out]	err	-	returns in '*err' the error return code
 * @param[out]	term	-	character terminating token.
 *
 * @return	char *
 * @retval	<value>	Returns the get next element (resource or value) as
 *			next token.
 *
 * @note
 * 		If called with cok = 2, the returned value, if non-null, will be on the
 * 		heap and must be freed by the caller.
 *
 * @par MT-safe: No
 */

char *
parse_node_token(char *start, int cok, int *err, char *term)
{
	static char *pt;
	char        *ts;
	char        quote;
	char	    *rn;

	*err = 0;
	if (start)
		pt = start;

	if (cok == 2) {
		/* apply quoted value parsing rules */
		if ((*err = pbs_quote_parse(pt, &rn, &ts, QMGR_NO_WHITE_IN_VALUE)) == 0) {
			*term = *ts;
			if (*ts != '\0')
				pt =  ts + 1;
			else
				pt = ts;
			return rn;
		} else {
			return NULL;
		}

	}

	while (*pt && isspace((int)*pt))	/* skip leading whitespace */
		pt++;
	if (*pt == '\0')
		return NULL;		/* no token */

	ts = pt;

	/* test for legal characters in token */

	for (; *pt; pt++) {
		if (*pt == '\"') {
			quote = *pt;
			++pt;
			while (*pt != '\0' && *pt != quote)
				pt++;
			quote = 0;
		}
		else  {
			if (legal_vnode_char(*pt, cok) || (*pt == ':'))
				continue;		/* valid anywhere */
			else if (isspace((int)*pt))
				break;			/* separator anywhere */
			else if (!cok && (*pt == '.'))
				break;			/* separator attr.resource */
			else if (!cok && (*pt == '='))
				break;			/* separate attr(.resc)=value */
			else
				*err = 1;
		}
	}
	*term = *pt;
	*pt   = '\0';
	pt++;
	return (ts);
}

#define	VN_NCHUNKS	4	/* number of chunks to allocate initially */
#define	VN_MULT		4	/* multiplier for next allocation size */

/**
 * @brief
 *		Handle initial allocation of a vnl_t as well as reallocation when
 *		we run out of space.  The list of vnodes (vnl_t) and the attributes
 *		for each (vnal_t) are initially allocated VN_NCHUNKS entries;  when
 *		that size is outgrown, a list VN_MULT times the current size is
 *		reallocated.
 *
 * @param[out]	vp	-	vnl_t which requires allocation or reallocation.
 */
vnl_t *
vnl_alloc(vnl_t **vp)
{
	vnl_t		*newchunk;
	vnal_t		*newlist;

	assert(vp != NULL);
	if (*vp == NULL) {
		/*
		 *	Allocate chunk structure and first chunk of
		 *	VN_NCHUNKS attribute list entries.
		 */
		if ((newchunk = malloc(sizeof(vnl_t))) == NULL) {
			sprintf(log_buffer, "malloc vnl_t");
			log_err(errno, __func__, log_buffer);
			return NULL;
		}

		newlist = NULL;
		if (vnal_alloc(&newlist) == NULL) {
			free(newchunk);
			return NULL;
		}
		if ((newchunk->vnl_ix = pbs_idx_create(0, 0)) == NULL) {
			free(newchunk);
			return NULL;
		}
		newchunk->vnl_list = newlist;
		newchunk->vnl_nelem = 1;
		newchunk->vnl_cur = 0;
		newchunk->vnl_used = 0;
		newchunk->vnl_modtime = time(NULL);
		return (*vp = newchunk);
	} else {
		/*
		 *	Reallocate a larger chunk, multiplying the number of
		 *	entries by VN_MULT and initializing the new ones to 0.
		 */
		int	cursize = (*vp)->vnl_nelem;
		int	newsize = cursize * VN_MULT;

		assert((*vp)->vnl_list != NULL);
		if ((newlist = realloc((*vp)->vnl_list,
			newsize * sizeof(vnal_t))) == NULL) {
			sprintf(log_buffer, "realloc vnl_list");
			log_err(errno, __func__, log_buffer);
			return NULL;
		} else {
			(*vp)->vnl_list = newlist;
			memset(((vnal_t *)(*vp)->vnl_list) + cursize, 0,
				((newsize - cursize) * sizeof(vnal_t)));
			(*vp)->vnl_nelem = newsize;
			return (*vp);
		}
	}
}

/**
 * @brief
 *		Handle initial allocation of a vnal_t as well as reallocation when
 *		we run out of space.  The list of vnode attributes for a given vnode
 *		(vnal_t) is initially allocated VN_NCHUNKS entries;  when that size
 *		is outgrown, a list VN_MULT times the current size is reallocated.
 *
 * @param[out]	vp	-	vnl_t which requires allocation or reallocation.
 */
static vnal_t *
vnal_alloc(vnal_t **vp)
{
	vnal_t		*newchunk;
	vna_t		*newlist;

	assert(vp != NULL);
	if (*vp == NULL) {
		/*
		 *	Allocate chunk structure and first chunk of
		 *	VN_NCHUNKS attribute list entries.
		 */
		if ((newchunk = malloc(sizeof(vnal_t))) == NULL) {
			sprintf(log_buffer, "malloc vnal_t");
			log_err(errno, __func__, log_buffer);
			return NULL;
		}
		if ((newlist = calloc(VN_NCHUNKS, sizeof(vna_t))) == NULL) {
			sprintf(log_buffer, "calloc vna_t");
			log_err(errno, __func__, log_buffer);
			free(newchunk);
			return NULL;
		} else {
			newchunk->vnal_nelem = VN_NCHUNKS;
			newchunk->vnal_cur = 0;
			newchunk->vnal_used = 0;
			newchunk->vnal_list = newlist;
			return (*vp = newchunk);
		}
	} else {
		/*
		 *	Reallocate a larger chunk, multiplying the number of
		 *	entries by VN_MULT and initializing the new ones to 0.
		 */
		int	cursize = (*vp)->vnal_nelem;
		int	newsize = (cursize == 0 ? 1 : cursize) * VN_MULT;

		if ((newlist = realloc((*vp)->vnal_list,
			newsize * sizeof(vna_t))) == NULL) {
			sprintf(log_buffer, "realloc vnal_list");
			log_err(errno, __func__, log_buffer);
			return NULL;
		} else {
			(*vp)->vnal_list = newlist;
			memset(((vna_t *)(*vp)->vnal_list) + cursize, 0,
				((newsize - cursize) * sizeof(vna_t)));
			(*vp)->vnal_nelem = newsize;
			return (*vp);
		}
	}
}

/**
 * @brief
 *	This return 1 if the given 'host' and 'part' matches the
 *	parent mom of node 'pnode'.
 *
 * @param[in]	pnode - the node to match host against
 * @param[in]	node_parent_host - if pnode is NULL, consults this as node parent host.
 * @param[in]	host - hostname to match
 * @param[in]	port - port to match
 *
 * @return int
 * @retval 1	- if true
 * @retval 0 	- if  false
 */
static int
is_parent_host_of_node(pbsnode *pnode, char *node_parent_host, char *host, int port)
{
	if (((pnode == NULL) && (node_parent_host == NULL)) || (host == NULL))
		return (0);

	if (pnode == NULL) {
		if (strcmp(node_parent_host, host) == 0)
			return (1);

	} else {
		int	i;
		for (i = 0; i < pnode->nd_nummoms; i++) {
			if ((strcmp(pnode->nd_moms[i]->mi_host, host) == 0) &&
		    	    (pnode->nd_moms[i]->mi_port == port)) {
				return (1);
			}
		}
	}
	return (0);
}

/**
 *
 * @brief
 *	Return <resource>=<value> entries in 'chunk' where
 *	<resource> does not appear in the comma-separated
 *	list 'res_list'.
 * @par
 *	For example, suppposed:
 *		res_list = <resA>,<resB>
 *	and
 *		chunk = <resB>=<valB>:<resC>=<valC>:<resD>=<valD>
 *
 *	then this function returns:
 *		<resC>=<valC>:<resD>=<valD>
 *
 * @param[in]	res_list - the resources list
 * @param[in]	chunk - the chunk to check for new resources.
 *
 * @return char *
 * @retval != NULL	the resources that are used in 'chunk',
 *			but not in 'res_list'.
 * @retval == NULL	if error encountered.
 *
 * @note
 *	The returned string points to a statically allocated buffer
 *	that must not be freed, and will get overwritten on the
 *	next call to this function.
 *
 */
static char *
return_missing_resources(char *chunk, char *res_list)
{
	int             snc;
 	int             snelma;
	static int	snelmt = 0;       /* must be static per parse_chunk_r() */
	static key_value_pair *skv = NULL; /* must be static per parse_chunk_r() */
	int		rc = 0;
	static char	*ret_buf = NULL;
	static int	ret_buf_size = 0;
	int		l;
	char		*chunk_dup = NULL;

	if ((res_list == NULL) || (chunk == NULL)) {
		log_err(-1, __func__, "bad params passed");
		return (NULL);
	}

	if (ret_buf == NULL) {
		int chunk_len;

		chunk_len = strlen(chunk);
		ret_buf = malloc(chunk_len + 1);
		if (ret_buf == NULL) {
			log_err(errno, __func__, "malloc failed");
			return NULL;
		}
		ret_buf_size = chunk_len;
	}

	chunk_dup = strdup(chunk);
	if (chunk_dup == NULL) {
		log_err(errno, __func__, "strdup failed on chunk");
		return (NULL);
	}
	rc = parse_chunk_r(chunk_dup, &snc, &snelma,
		&snelmt, &skv, NULL);
	if (rc != 0) {
		snprintf(log_buffer,  sizeof(log_buffer), "bad parse of %s", chunk_dup);
		log_err(-1, __func__, log_buffer);
		free(chunk_dup);
		return (NULL);
	}
	ret_buf[0] = '\0';
	for (l = 0; l < snelma; ++l) {
		if (!in_string_list(skv[l].kv_keyw, ',', res_list)) {
			if (ret_buf[0] != '\0') {
				if (pbs_strcat(&ret_buf, &ret_buf_size, ":") == NULL)
					return NULL;
			}

			if (pbs_strcat(&ret_buf, &ret_buf_size, skv[l].kv_keyw) == NULL)
				return NULL;
			if (pbs_strcat(&ret_buf, &ret_buf_size, "=") == NULL)
				return NULL;
			if (pbs_strcat(&ret_buf, &ret_buf_size, skv[l].kv_val) == NULL)
				return NULL;

		}
	}
	free(chunk_dup);
	return (ret_buf);
}

/**
 *
 * @brief
 *	Return a comma-separated list of resource names
 *	used/assigned in the given 'exec_vnode' string.
 *
 * @param[in]	exec_vnode - the master exec_vnode to search on.
 * @return char *
 * @retval != NULL	the resources from 'exec_vnode'.
 * @retval == NULL	if error encountered.
 *
 * @note
 *	The returned string can have duplicate resource
 *	names in them.
 *	The returned string points to a malloced area that
 *	must be freed when not needed.
 *
 */
static char *
resources_seen(char *exec_vnode)
{
	char		*selbuf = NULL;
	int		hasprn;
	char		*last = NULL;
	int		snelma;
	static key_value_pair *skv = NULL; /* must be static */
	int		j;
	char		*psubspec;
	char		*res_list = NULL;
	char		*noden = NULL;
	size_t		ssize = 0;
	size_t		slen = 0;

	if (exec_vnode == NULL) {
		log_err(-1, __func__, "bad params passed");
		return (NULL);
	}

	selbuf = strdup(exec_vnode);
	if (selbuf == NULL) {
		log_err(errno, __func__, "strdup failed on exec_vnode");
		return (NULL);
	}
	ssize = strlen(exec_vnode) + 1;
	res_list = (char *) calloc(1, strlen(exec_vnode) + 1);
	if (res_list == NULL) {
		log_err(errno, __func__, "calloc failed on exec_vnode");
		free(selbuf);
		return (NULL);
	}

	for (psubspec = parse_plus_spec_r(selbuf, &last, &hasprn); psubspec != NULL;
		psubspec = parse_plus_spec_r(last, &last, &hasprn)) {

		if (parse_node_resc(psubspec, &noden, &snelma, &skv) != 0) {
			free(selbuf);
			free(res_list);
			return (NULL);
		}

		for (j = 0; j < snelma; ++j) {
			if (res_list[0] == '\0') {
				strncpy(res_list, skv[j].kv_keyw, ssize - 1);
			} else {
				slen = strlen(res_list);
				strncat(res_list, ",", ssize - slen - 1);
				slen += 1;
				strncat(res_list, skv[j].kv_keyw, ssize - slen - 1);
			}
		}

	}
	free(selbuf);
	return (res_list);
}

/**
 * @brief
 *	Look into a job's exec_host2 or exec_host attribute
 *	for the first entry which is considered the MS host and its
 *	port. 'exec_host2' is consulted first if it is non-NULL, then 'exec_host'.
 * @param[in]	exec_host - exechost to consult
 * @param[in]	exec_host2 - exechost to consult
 * @param[out]  port	- where the corresponding port is returned.
 *
 * @return char *
 * @retval	!= NULL - mother superior full hostname
 * @retval	NULL - if error obtaining hostname.
 *
 * @note
 *	Returned string is in a malloc-ed area which must be freed
 *	outside after use.
 */
static char *
find_ms_full_host_and_port(char *exec_host, char *exec_host2, int *port)
{
	char	*ms_exec_host = NULL;
	char	*p;

	if (((exec_host == NULL) && (exec_host2 == NULL)) || (port == NULL)) {
		log_err(PBSE_INTERNAL, __func__, "bad input parameter");
		return (NULL);
	}

	*port = pbs_conf.mom_service_port;

	if (exec_host2 != NULL) {
		ms_exec_host = strdup(exec_host2);
		if (ms_exec_host == NULL) {
			log_err(errno, __func__, "strdup failed");
			return (NULL);

		}
		if ((p = strchr(ms_exec_host, '/')) != NULL)
			*p = '\0';

		if ((p = strchr(ms_exec_host, ':')) != NULL) {
			char *endp;
			long pnum;

			pnum = (int)strtol(p + 1, &endp, 10);
			if ((*endp != '\0') || (pnum == LONG_MIN) || (pnum == LONG_MAX)) {
				log_err(errno, __func__, "strtoul error");
				return (NULL);
			}
			*p = '\0';
			*port = pnum;
		}
	} else if (exec_host != NULL) {
		ms_exec_host = strdup(exec_host);
		if (ms_exec_host == NULL) {
			log_err(errno, __func__, "strdup failed");
			return (NULL);

		}
		if ((p = strchr(ms_exec_host, '/')) != NULL)
			*p = '\0';
	}
	return (ms_exec_host);
}

/**
 * @brief
 *	Given a select string specification of the form:
 *		<num>:<resA>=<valA>:<resB>=<valB>+<resN>=<valN>
 *	expand the spec to write out the repeated chunks
 *	completely. For example, given:
 *		2:ncpus=1:mem=3gb:mpiprocs=5
 *	this expands to:
 *	   ncpus=1:mem=3gb:mpiprocs=5+ncpus=1:mem=3gb:mpiprocs=5
 * @param[in]	select_str - the select/schedselect specification
 *
 * @return char *
 * @retval	!= NULL - the expanded select string
 * @retval	NULL - if unexpected encountered during processing.
 *
 * @note
 *	Returned string is in a malloc-ed area which must be freed
 *	outside after use.
 */
static char *
expand_select_spec(char *select_str)
{
	char		*selbuf = NULL;
	int		hasprn3;
	char		*last3 = NULL;
	int		snc;
	int		snelma;
	static int	snelmt = 0; /* must be static per parse_chunk_r() */
	static key_value_pair *skv = NULL; /* must be static per parse_chunk_r() */
	int		i, j;
	char		*psubspec;
	char		buf[LOG_BUF_SIZE + 1];
	int		ns_malloced = 0;
	char		*new_sel = NULL;

        if (select_str == NULL) {
                log_err(-1, __func__, "bad param passed");
		return (NULL);
        }

	selbuf = strdup(select_str);
        if (selbuf == NULL) {
                log_err(errno, __func__, "strdup fail");
		return (NULL);
        }

	/* parse chunk from select spec */
	for (psubspec = parse_plus_spec_r(selbuf, &last3, &hasprn3); psubspec != NULL;
		psubspec = parse_plus_spec_r(last3, &last3, &hasprn3)) {
		int rc = 0;
		rc = parse_chunk_r(psubspec, &snc, &snelma, &snelmt, &skv, NULL);
		/* snc = number of chunks */
		if (rc != 0) {
			free(selbuf);
			free(new_sel);
			return (NULL);
		}

		for (i = 0; i < snc; ++i) {	   /* for each chunk in select.. */

			for (j = 0; j < snelma; ++j) {
				if (j == 0) {
					snprintf(buf, sizeof(buf), "1:%s=%s",
							skv[j].kv_keyw, skv[j].kv_val);
				} else {
					snprintf(buf, sizeof(buf), ":%s=%s",
							skv[j].kv_keyw, skv[j].kv_val);
				}
				if ((new_sel != NULL) && (new_sel[0] != '\0') && (j == 0)) {
					if (pbs_strcat(&new_sel, &ns_malloced, "+") == NULL) {
						if (ns_malloced > 0)
							free(new_sel);
						log_err(errno, __func__, "pbs_strcat failed");
						free(selbuf);
						return (NULL);
					}

				}
				if (pbs_strcat(&new_sel, &ns_malloced, buf) == NULL) {
					if (ns_malloced > 0)
						free(new_sel);
					log_err(errno, __func__, "pbs_strcat failed");
					free(selbuf);
					return (NULL);
				}
			}
		}

	}
	free(selbuf);
	return (new_sel);

}

enum resc_sum_action {
	RESC_SUM_ADD,
	RESC_SUM_GET_CLEAR
};

/**
 * @brief
 *	manage_resc_sum_values: perform some 'action' on the internal resc_sum_values
 *	array, whether adding a new entry, getting an entry, or clearing/initializing
 *	an entry.
 *
 * @param[in]	action	- can either be 'RESC_SUM_ADD' to add an entry (resc_def,
 *			  keyw, value) into the internal resc_sum_values array,
 *			  or 'RESC_SUM_GET_CLEAR' to return the contents of the
 *			  resc_sum_values array.
 * @param[in]	resc_def- resource definition of the resource to be added to the array.
 *			- must be non-NULL if 'action' is 'RESC_SUM_ADD'.
 * @param[in]	keyw	- resource name of the resource to be added to the array.
 *			- must be non-NULL if 'action' is 'RESC_SUM_ADD'.
 * @param[in]	value	- value of the resource to be added to the array.
 *			  must be non-NULL if 'action' is 'RESC_SUM_ADD'.
 * @param[out]	err_msg	- error message buffer filled in if there's an error executing
 *			  this function.
 * @param[in]	err_msg_sz - size of 'err_msg' buffer.
 *
 * @return 	char *
 * @retval	<string> If 'action' is RESC_SUM_ADD, then this returns the 'keyw' to
 *			 signal success adding the <resc_def, keyw, value>.
 *			 If 'action' is RESC_SUM_GET_CLEAR, then this returns the
 *			 <res>=<value> entries in the internal resc_sum_values
 *			 array, as well as clear/initialize entries in the resc_sum_values
 *			 array.The returned string is of the form:
 *				":<res>=<value>:<res1>=(value1>:<res2>=<value2>..."
 * @retval	NULL	 If an error has occurred, filling in the 'err_msg' with the error
 *			 message.
 * @par	MT-safe: No.
 */
static char *
manage_resc_sum_values(enum resc_sum_action action, resource_def *resc_def, char *keyw, char *value,
	char *err_msg, int err_msg_sz)
{
	static	struct resc_sum	*resc_sum_values = NULL;
	static	int	resc_sum_values_size = 0;
	struct	resc_sum *rs;
	int		k;

	if ((action == RESC_SUM_ADD) && ((resc_def == NULL) || (keyw == NULL) || (value == NULL))) {
        	log_err(-1, __func__, "RESC_SUM_ADD: resc_def, keyw, or value is NULL");
		return (NULL);
	}

	if (resc_sum_values_size == 0) {
		resc_sum_values = (struct resc_sum *)calloc(20,
						sizeof(struct resc_sum));
		if (resc_sum_values == NULL) {
        		log_err(-1, __func__, "resc_sum_values calloc error");
			return (NULL);
		}
		resc_sum_values_size = 20;
	}

	if (action == RESC_SUM_ADD) {
		int	r;
		struct	resc_sum *tmp_rs;
		int	found_match = 0;
		struct	attribute tmpatr;

		found_match = 0;
		for (k = 0; k < resc_sum_values_size; k++) {
			rs = resc_sum_values;
			if (rs[k].rs_def == NULL)
				break;

			if (strcmp(rs[k].rs_def->rs_name, keyw) == 0) {
				r = rs[k].rs_def->rs_decode(&tmpatr, keyw, NULL, value);
				if (r == 0)
					rs[k].rs_def->rs_set(&rs[k].rs_attr, &tmpatr, INCR);
				found_match = 1;
				break;
			}
		}

		if (k == resc_sum_values_size) {
			int t;
			/* add a new entry */

			t = resc_sum_values_size + 5;
			tmp_rs = (struct resc_sum *)realloc(resc_sum_values,
				  		t * sizeof(struct resc_sum));
			if (tmp_rs == NULL) {
        			log_err(-1, __func__, "resc_sum_values realloc error");
				return (NULL);
			}
			resc_sum_values = tmp_rs;
			for (k = resc_sum_values_size; k < t; k++) {
				rs = resc_sum_values;
				rs[k].rs_def = NULL;
				memset(&rs[k].rs_attr, 0, sizeof(struct attribute));
			}
			/* k becomes the index to the new netry */
			k = resc_sum_values_size;
			resc_sum_values_size = t;
		}

		if (!found_match) {
			rs = resc_sum_values;
			rs[k].rs_def = resc_def;
			rs[k].rs_def->rs_decode(&rs[k].rs_attr, keyw, NULL,
								value);
		}
		return (keyw);

	} else if (action == RESC_SUM_GET_CLEAR) {
		svrattrl *val = NULL;
		static	char	*buf = NULL;
		static	int	buf_size = 0;

		if (buf_size == 0) {
			buf = (char *)malloc(LOG_BUF_SIZE);

			if (buf == NULL) {
        			log_err(-1, __func__, "local buf malloc error");
				return (NULL);
			}
			buf_size = LOG_BUF_SIZE;
		}
		buf[0] = '\0';

		for (k = 0; k < resc_sum_values_size; k++) {
			int rc;

			rs = resc_sum_values;
			if (rs[k].rs_def == NULL)
				break;

			rc = rs[k].rs_def->rs_encode(&rs[k].rs_attr,
				NULL, ATTR_l, rs[k].rs_def->rs_name,
				ATR_ENCODE_CLIENT, &val);
			if (rc > 0) {
				if (pbs_strcat(&buf, &buf_size, ":") == NULL)
					return (NULL);
				if (pbs_strcat(&buf, &buf_size, val->al_resc) == NULL)
					return (NULL);
				if (pbs_strcat(&buf, &buf_size, "=") == NULL)
					return (NULL);
				if (pbs_strcat(&buf, &buf_size, val->al_value) == NULL)
					return (NULL);
			}
			free(val);

			rs[k].rs_def->rs_free(&rs[k].rs_attr);
			rs[k].rs_def = NULL;
			memset(&rs[k].rs_attr, 0, sizeof(struct attribute));
		}
		return (buf);
	}
	return (NULL);
}

/*
 * @brief
 *	Initialize the relnodes_input_vnodelist_t structure used as argument to
 *	pbs_release_nodes_given_nodelist() function.
 *
 * @param[out]	r_input	- structure to initialize
 * @return none
 */
void
relnodes_input_vnodelist_init(relnodes_input_vnodelist_t *r_input)
{
	r_input->vnodelist = NULL;
	r_input->deallocated_nodes_orig = NULL;
	r_input->p_new_deallocated_execvnode = NULL;
}

/*
 * @brief
 *	Release node resources from a job whose node/vnode are appearing in
 *	specified nodelist.
 *
 * @param[in]		r_input	- contains various input including the job id
 * @param[in,out]	r_input2 - contains various input and output parameters
 *				   including the list of nodes/vnodes to release
 *				   resources from, as well
 *				   the resulting new values to job's exec_vnode,
 *				   exec_host, exec_host2, and schedselect.
 * @param[out]		err_msg - gets filled in with the error message if this
 *				  function returns a non-zero value.
 * @param[in]		err_sz - size of the 'err_msg' buffer.
 * @return int
 * @retval 0 - success
 * @retval 1 - fail with 'err_msg' filled in with message.
 */
int
pbs_release_nodes_given_nodelist(relnodes_input_t *r_input, relnodes_input_vnodelist_t *r_input2, char *err_msg, int err_msg_sz)
{
	char	*new_exec_vnode = NULL;
	char	*new_exec_host = NULL;
	char	*new_exec_host2 = NULL;
	char	*new_select = NULL;
	char	*chunk_buf = NULL;
	int	chunk_buf_sz = 0;
	char	*chunk = NULL;
	char	*chunk1 = NULL;
	char	*chunk2 = NULL;
	char	*chunk3 = NULL;
	char	*last = NULL;
	char	*last1 = NULL;
	char	*last2 = NULL;
	char	*last3 = NULL;
        int	hasprn = 0;
	int	hasprn1 = 0;
	int	hasprn2 = 0;
	int	hasprn3 = 0;
	int	entry = 0;
	int	f_entry = 0;
	int	h_entry = 0;
	int	sel_entry = 0;
	int	j;
	int	nelem;
	char	*noden;
	struct	key_value_pair *pkvp;
	char	buf[LOG_BUF_SIZE] = {0};
	struct	pbsnode *pnode = NULL;
	int		rc = 1;
	int		ns_malloced = 0;
	char		*buf_sum = NULL;
	int		paren = 0;
	int		found_paren = 0;
	int		found_paren_dealloc = 0;
	resource_def	*resc_def = NULL;
	char		*deallocated_execvnode = NULL;
	int		deallocated_execvnode_sz = 0;
	char		*extra_res = NULL;
	resource	*prs;
	resource_def	*prdefvntype;
	char		*parent_mom;
	char		prev_noden[PBS_MAXNODENAME + 1];
	char		*res_in_exec_vnode = NULL;
	char		*ms_fullhost = NULL;
	int		ms_port = 0;
	char		*exec_vnode = NULL;
	char		*exec_host = NULL;
	char		*exec_host2 = NULL;
	char		*sched_select = NULL;
#ifdef PBS_MOM
	momvmap_t 	*vn_vmap = NULL;
#endif

	if ((r_input == NULL) || (r_input->jobid == NULL) || (r_input->execvnode == NULL) || (r_input->exechost == NULL) || (r_input->exechost2 == NULL) || (r_input->schedselect == NULL) || (err_msg == NULL) || (err_msg_sz <= 0)) {

		log_err(errno, __func__, "required parameter is null");
		return (1);
	}

	err_msg[0] = '\0';

	exec_vnode = strdup(r_input->execvnode);
	if (exec_vnode == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodeslist_exit;
	}

	exec_host = strdup(r_input->exechost);
	if (exec_host == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodeslist_exit;
	}

	exec_host2 = strdup(r_input->exechost2);
	if (exec_host2 == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodeslist_exit;
	}

	sched_select = expand_select_spec(r_input->schedselect);
	if (sched_select == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodeslist_exit;
	}

	ms_fullhost = find_ms_full_host_and_port(exec_host, exec_host2, &ms_port);
	if (ms_fullhost == NULL) {
	 	log_err(-1, __func__, "can't determine primary execution host and port");
		goto release_nodeslist_exit;
	}

	res_in_exec_vnode = resources_seen(exec_vnode);

	new_exec_vnode = (char *)calloc(1, strlen(exec_vnode) + 1);
	if (new_exec_vnode == NULL) {
	 	log_err(-1, __func__, "new_exec_vnode calloc error");
		goto release_nodeslist_exit;
	}
	new_exec_vnode[0] = '\0';

	chunk_buf_sz = strlen(exec_vnode) + 1;
	chunk_buf = (char *) calloc(1, chunk_buf_sz);
	if (chunk_buf == NULL) {
	 	log_err(-1, __func__, "chunk_buf calloc error");
		goto release_nodeslist_exit;
	}

	deallocated_execvnode_sz = strlen(exec_vnode) + 1;
	deallocated_execvnode = (char *) calloc(1, deallocated_execvnode_sz);
	if (deallocated_execvnode == NULL) {
	 	log_err(-1, __func__, "deallocated_execvnode calloc error");
		goto release_nodeslist_exit;
	}

	if (exec_host != NULL) {
		new_exec_host = (char *) calloc(1, strlen(exec_host) + 1);
		if (new_exec_host == NULL) {
	 		log_err(-1, __func__, "new_exec_host calloc error");
			goto release_nodeslist_exit;
		}
		new_exec_host[0] = '\0';
	}

	if (exec_host2 != NULL) {
		new_exec_host2 = (char *) calloc(1, strlen(exec_host2) + 1);
		if (new_exec_host2 == NULL) {
	 		log_err(-1, __func__, "new_exec_host2 calloc error");
			goto release_nodeslist_exit;
		}
		new_exec_host2[0] = '\0';
	}

	prdefvntype = &svr_resc_def[RESC_VNTYPE];
	/* There's a 1:1:1 mapping among exec_vnode parenthesized
	 * entries, exec_host, and exec_host2.
	 */
	entry = 0;	/* exec_vnode entries */
	h_entry = 0;	/* exec_host* entries */
	sel_entry = 0;	/* select and schedselect entries */
	f_entry = 0;	/* number of freed sister nodes */
	paren = 0;
	prev_noden[0] = '\0';
	parent_mom = NULL;
	for (	chunk = parse_plus_spec_r(exec_vnode, &last, &hasprn),
	     	chunk1 = parse_plus_spec_r(exec_host, &last1, &hasprn1),
	     	chunk2 = parse_plus_spec_r(exec_host2,&last2, &hasprn2),
	     	chunk3 = parse_plus_spec_r(sched_select, &last3, &hasprn3);
		(chunk != NULL) && (chunk1 != NULL) && (chunk2 != NULL) && (chunk3 != NULL);
		chunk = parse_plus_spec_r(last, &last, &hasprn) ) {

		paren += hasprn;
		strncpy(chunk_buf, chunk, chunk_buf_sz - 1);
		if (parse_node_resc(chunk, &noden, &nelem, &pkvp) == 0) {

#ifdef PBS_MOM
			/* see if previous entry already matches this */
			if ((strcmp(prev_noden, noden) != 0)) {
				vn_vmap = find_vmap_entry(noden);
				if (vn_vmap == NULL) { /* should not happen */

					snprintf(log_buffer, sizeof(log_buffer), "no vmap entry for %s", noden);
					log_err(errno, __func__, log_buffer);
					goto release_nodeslist_exit;
				}
				if (vn_vmap->mvm_hostn != NULL)
					parent_mom = vn_vmap->mvm_hostn;
				else
					parent_mom = vn_vmap->mvm_name;
			}

			if (parent_mom == NULL) { /* should not happen */

				snprintf(log_buffer, sizeof(log_buffer), "no parent_mom for %s", noden);
				log_err(errno, __func__, log_buffer);
				goto release_nodeslist_exit;
			}

			strncpy(prev_noden, noden, PBS_MAXNODENAME);
#else
			if (r_input->vnodes_data != NULL) {
				/* see if previous entry already matches this */
				if ((strcmp(prev_noden, noden) != 0)) {
					char key_buf[BUF_SIZE];
					svrattrl *svrattrl_e;

					snprintf(key_buf, BUF_SIZE, "%s.resources_assigned", noden);
					if ((svrattrl_e = find_svrattrl_list_entry(r_input->vnodes_data, key_buf, "host,string")) != NULL) {
						parent_mom = svrattrl_e->al_value;
					}
				}

				if (parent_mom == NULL) { /* should not happen */

					snprintf(log_buffer, sizeof(log_buffer), "no parent_mom for %s", noden);
					log_err(errno, __func__, log_buffer);
					goto release_nodeslist_exit;
				}

				strncpy(prev_noden, noden, PBS_MAXNODENAME);
			} else {
				/* see if previous entry already matches this */

				if ((pnode == NULL) ||
					(strcmp(pnode->nd_name, noden) != 0)) {
					pnode = find_nodebyname(noden);
				}

				if (pnode == NULL) { /* should not happen */
					if ((err_msg != NULL) && (err_msg_sz > 0)) {
        					snprintf(err_msg, err_msg_sz, "no node entry for %s", noden);
        					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
					}
					goto release_nodeslist_exit;
				}
			}
#endif

			if (is_parent_host_of_node(pnode, parent_mom, ms_fullhost, ms_port) &&
			     (r_input2->vnodelist != NULL) &&
			      in_string_list(noden, '+', r_input2->vnodelist)) {
				if ((err_msg != NULL) && (err_msg_sz > 0)) {
        				snprintf(err_msg, err_msg_sz,
				 		"Can't free '%s' since it's on a primary execution host", noden);
        				log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
				}
				goto release_nodeslist_exit;
			}

			if ((r_input2->vnodelist != NULL) &&
			      in_string_list(noden, '+', r_input2->vnodelist) && (pnode != NULL) &&
				(is_nattr_set(pnode, ND_ATR_ResourceAvail) != 0)) {
				for (prs = (resource *)GET_NEXT(get_nattr_list(pnode, ND_ATR_ResourceAvail)); prs != NULL; prs = (resource *)GET_NEXT(prs->rs_link)) {
					if ((prdefvntype != NULL) &&
						(prs->rs_defin == prdefvntype) &&
						(is_attr_set(&prs->rs_value)) != 0) {
						struct array_strings *as;
						int	l;
						as = prs->rs_value.at_val.at_arst;
						for (l = 0; l < as->as_usedptr; l++) {
							if (strncmp(as->as_string[l], "cray_", 5) == 0)  {
								if ((err_msg != NULL) && (err_msg_sz > 0)) {
        								snprintf(err_msg, err_msg_sz, "not currently supported on Cray X* series nodes: %s", noden);
        								log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
								}
								goto release_nodeslist_exit;
							}
						}
					}
				}
			}

			if (is_parent_host_of_node(pnode, parent_mom, ms_fullhost, ms_port) ||
			     ((r_input2->vnodelist != NULL) && !in_string_list(noden, '+', r_input2->vnodelist))) {

				if (entry > 0) /* there's something put in previously */
					strcat(new_exec_vnode, "+");

				if (((hasprn > 0) && (paren > 0)) ||
				     ((hasprn == 0) && (paren == 0))) {
						 /* at the beginning of chunk for current host */
					if (!found_paren) {
						strcat(new_exec_vnode, "(");
						found_paren = 1;

						if (h_entry > 0) {
							/* there's already previous exec_host entry */
							if (new_exec_host != NULL)
								strcat(new_exec_host, "+");
							if (new_exec_host2 != NULL)
								strcat(new_exec_host2, "+");
						}

						if (new_exec_host != NULL)
							strcat(new_exec_host, chunk1);
						if (new_exec_host2 != NULL)
							strcat(new_exec_host2, chunk2);
						h_entry++;
					}
				}

				if (!found_paren) {
					strcat(new_exec_vnode, "(");
					found_paren = 1;

					if (h_entry > 0) {
						/* there's already previous exec_host entry */
						if (new_exec_host != NULL)
							strcat(new_exec_host, "+");
						if (new_exec_host2 != NULL)
							strcat(new_exec_host2, "+");
					}

					if (new_exec_host != NULL)
						strcat(new_exec_host, chunk1);
					if (new_exec_host2 != NULL)
						strcat(new_exec_host2, chunk2);
					h_entry++;
				}
				strcat(new_exec_vnode, noden);
				entry++;

				for (j = 0; j < nelem; ++j) {

					resc_def = find_resc_def(svr_resc_def, pkvp[j].kv_keyw);
					if (resc_def == NULL) {
						continue;
					}

					if (manage_resc_sum_values(RESC_SUM_ADD, resc_def,
							pkvp[j].kv_keyw, pkvp[j].kv_val, err_msg, err_msg_sz) == NULL) {
						log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
											__func__, err_msg);
						goto release_nodeslist_exit;

					}

					snprintf(buf, sizeof(buf),
						":%s=%s", pkvp[j].kv_keyw, pkvp[j].kv_val);
					strcat(new_exec_vnode, buf);
				}

				if (paren == 0) { /* have all chunks for current host */

					if (found_paren) {
						strcat(new_exec_vnode, ")");
						found_paren = 0;
					}

					if (found_paren_dealloc) {
						strcat(deallocated_execvnode, ")");
						found_paren_dealloc = 0;
					}


					buf_sum = manage_resc_sum_values(RESC_SUM_GET_CLEAR,
							NULL, NULL, NULL, err_msg, err_msg_sz);

					if (buf_sum == NULL) {
						log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
							__func__, err_msg);
						goto release_nodeslist_exit;
					}

					if (buf_sum[0] != '\0') {
						extra_res = return_missing_resources(chunk3,
								res_in_exec_vnode);

						if (sel_entry > 0) {
						/* there's already previous select/schedselect entry */
							if (pbs_strcat(
								&new_select,
								&ns_malloced,
								"+") == NULL) {
								log_err(-1, __func__, "pbs_strcat failed");
								goto release_nodeslist_exit;
							}
						}
						if (pbs_strcat(&new_select, &ns_malloced, "1") == NULL) {
							log_err(-1, __func__, "pbs_strcat failed");
							goto release_nodeslist_exit;
						}
						if (pbs_strcat(&new_select, &ns_malloced, buf_sum) == NULL) {
							log_err(-1, __func__, "pbs_strcat failed");
							goto release_nodeslist_exit;
						}
						if ((extra_res != NULL) && (extra_res[0] != '\0')) {
							if (pbs_strcat(&new_select, &ns_malloced, ":") == NULL) {
								log_err(-1, __func__, "pbs_strcat failed");
								goto release_nodeslist_exit;
							}
							if (pbs_strcat(&new_select, &ns_malloced, extra_res) == NULL) {
								log_err(-1, __func__, "pbs_strcat failed");
								goto release_nodeslist_exit;
							}
						}
						sel_entry++;
					}
				}
			} else {
				if (!is_parent_host_of_node(pnode, parent_mom, ms_fullhost, ms_port)) {
					if (f_entry > 0) { /* there's something put in previously */
						strcat(deallocated_execvnode, "+");
					}

					if (((hasprn > 0) && (paren > 0)) || ((hasprn == 0) && (paren == 0)) ) {
						 /* at the beginning of chunk for current host */
						if (!found_paren_dealloc) {
							strcat(deallocated_execvnode, "(");
							found_paren_dealloc = 1;
						}
					}

					if (!found_paren_dealloc) {
						strcat(deallocated_execvnode, "(");
						found_paren_dealloc = 1;
					}
					strcat(deallocated_execvnode, chunk_buf);
					f_entry++;

					if (paren == 0) { /* have all chunks for current host */

						if (found_paren) {
							strcat(new_exec_vnode, ")");
							found_paren = 0;
						}

						if (found_paren_dealloc) {
							strcat(deallocated_execvnode, ")");
							found_paren_dealloc = 0;
						}
					}

				}

				if (hasprn < 0) {
					/* matched ')' in chunk, so need to balance the parenthesis */
					if (found_paren) {
						strcat(new_exec_vnode, ")");
						found_paren = 0;
					}
					if (found_paren_dealloc) {
						strcat(deallocated_execvnode, ")");
						found_paren_dealloc = 0;
					}

					buf_sum = manage_resc_sum_values(RESC_SUM_GET_CLEAR,
							NULL, NULL, NULL, err_msg, err_msg_sz);

					if (buf_sum == NULL) {
						log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG,
							__func__, err_msg);
						goto release_nodeslist_exit;
					}

					if (buf_sum[0] != '\0') {
						extra_res = return_missing_resources(chunk3,
								res_in_exec_vnode);

						if (sel_entry > 0) {
							/* there's already previous select/schedselect entry */
							if (pbs_strcat(&new_select, &ns_malloced, "+") == NULL) {
								log_err(-1, __func__, "pbs_strcat failed");
								goto release_nodeslist_exit;
							}
						}
						if (pbs_strcat(&new_select, &ns_malloced, "1") == NULL) {
							log_err(-1, __func__, "pbs_strcat failed");
							goto release_nodeslist_exit;
						}
						if (pbs_strcat(&new_select, &ns_malloced, buf_sum) == NULL) {
							log_err(-1, __func__, "pbs_strcat failed");
							goto release_nodeslist_exit;
						}
						if ((extra_res != NULL) && (extra_res[0] != '\0')) {
							if (pbs_strcat(&new_select, &ns_malloced, ":") == NULL) {
								log_err(-1, __func__, "pbs_strcat failed");
								goto release_nodeslist_exit;
							}
							if (pbs_strcat(&new_select, &ns_malloced, extra_res) == NULL) {
								log_err(-1, __func__, "pbs_strcat failed");
								goto release_nodeslist_exit;
							}
						}
						sel_entry++;

					}

				}
			}
		} else {
			log_err(-1, __func__, "parse_node_resc error");
			goto release_nodeslist_exit;
		}

		if (paren == 0) {
			chunk1 = parse_plus_spec_r(last1, &last1, &hasprn1),
			chunk2 = parse_plus_spec_r(last2, &last2, &hasprn2);
			chunk3 = parse_plus_spec_r(last3, &last3, &hasprn3);
		}
	}
	entry = strlen(new_exec_vnode)-1;
	if ((entry >= 0) && (new_exec_vnode[entry] == '+'))
		new_exec_vnode[entry] = '\0';

	if (strcmp(new_exec_vnode, r_input->execvnode) == 0) {
		/* no change, don't bother setting the new_* return values */
		goto release_nodeslist_exit;
	}

	if (new_exec_host != NULL) {
		entry = strlen(new_exec_host) - 1;
		if ((entry >= 0) && (new_exec_host[entry] == '+'))
			new_exec_host[entry] = '\0';
	}

	if (new_exec_host2 != NULL) {
		entry = strlen(new_exec_host2) - 1;
		if ((entry >= 0) && (new_exec_host2[entry] == '+'))
			new_exec_host2[entry] = '\0';
	}

	entry = strlen(new_select) - 1;
	if ((entry >= 0) && (new_select[entry] == '+'))
		new_select[entry] = '\0';

	entry = strlen(deallocated_execvnode) - 1;
	if ((entry >= 0) && (deallocated_execvnode[entry] == '+'))
		deallocated_execvnode[entry] = '\0';

	if (deallocated_execvnode[0] != '\0') {
		if ((r_input2->deallocated_nodes_orig != NULL) && (r_input2->deallocated_nodes_orig[0] != '\0')) {
			if (pbs_strcat(&deallocated_execvnode,
				&deallocated_execvnode_sz, "+") == NULL) {
				log_err(-1, __func__,
					"pbs_strcat deallocated_execvnode failed");
				goto release_nodeslist_exit;
			}
			if (pbs_strcat(&deallocated_execvnode, &deallocated_execvnode_sz,
				r_input2->deallocated_nodes_orig) == NULL) {
				log_err(-1, __func__,
					"pbs_strcat deallocated_execvnode failed");
				goto release_nodeslist_exit;
			}
		}
	}

	/* output message about nodes to be freed but no part of job */
	if ((r_input2->vnodelist != NULL) && (err_msg != NULL) &&
					(err_msg_sz > 0)) {
		char	*tmpbuf;
		char	*tmpbuf2;
		char	*pc = NULL;
		char	*pc1 = NULL;
		char	*save_ptr;	/* posn for strtok_r() */

		tmpbuf = strdup(r_input2->vnodelist);
		/* will contain nodes that are in 'vnodelist' but not in deallocated_execvnode */
		tmpbuf2 = strdup(r_input2->vnodelist);
		if ((tmpbuf != NULL) && (tmpbuf2 != NULL)) {

			tmpbuf2[0] = '\0';

			pc = strtok_r(tmpbuf, "+", &save_ptr);
			while (pc != NULL) {
				/* trying to match '(<vnode_name>:'
				 *  or '+<vnode_name>:'
				 */
				snprintf(chunk_buf, chunk_buf_sz, "(%s:", pc);
				pc1 = strstr(deallocated_execvnode, chunk_buf);
				if (pc1 == NULL) {
					snprintf(chunk_buf, chunk_buf_sz, "+%s:", pc);
					pc1 = strstr(deallocated_execvnode, chunk_buf);
				}
				if (pc1 == NULL) {
					if (tmpbuf2[0] != '\0')
						strcat(tmpbuf2, " ");
					strcat(tmpbuf2, pc);
				}
				pc = strtok_r(NULL, "+", &save_ptr);
			}

			if (tmpbuf2[0] != '\0') {
				snprintf(err_msg, err_msg_sz,
					"node(s) requested to be released not part of the job: %s", tmpbuf2);
				free(tmpbuf);
				free(tmpbuf2);
				goto release_nodeslist_exit;
			}
		}
		free(tmpbuf);
		free(tmpbuf2);
	}

	if (new_exec_vnode[0] != '\0') {

		if (strcmp(r_input->execvnode, new_exec_vnode) == 0) {
			/* no change */
			if ((err_msg != NULL) && (err_msg_sz > 0)) {
				snprintf(err_msg, err_msg_sz, "node(s) requested to be released not part of the job: %s", r_input2->vnodelist?r_input2->vnodelist:"");
        			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
			}
			goto release_nodeslist_exit;
		}
		if (r_input->p_new_exec_vnode != NULL)
			*(r_input->p_new_exec_vnode) = new_exec_vnode;
	}

	if (deallocated_execvnode[0] != '\0') {
		if (r_input2->p_new_deallocated_execvnode != NULL)
			*(r_input2->p_new_deallocated_execvnode) = deallocated_execvnode;
	}

	if ((new_exec_host != NULL) && (new_exec_host[0] != '\0')) {

		if (r_input->p_new_exec_host[0] != NULL)
			*(r_input->p_new_exec_host[0]) = new_exec_host;
	}

	if ((new_exec_host2 != NULL) && (new_exec_host2[0] != '\0')) {

		if (r_input->p_new_exec_host[1] != NULL)
			*(r_input->p_new_exec_host[1]) = new_exec_host2;
	}

	if (new_select[0] != '\0') {
		if (r_input->p_new_schedselect != NULL)
			*(r_input->p_new_schedselect) = new_select;

	}
	rc = 0;

release_nodeslist_exit:
	free(ms_fullhost);
	free(res_in_exec_vnode);
	free(chunk_buf);
	free(exec_vnode);
	free(exec_host);
	free(exec_host2);
	free(sched_select);
	if ((rc != 0) || (strcmp(new_exec_vnode, r_input->execvnode) == 0)) {
		free(new_exec_vnode);
		free(new_exec_host);
		free(new_exec_host2);
		free(new_select);
		free(deallocated_execvnode);
	}
	/* clear the summation buffer */
	(void)manage_resc_sum_values(RESC_SUM_GET_CLEAR, NULL, NULL, NULL, buf, sizeof(buf));

	return (rc);
}

/**
 *
 * @brief
 *	 Print/log all the entries in the list of nodes for a job.
 *
 * @param[in]	header_str	- header string for logging
 * @param[in]	node_list	- the PBS node list
 *
 * @return none
 */
void
reliable_job_node_print(char *header_str, pbs_list_head *node_list, int logtype)
{
	reliable_job_node	*rjn;

	if ((header_str == NULL) || (node_list == NULL))
		return;

	for (rjn = (reliable_job_node *)GET_NEXT(*node_list); rjn != NULL;
		rjn = (reliable_job_node *)GET_NEXT(rjn->rjn_link)) {
		snprintf(log_buffer, sizeof(log_buffer), "%s: node %s", header_str, rjn->rjn_host);
		log_event(logtype, PBS_EVENTCLASS_NODE,
			  LOG_INFO, __func__, log_buffer);
	}
}

/**
 *
 * @brief
 *	 Free up all the entries in the list of nodes for a job.
 *
 * @param[in]	node_list	- the PBS node list
 *
 * @return none
 */
void
reliable_job_node_free(pbs_list_head *node_list)
{
	reliable_job_node	*rjn;

	if (node_list == NULL)
		return;

	for (rjn = (reliable_job_node *)GET_NEXT(*node_list); rjn != NULL; rjn = (reliable_job_node *)GET_NEXT(*node_list)) {
		delete_link(&rjn->rjn_link);
		free(rjn);
	}
}

/**
 *
 * @brief
 *	 Find an entry from the list of nodes for a job.
 *
 * @param[in]	node_list	- the PBS node list
 * @param[in]	nname		- node hostname to search for.
 *
 * @return reliable_job_node *
 *
 * @retval <reliable_nob_node entry>	- if one found.
 * @retval NULL  			- if no entry found.
 *
 */
reliable_job_node *
reliable_job_node_find(pbs_list_head *node_list, char *nname)
{
	reliable_job_node *rjn = NULL;

	if ((node_list == NULL) || (nname == NULL))
		return (NULL);

	for (rjn = (reliable_job_node *)GET_NEXT(*node_list); rjn != NULL; rjn = (reliable_job_node *)GET_NEXT(rjn->rjn_link)) {
		if (strcmp(rjn->rjn_host, nname) == 0) {
			return (rjn);
		}
	}
	return (NULL);
}

/**
 *
 * @brief
 * 	Add a unique entry to the list of mom nodes for a job.
 *
 * @param[in]	node_list	- the PBS node list
 * @param[in]	nname		- node hostname
 *
 * @return int
 * @retval 0	- success
 * @retval -1	- error encountered
 *
 * @return none
 */
int
reliable_job_node_add(pbs_list_head *node_list, char *nname)
{
	reliable_job_node *rjn = NULL;

	if ((node_list == NULL) || (nname == NULL) || (nname[0] == '\0')) {
		log_err(-1, __func__, "unexpected input");
		return (-1);
	}

	if (reliable_job_node_find(node_list, nname) != NULL) {
		return (0);
	}

	rjn = (reliable_job_node *)malloc(sizeof(reliable_job_node));
	if (rjn == NULL) {
		log_err(errno, __func__, msg_err_malloc);
		return (-1);
	}
	CLEAR_LINK(rjn->rjn_link);

	snprintf(rjn->rjn_host, sizeof(rjn->rjn_host), "%s", nname);

	rjn->prologue_hook_success = 0;

	append_link(node_list, &rjn->rjn_link, rjn);

	return (0);
}

/**
 *
 * @brief
 * 	Delete an entry from the list nodes for a job.
 *
 * @param[in]	node_list	- the PBS node list
 * @param[in]	nname		- node hostname to delete
 *
 * @return none
 */
void
reliable_job_node_delete(pbs_list_head *node_list, char *nname)
{
	reliable_job_node	*rjn;

	if ((node_list == NULL) || (nname == NULL)) {
		return;
	}

	for (rjn = (reliable_job_node *)GET_NEXT(*node_list); rjn != NULL; rjn = (reliable_job_node *)GET_NEXT(rjn->rjn_link)) {
		if (strcmp(rjn->rjn_host, nname) == 0) {
			delete_link(&rjn->rjn_link);
			free(rjn);
			return;
		}
	}

}

/**
 *
 * @brief
 *	Find an entry from the list of nodes for a job
 *	named 'nname', and mark this node host as having
 *	successfully executed execjob_prologue hook,
 *	resulting in a hook event accept.
 *	If no existing node host was matched, then add one.
 *
 * @param[in]	node_list	- the PBS node list
 * @param[in]	nname		- node hostname to search for.
 *
 * @return reliable_job_node *
 *
 * @retval <reliable_nob_node entry>	- the updated/added node entry
 * @retval NULL  			- if an error occurred.
 *
 */
reliable_job_node *
reliable_job_node_set_prologue_hook_success(pbs_list_head *node_list, char *nname)
{
	reliable_job_node *rjn = NULL;

	if ((node_list == NULL) || (nname == NULL))
		return (NULL);

	for (rjn = (reliable_job_node *)GET_NEXT(*node_list); rjn != NULL; rjn = (reliable_job_node *)GET_NEXT(rjn->rjn_link)) {
		if (strcmp(rjn->rjn_host, nname) == 0) {
			rjn->prologue_hook_success = 1;
			return (rjn);
		}
	}
	/* no entry matched so add one */
	rjn = (reliable_job_node *)malloc(sizeof(reliable_job_node));
	if (rjn == NULL) {
		log_err(errno, __func__, msg_err_malloc);
		return (NULL);
	}
	CLEAR_LINK(rjn->rjn_link);

	snprintf(rjn->rjn_host, sizeof(rjn->rjn_host), "%s", nname);

	rjn->prologue_hook_success = 1;

	append_link(node_list, &rjn->rjn_link, rjn);

	return (rjn);
}

/* Functions and structure in support of releasing node resources to satisfy
 * a new select spec.
 */

typedef struct resc_limit_entry {
	pbs_list_link	rl_link;
	resc_limit_t	*resc;
} rl_entry;

#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
/**
 * @brief
 * compare lexicographically the names of resources in the resource list contained in
 * two resc_limit_t structures
 *
 * @param[in]	left - the left resource limit.
 * @param[in]	right - the right resource limit.
 *
 * @return int
 * @retval -1	- left < right
 * @retval 0	- left = right
 * @retval 1	- left > right
 * @retval -2	- error
 */
static int
resc_limit_list_cmp_name(resc_limit_t *left, resc_limit_t *right)
{
	resource *pres_l, *pres_r;

	if ((left == NULL) || (right == NULL))
		return -2;

	if (left->rl_ncpus && !right->rl_ncpus)
		return 1;
	if (!left->rl_ncpus && right->rl_ncpus)
		return -1;

	if (left->rl_ssi && !right->rl_ssi)
		return 1;
	if (!left->rl_ssi && right->rl_ssi)
		return -1;

	if (left->rl_mem && !right->rl_mem)
		return 1;
	if (!left->rl_mem && right->rl_mem)
		return -1;

	if (left->rl_vmem && !right->rl_vmem)
		return 1;
	if (!left->rl_vmem && right->rl_vmem)
		return -1;

	if (left->rl_naccels && !right->rl_naccels)
		return 1;
	if (!left->rl_naccels && right->rl_naccels)
		return -1;

	if (left->rl_accel_mem && !right->rl_accel_mem)
		return 1;
	if (!left->rl_accel_mem && right->rl_accel_mem)
		return -1;

	for (pres_l = (resource *)GET_NEXT(left->rl_other_res),
		pres_r = (resource *)GET_NEXT(right->rl_other_res);
		pres_l && pres_r;
		pres_l = (resource *)GET_NEXT(pres_l->rs_link),
		pres_r = (resource *)GET_NEXT(pres_r->rs_link)) {
		int cmp_res;
		if ((cmp_res = strcasecmp(pres_l->rs_defin->rs_name, pres_r->rs_defin->rs_name)))
			return cmp_res;
	}

	return 0;
}

/**
 * @brief
 * compare the values of resources in the resource list contained in
 * two resc_limit_t structures
 *
 * @param[in]	left - the left resource limit.
 * @param[in]	right - the right resource limit.
 *
 * @return int
 * @retval -1	- left < right
 * @retval 0	- left = right
 * @retval 1	- left > right
 * @retval -2	- error
 */
static int
resc_limit_list_cmp_val(resc_limit_t *left, resc_limit_t *right)
{
	resource *pres_l, *pres_r;

	if ((left == NULL) || (right == NULL))
		return -2;

	if (left->rl_ncpus > right->rl_ncpus)
		return 1;
	if (left->rl_ncpus < right->rl_ncpus)
		return -1;

	if (left->rl_ssi > right->rl_ssi)
		return 1;
	if (left->rl_ssi < right->rl_ssi)
		return -1;

	if (left->rl_mem > right->rl_mem)
		return 1;
	if (left->rl_mem < right->rl_mem)
		return -1;

	if (left->rl_vmem > right->rl_vmem)
		return 1;
	if (left->rl_vmem < right->rl_vmem)
		return -1;

	if (left->rl_naccels > right->rl_naccels)
		return 1;
	if (left->rl_naccels < right->rl_naccels)
		return -1;

	if (left->rl_accel_mem > right->rl_accel_mem)
		return 1;
	if (left->rl_accel_mem < right->rl_accel_mem)
		return -1;

	for (pres_l = (resource *)GET_NEXT(left->rl_other_res),
		pres_r = (resource *)GET_NEXT(right->rl_other_res);
		pres_l && pres_r;
		pres_l = (resource *)GET_NEXT(pres_l->rs_link),
		pres_r = (resource *)GET_NEXT(pres_r->rs_link)) {
		int cmp_res;
		if (pres_l->rs_defin->rs_type == ATR_TYPE_BOOL)
			cmp_res = pres_l->rs_value.at_val.at_long - pres_r->rs_value.at_val.at_long;
		else
			cmp_res = pres_l->rs_defin->rs_comp(&pres_l->rs_value, &pres_r->rs_value);

		if (cmp_res)
			return cmp_res;
	}

	return 0;
}
#endif
/**
 * @brief
 *	Add the resc_limit entry 'resc' into pbs list 'pbs_head' in
 *	a sorted manner, in the order of increasing cpus or mem.
 *
 * @param[in,out]	phead - the list to add to.
 * @param[in]		resc - the resource limit to add.
 *
 * @return int
 * @retval 0	- successful operation.
 * @retval 1	- unsuccessful operation.
 * 0 for successfully added; 1 otherwise.
 */
static int
add_to_resc_limit_list_sorted(pbs_list_head *phead, resc_limit_t *resc)
{
	pbs_list_link	*plink_cur;
	rl_entry	*p_entry_cur = NULL;
	rl_entry	*new_resc = NULL;
	resc_limit_t	*p_res_cur;

	if ((phead == NULL) || (resc == NULL))
		return (1);

	for (plink_cur = phead,
		p_entry_cur = (rl_entry *)GET_NEXT(*phead);
		p_entry_cur;
		p_entry_cur = (rl_entry *)GET_NEXT(*plink_cur)) {
		plink_cur = &p_entry_cur->rl_link;
		p_res_cur = p_entry_cur->resc;

		if (p_res_cur != NULL) {
#if defined(PBS_MOM) || defined(PBS_PYTHON)
			/* order according to increasing # of cpus
			 * if same # of cpus, use increasing amt of mem
			 */
			if ((p_res_cur->rl_ncpus > resc->rl_ncpus)
				|| ((p_res_cur->rl_ncpus == resc->rl_ncpus)
					&& (p_res_cur->rl_mem > resc->rl_mem))) {
				break;
			}
#else
			int cmp_res_name;

			if (p_res_cur->rl_res_count < resc->rl_res_count)
				continue;
			else if (p_res_cur->rl_res_count > resc->rl_res_count)
				break;

			cmp_res_name = resc_limit_list_cmp_name(p_res_cur, resc);

			if (cmp_res_name < 0)
				continue;
			else if (cmp_res_name > 0)
				break;
			else {
				int cmp_res_val = resc_limit_list_cmp_val(p_res_cur, resc);
				if (cmp_res_val < 0)
					continue;
				else
					break;
			}
#endif
		}
	}

	new_resc = (rl_entry *)malloc(sizeof(rl_entry));
	if (new_resc == NULL) {
		log_err(errno, __func__, msg_err_malloc);
		return (1);
	}
	CLEAR_LINK(new_resc->rl_link);

	new_resc->resc = resc;

	/* link after 'current' (or end) of resc_limit_entry in list */
	if (p_entry_cur != NULL) {
		insert_link(plink_cur, &new_resc->rl_link, new_resc, LINK_INSET_BEFORE);
	} else {
		insert_link(plink_cur, &new_resc->rl_link, new_resc, LINK_INSET_AFTER);
	}

	return (0);
}

/**
 * @brief
 *	Add the resc_limit entry 'resc' into the beginning of pbs list
 *	'pbs_head'.
 *
 * @param[in,out]	phead - the list to add to.
 * @param[in]		resc - the resource limit to add as head.
 *
 * @return int
 * @retval 0	- successful operation.
 * @retval 1	- unsuccessful operation.
 */
static int
add_to_resc_limit_list_as_head(pbs_list_head *phead, resc_limit_t *resc)
{
	pbs_list_link	*plink_cur;
	rl_entry	*new_resc = NULL;
	rl_entry	*p_entry_cur = NULL;

	if ((phead == NULL) || (resc == NULL))
		return (1);

	plink_cur = phead;
	p_entry_cur = (rl_entry *)GET_NEXT(*phead);

	if (p_entry_cur) {
		plink_cur = &p_entry_cur->rl_link;
	}

	new_resc = (rl_entry *)malloc(sizeof(rl_entry));
	if (new_resc == NULL) {
		log_err(errno, __func__, msg_err_malloc);
		return (1);
	}
	CLEAR_LINK(new_resc->rl_link);

	new_resc->resc = resc;

	/* link after 'current' (or end) of resc_limit_entry in list */
	if (p_entry_cur) {
		insert_link(plink_cur, &new_resc->rl_link, new_resc, LINK_INSET_BEFORE);
	} else {
		insert_link(plink_cur, &new_resc->rl_link, new_resc, LINK_INSET_AFTER);
	}
	return (0);
}

#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
/**
 * @brief
 *	inserts the resource in the resc_limit_t in lexically increasing order of
 *	resource name
 *
 * @param[in]	have - the resc_limit structure.
 * @param[in]	kv_keyw - resource name.
 * @param[in]	kv_val - resource value.
 * @param[in]	execv_f - flag to indicate if the resource was found in execvnode
 *
 * @return int
 * @retval 0	- successful operation.
 * @retval PBSE_Error	- Error Code.
 */
int
resc_limit_insert_other_res(resc_limit_t *have, char *kv_keyw, char *kv_val, int execv_f)
{
	resource *pres, *pnewres;
	resource_def *resc_def = NULL;
	int cmp_res = -1;
	int rc;

	if (have == NULL) {
		log_err(-1, __func__, "have is NULL");
		return PBSE_INTERNAL;
	}

	if (kv_keyw == NULL) {
		log_err(-1, __func__, "kv_keyw is NULL");
		return PBSE_INVALJOBRESC;
	}

	if (kv_val == NULL) {
		log_err(-1, __func__, "kv_val is NULL");
		return PBSE_INVALJOBRESC;
	}

	resc_def = find_resc_def(svr_resc_def, kv_keyw);
	if (resc_def == NULL) {
		log_err(-1, __func__, "resc_def is NULL");
		return PBSE_UNKRESC;
	}

	for (pres = (resource *)GET_NEXT(have->rl_other_res);
		pres != NULL;
		pres = (resource *)GET_NEXT(pres->rs_link)) {
		if ((cmp_res = strcasecmp(pres->rs_defin->rs_name, kv_keyw)) >= 0)
			break;
	}

	if (!cmp_res) {
		attribute tmp = {0};
		if ((rc = pres->rs_defin->rs_decode(&tmp, NULL, NULL, kv_val))) {
			snprintf(log_buffer, sizeof(log_buffer), "failed to decode res %s=%s, (rc=%d)", kv_keyw, kv_val, rc);
			log_err(-1, __func__, log_buffer);
			return rc;
		}
		pres->rs_defin->rs_set(&pres->rs_value, &tmp, INCR);
		free_svrcache(&pres->rs_value);
		pres->rs_defin->rs_encode(&pres->rs_value, NULL, pres->rs_defin->rs_name,
				NULL, ATR_ENCODE_CLIENT, &pres->rs_value.at_priv_encoded);
		pres->rs_defin->rs_free(&tmp);
	} else {
		pnewres = (resource *)calloc(1, sizeof(resource));
		if (pnewres == NULL) {
			log_err(-1, __func__, "unable to calloc resource");
			return 1;
		}
		CLEAR_LINK(pnewres->rs_link);
		pnewres->rs_defin = resc_def;
		if ((rc = resc_def->rs_decode(&pnewres->rs_value, NULL, NULL, kv_val))) {
			snprintf(log_buffer, sizeof(log_buffer), "failed to decode res %s=%s, (rc=%d)", kv_keyw, kv_val, rc);
			log_err(-1, __func__, log_buffer);
			free(pnewres);
			return rc;
		}
		resc_def->rs_encode(&pnewres->rs_value, NULL, resc_def->rs_name,
				NULL, ATR_ENCODE_CLIENT, &pnewres->rs_value.at_priv_encoded);
		if (execv_f)
			pnewres->rs_value.at_flags |= ATR_VFLAG_IN_EXECVNODE_FLAG;
		if (cmp_res < 0)  /* pres will be NULL */
			append_link(&have->rl_other_res, &pnewres->rs_link, pnewres);
		else  /* cmp_res > 0, pres wont be NULL */
			insert_link(&pres->rs_link, &pnewres->rs_link, pnewres, LINK_INSET_BEFORE);
	}
	have->rl_res_count++;

	return 0;
}
#endif

/**
 * @brief
 *	Initialize to zero the resc_limit_t structure.
 *
 * @param[in]	have - the resc_limit_t structure.
 *
 * @return none
 */
void
resc_limit_init(resc_limit_t *have)
{
	if (have == NULL)
		return;

	have->rl_ncpus = 0;
	have->rl_ssi = 0;
	have->rl_mem = 0LL;
	have->rl_vmem = 0LL;
	have->rl_naccels = 0;
	have->rl_accel_mem = 0LL;
	CLEAR_HEAD(have->rl_other_res);
	have->rl_res_count = 0U;
	have->chunkstr = NULL;
	have->chunkstr_sz = 0;
	have->chunkspec = NULL;
	have->host_chunk[0].str = NULL;
	have->host_chunk[0].num = 0;
	have->host_chunk[1].str = NULL;
	have->host_chunk[1].num = 0;
}

/**
 * @brief
 *	Free resource list.
 *
 * @param[in]	pl_head - pointer to pbs_list_head of res list
 *
 * @return none
 */
void
resc_limit_free_res_list(pbs_list_head *pl_head)
{
	resource *next;
	resource *pr;

	if ((pl_head == NULL) || (pl_head->ll_next == NULL))
		return;

	pr = (resource *)GET_NEXT(*pl_head);
	while (pr != NULL) {
		next = (resource *)GET_NEXT(pr->rs_link);
		delete_link(&pr->rs_link);
		pr->rs_defin->rs_free(&pr->rs_value);
		free(pr);
		pr = next;
	}
	CLEAR_HEAD((*pl_head));
}

/**
 * @brief
 *	Free any malloced entries in resc_limit structure.
 *
 * @param[in]	have - the resc_limit structure.
 *
 * @return none
 */
void
resc_limit_free(resc_limit_t *have)
{
	if (have == NULL)
		return;

	resc_limit_free_res_list(&have->rl_other_res);
	have->rl_res_count = 0U;
	free(have->chunkstr);
	have->chunkstr = NULL;
	have->chunkstr_sz = 0;
	free(have->chunkspec);
	have->chunkspec = NULL;
	free(have->host_chunk[0].str);
	have->host_chunk[0].str = NULL;
	have->host_chunk[0].num = 0;
	free(have->host_chunk[1].str);
	have->host_chunk[1].str = NULL;
	have->host_chunk[1].num = 0;
}

/**
 * @brief
 *	Free any malloced entries in the 'resc_list' parameter..
 *
 * @param[in]	have - the resc_limit structure.
 *
 * @return none
 */
void
resc_limit_list_free(pbs_list_head *res_list)
{
	rl_entry		*p_entry = NULL;

	if (res_list == NULL)
		return;

	for (p_entry = (rl_entry *)GET_NEXT(*res_list); p_entry != NULL; p_entry = (rl_entry *)GET_NEXT(*res_list)) {
		resc_limit_free(p_entry->resc);
		free(p_entry->resc);
		delete_link(&p_entry->rl_link);
		free(p_entry);
	}
}

/**
 * @brief
 *	Print out the entries in the 'res_list' the server log under 'logtype'
 *
 * @param[in]	header_str - a string to accompany the logged message
 * @param[in]	res_list - the resc_limit structure list
 * @param[in]	logtype -  log level type
 *
 * @return none
 */
void
resc_limit_list_print(char *header_str, pbs_list_head *res_list, int logtype)
{
	rl_entry		*p_entry = NULL;
	int			i;
	resource		*phave;

	if ((header_str == NULL) || (res_list == NULL))
		return;

	p_entry = (rl_entry *)GET_NEXT(*res_list);
	i = 0;
	while (p_entry) {
		resc_limit_t *have;

		have = p_entry->resc;

		snprintf(log_buffer, sizeof(log_buffer), "%s[%d]: ncpus=%d ssi=%d mem=%lld vmem=%lld naccels=%d accel_mem=%lld chunkstr=%s host_chunk[0].str=%s host_chunk[1].str=%s",
				header_str,
				i,
				have->rl_ncpus,
				have->rl_ssi,
				have->rl_mem,
				have->rl_vmem,
				have->rl_naccels,
				have->rl_accel_mem,
				have->chunkstr?have->chunkstr:"",
				have->host_chunk[0].str?have->host_chunk[0].str:"",
				have->host_chunk[1].str?have->host_chunk[1].str:"");
		log_event(logtype, PBS_EVENTCLASS_RESC,
			LOG_INFO, __func__, log_buffer);
		for (phave = (resource *)GET_NEXT(have->rl_other_res);
			phave;
			phave = (resource *)GET_NEXT(phave->rs_link)) {
			snprintf(log_buffer, sizeof(log_buffer), "%s[%d]: other res %s=%s",
					header_str, i, phave->rs_defin->rs_name, phave->rs_value.at_priv_encoded->al_value);
			log_event(logtype, PBS_EVENTCLASS_RESC,
				LOG_INFO, __func__, log_buffer);
		}
		p_entry = (rl_entry *)GET_NEXT(p_entry->rl_link);
		i++;
	}
}

/**
 * @brief
 * 	Return in 'buf' of size 'sz' a string of the form:
 *
 *		<resource_name>=<resource_value>
 *
 * 	where <resource_name> and <resource_val> maps 'have_resc',
 *	'have_val'  against map_need value. <resource_value> must be of type int.
 *
 * @param[out]		buf - the buffer to fill
 * @param[in]		buf_sz - the size of 'buf'.
 * @param[in]		have_resc 	- the resource name being matched.
 * @param[in]		have_val	- the resource value available.
 * @param[in,out]	map_need_val 	- the needed value. If have_val is <
 *					  map_need_val, then map_need_val is
 *					  decremented by have_val amount and
 *					  returned.
 * @return none
 */
static void
intmap_need_to_have_resources(char *buf, size_t buf_sz,
		char *have_resc, char *have_val, int *map_need_val)
{
	int	have_int;
	char	*endp;

	if ((have_resc == NULL) || (have_val == NULL) || (buf == NULL) ||
	    (buf_sz == 0) || (map_need_val == NULL) ) {
		log_err(-1, __func__, "map_need_to_have_resources");
		return;
	}

	if (*map_need_val == 0)
		return;

	have_int = (int)strtol(have_val, &endp, 10);
	if (*endp != '\0') {
		log_err(errno, __func__, "strtoul error");
		return;
	}

	if (have_int > *map_need_val) {
		snprintf(buf, buf_sz, ":%s=%d", have_resc, *map_need_val);
		*map_need_val = 0;
	} else {
	 	*map_need_val -= have_int;
		snprintf(buf, buf_sz, ":%s=%s", have_resc, have_val);
	}
}

/**
 * @brief
 * 	Return in 'buf' of size 'sz' a string of the form:
 *
 *		<resource_name>=<resource_value>kb
 *
 * 	where <resource_name> and <resource_val> maps 'have_resc',
 *	'have_val'  against map_neeed value. <resource_value> must be of size
 *	value.
 *
 * @param[out]		buf - the buffer to fill
 * @param[in]		buf_sz - the size of 'buf'.
 * @param[in]		have_resc 	- the resource name being matched.
 * @param[in]		have_val	- the resource value we have in stock.
 * @param[in,out]	map_need_val 	- the needed value. If have_val is <
 *					  map_neeed_val, then map_need_val is
 *					  decremented by have_val amount and
 *					  returned.
 * @return none
 */
static void
sizemap_need_to_have_resources(char *buf, size_t buf_sz, char *have_resc, char *have_val,
			       long long *map_need_val)
{
	long long have_size;

	if ((have_resc == NULL) || (have_val == NULL) || (buf == NULL) ||
	    (buf_sz == 0) || (map_need_val == NULL) ) {
		log_err(-1, __func__, "map_need_to_have_resources");
		return;
	}

	if (*map_need_val == 0LL)
		return;

	have_size = to_kbsize(have_val);

	if (have_size > *map_need_val) {
		snprintf(buf, buf_sz, ":%s=%lldkb", have_resc, *map_need_val);
		*map_need_val = 0LL;
	} else {
	 	*map_need_val -= have_size;
		snprintf(buf, buf_sz, ":%s=%s", have_resc, have_val);
	}
}

/**
 * @brief
 * 	Return in 'buf' of size 'sz' a string of the form:
 *
 *		<resource_name>=<resource_value>kb
 *
 * 	where <resource_name> and <resource_val> map 'have_resc',
 *	'have_val' against the resc_limit 'need' value.
 *
 * @param[out]		buf - the buffer to fill
 * @param[in]		buf_sz - the size of 'buf'.
 * @param[in]		have_resc 	- the resource name being matched.
 * @param[in]		have_val	- the resource value we have in stock.
 * @param[in,out]	need		- a resc_limit_t structure.
 *					  The 'need' value is
 *					  decremented by have_val amount and
 *					  returned.
 * @return none
 */
static void
map_need_to_have_resources(char *buf, size_t buf_sz, char *have_resc,
			    char *have_val, resc_limit_t *need)
{

	if ((buf == NULL) || (buf_sz == 0) || (have_resc == NULL) ||
	     (have_val == NULL) || (need == NULL)) {
		return;
	}

	if (strcmp(have_resc, "ncpus") == 0) {
		intmap_need_to_have_resources(buf, buf_sz,
				have_resc, have_val, &need->rl_ncpus);

	} else if (strcmp( have_resc, "mem") == 0) {
		sizemap_need_to_have_resources(buf, buf_sz,
				have_resc, have_val, &need->rl_mem);

	} else if (strcmp( have_resc, "vmem") == 0) {
		sizemap_need_to_have_resources(buf, buf_sz,
				have_resc, have_val, &need->rl_vmem);

	} else if (strcmp( have_resc, "naccelerators") == 0) {
		intmap_need_to_have_resources(buf, buf_sz,
			have_resc, have_val, &need->rl_naccels);

	} else if ( strcmp(have_resc, "accelerator_memory") == 0) {
		sizemap_need_to_have_resources(buf, buf_sz,
			have_resc, have_val, &need->rl_accel_mem);
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
	} else {
		resource *pneed;
		for (pneed = (resource *)GET_NEXT(need->rl_other_res);
			pneed;
			pneed = (resource *)GET_NEXT(pneed->rs_link)) {
			if (strcasecmp(have_resc, pneed->rs_defin->rs_name) == 0) {
				attribute hattr = {0};
				int cmp_res;
				if (!(pneed->rs_value.at_flags & ATR_VFLAG_IN_EXECVNODE_FLAG))
					return;
				pneed->rs_defin->rs_decode(&hattr, NULL, NULL, have_val);
				cmp_res = pneed->rs_defin->rs_comp(&hattr, &pneed->rs_value);
				if (!cmp_res) {
					resource *tmp =  pneed;
					pneed = (resource *)pneed->rs_link.ll_prior;
					snprintf(buf, buf_sz, ":%s=%s", have_resc, have_val);
					delete_link(&tmp->rs_link);
					tmp->rs_defin->rs_free(&tmp->rs_value);
					free(tmp);
				} else {
					if (cmp_res > 0) {
						snprintf(buf, buf_sz, ":%s=%s", have_resc, pneed->rs_value.at_priv_encoded->al_value);
						pneed->rs_defin->rs_decode(&pneed->rs_value, NULL, NULL, "0");
					} else {
						pneed->rs_defin->rs_set(&pneed->rs_value, &hattr, DECR);
						snprintf(buf, buf_sz, ":%s=%s", have_resc, have_val);
					}
					free_svrcache(&pneed->rs_value);
					pneed->rs_defin->rs_encode(&pneed->rs_value, NULL, pneed->rs_defin->rs_name,
							NULL, ATR_ENCODE_CLIENT, &pneed->rs_value.at_priv_encoded);
				}
			}
		}
#endif
	}
}

/**
 * @brief
 *	Helper function that adds 'noden' resources assigned
 *	'keyw' = 'keyval' values to 'vnlp'.
 * @param[in]	vnlp	- vnode list structure
 * @param[in]	noden   - the node/vnode represented
 * @param[in]	keyw	- resource name
 * @param[in]	keyval	- resource value
 * @return int
 * @retval	0	- success
 * @retval	1	- failure
 */
static int
add_to_vnl(vnl_t **vnlp, char *noden, char *keyw, char *keyval)
{
#if defined(PBS_MOM) || defined(PBS_PYTHON)
	int 		rc;
	char 		buf[LOG_BUF_SIZE];
	char 		buf_val[LOG_BUF_SIZE];
	char		*attr_val = NULL;

	if ((vnlp == NULL) || (noden == NULL) || (keyw == NULL) || (keyval == NULL))
		return (0);

	if (*vnlp == NULL) {
		if (vnl_alloc(vnlp) == NULL) {
			log_err(errno, __func__,
		  	"Failed to allocate a vnlp structure");
			return (1);
		}
	}

	snprintf(buf, sizeof(buf), "resources_assigned.%s", keyw);

	snprintf(buf_val, sizeof(buf_val), "%s", keyval);

	attr_val = vn_exist(*vnlp, noden, buf);
	if (attr_val != NULL) {

		if ((strcmp(buf, "resources_assigned.mem") == 0) ||
		    (strcmp(buf, "resources_assigned.vmem") == 0) ||
		    (strcmp(buf, "resources_assigned.accelerator_memory") == 0)) {
			long long size1;
			long long size2;

			size1 = to_kbsize(attr_val);
			size2 = to_kbsize(keyval);

			snprintf(buf_val, sizeof(buf_val), "%lldkb", size1 + size2);

		} else {
			int	val1;
			int	val2;

			val1 = atol(attr_val);
			val2 = atol(keyval);
			snprintf(buf_val, sizeof(buf_val)-1, "%d", val1 + val2);

		}
	}
	rc = vn_addvnr(*vnlp, noden, buf, buf_val, 0, 0, NULL);
	if (rc == -1) {
		char *msgbuf;
		pbs_asprintf(&msgbuf, "failed to add '%s=%s', buf, keyval");
		log_err(-1, __func__ , msgbuf);
		free(msgbuf);
		return (1);
	}
#endif
	return (0);
}

#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
/**
 * @brief
 *	Check if other resources in 'have' satisfy the remaining
 *	 resources from 'need'.
 *
 * @param[in]	need - the need value of resc_limit_t type.
 * @param[in]	have - the have value of resc_limit_t type.
 *
 * @return int
 *	 1 - if not satisfied
 *	 0 - otherwise
 *	-1 - error
 */
static int
check_other_res(resc_limit_t *need, resc_limit_t *have)
{
	resource *pneed, *phave;

	if ((need == NULL) || (have == NULL))
		return -1;

	if (!GET_NEXT(need->rl_other_res))
		return 0;

	for (pneed = (resource *)GET_NEXT(need->rl_other_res);
		pneed;
		pneed = (resource *)GET_NEXT(pneed->rs_link)) {
		int matched = 0;
		for (phave = (resource *)GET_NEXT(have->rl_other_res);
			phave;
			phave = (resource *)GET_NEXT(phave->rs_link)) {
			if (pneed->rs_defin == phave->rs_defin) {
				resource_def *prdef = pneed->rs_defin;
				unsigned int atr_type = prdef->rs_type;
				if ((atr_type == ATR_TYPE_STR)
					|| (atr_type == ATR_TYPE_BOOL)) {
					if (!prdef->rs_comp(&pneed->rs_value, &phave->rs_value)) {
						matched = 1;
						break;
					}
				} else { /* for atr type long, float and size */
					if (prdef->rs_comp(&pneed->rs_value, &phave->rs_value) <= 0) {
						matched = 1;
						break;
					}
				}
			}
		}
		if (!matched)
			return 1;
	}

	return 0;
}

/**
 * @brief
 *	appends a chunk spec to sched select and also tries to
 *	group identical chunk specs by increasing the chunk count
 *
 * @param[in/out]	new_schedselect - pointer to new sched select
 * @param[in]		chunkstr - current chunk spec to append
 * @param[in/out]	tmp_chunk_spec - buffer to accumulate identical chunk specs
 * @param[in/out]	tmp_chunk_ct - count of gathered identical chunk specs
 *
 * @return none
 */
static void
append_and_group_sched_sel(char *new_schedselect, char *chunkstr, char *tmp_chunk_spec, int *tmp_chunk_ct)
{
	if ((new_schedselect == NULL) || (chunkstr == NULL) || (tmp_chunk_spec == NULL) || (tmp_chunk_ct == NULL)) {
		log_err(-1, __func__, "a parameter is NULL");
		return;
	}

	if (*tmp_chunk_spec) {
		if (!strcasecmp(tmp_chunk_spec, chunkstr)) {
			(*tmp_chunk_ct)++;
			return;
		}
		if (*new_schedselect)
			strcat(new_schedselect, "+");
		sprintf(new_schedselect + strlen(new_schedselect), "%d:%s", *tmp_chunk_ct, tmp_chunk_spec);
	}

	(*tmp_chunk_ct) = 1;
	strcpy(tmp_chunk_spec, chunkstr);
}
#endif

/**
 * @brief
 *	Return a string representing a chunk that satisfies 'need'
 *	 resources from the 'have' pool.
 *
 * @param[in]	need - the need value of resc_limit_t type.
 * @param[in]	have - the have value of resc_limit_t type.
 * @param[in]	vnlp - if not-NULL, add the vnodes and
 *			resources that satisfy 'need'
 *			request against 'have' resources.
 *
 * @return char *
 *	<chunk string> - if successful
 *	NULL 		- if could not find a chunk string to satisfy need
 *			  against have, or if an error occurred.
 */
static char *
satisfy_chunk_need(resc_limit_t *need, resc_limit_t *have, vnl_t **vnlp)
{
	resc_limit_t 	map_need;
	char		*chunk = NULL;
	char		*noden;
	int		nelem;
	char		*chunkstr = NULL;
	static char	*ret_chunkstr = NULL;
	static size_t	ret_chunkstr_size = 0;
	size_t		data_size = 0;
	char		buf[LOG_BUF_SIZE];
	struct	key_value_pair *pkvp;
	int		paren = 0;
	int		found_paren = 0;
	char		*last = NULL;
	int		hasprn = 0;
	int		j;
	int		entry = 0;
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
	resource	*presnew, *pres, *pneed;
#endif

	if ((need == NULL) || (have == NULL))
		return (NULL);

	if ((have->chunkstr == NULL) || (have->chunkstr[0] == '\0'))
		return (NULL);

	if ((need->rl_ncpus > have->rl_ncpus) ||
	    (need->rl_mem > have->rl_mem) ||
	    (need->rl_ssi > have->rl_ssi) ||
	    (need->rl_vmem > have->rl_vmem) ||
	    (need->rl_naccels > have->rl_naccels) ||
	    (need->rl_accel_mem > have->rl_accel_mem)
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
		|| check_other_res(need,have)
#endif
		) {
		return (NULL);
	}

	memset(&map_need, 0, sizeof(resc_limit_t));
	resc_limit_init(&map_need);

#if defined(PBS_MOM) || defined(PBS_PYTHON)
	map_need.rl_ncpus = need->rl_ncpus;
	map_need.rl_mem = need->rl_mem;
	map_need.rl_ssi = need->rl_ssi;
	map_need.rl_vmem = need->rl_vmem;
	map_need.rl_naccels = need->rl_naccels;
	map_need.rl_accel_mem = need->rl_accel_mem;
#else
	map_need.rl_ncpus = have->rl_ncpus;
	map_need.rl_mem = have->rl_mem;
	map_need.rl_ssi = have->rl_ssi;
	map_need.rl_vmem = have->rl_vmem;
	map_need.rl_naccels = have->rl_naccels;
	map_need.rl_accel_mem = have->rl_accel_mem;

	for (pres = (resource *)GET_NEXT(have->rl_other_res);
		pres;
		pres = (resource *)GET_NEXT(pres->rs_link)) {
		presnew = (resource *)calloc(1, sizeof(resource));
		if (presnew == NULL) {
			log_err(-1, __func__, "unable to calloc resource");
			return (NULL);
		}
		CLEAR_LINK(presnew->rs_link);
		presnew->rs_defin = pres->rs_defin;
		append_link(&map_need.rl_other_res, &presnew->rs_link, presnew);
		presnew->rs_defin->rs_set(&presnew->rs_value, &pres->rs_value, SET);
		presnew->rs_defin->rs_encode(&presnew->rs_value, NULL, presnew->rs_defin->rs_name,
				NULL, ATR_ENCODE_CLIENT, &presnew->rs_value.at_priv_encoded);
		if (pres->rs_value.at_flags & ATR_VFLAG_IN_EXECVNODE_FLAG)
			presnew->rs_value.at_flags |= ATR_VFLAG_IN_EXECVNODE_FLAG;
	}

	if (need->rl_ncpus)
		map_need.rl_ncpus = need->rl_ncpus;
	if (need->rl_mem)
		map_need.rl_mem = need->rl_mem;
	if (need->rl_ssi)
		map_need.rl_ssi = need->rl_ssi;
	if (need->rl_vmem)
		map_need.rl_vmem = need->rl_vmem;
	if (need->rl_naccels)
		map_need.rl_naccels = need->rl_naccels;
	if (need->rl_accel_mem)
		map_need.rl_accel_mem = need->rl_accel_mem;

	pres = (resource *)GET_NEXT(map_need.rl_other_res);
	pneed = (resource *)GET_NEXT(need->rl_other_res);
	while (pres && pneed) {
		unsigned int res_type = pneed->rs_defin->rs_type;;
		while (pres && (pneed->rs_defin != pres->rs_defin))
			pres = (resource *)GET_NEXT(pres->rs_link);
		if (!pres)
			break;

		if (((res_type == ATR_TYPE_LONG)
			|| (res_type == ATR_TYPE_SIZE)
			|| (res_type == ATR_TYPE_FLOAT))
			&& (pres->rs_defin->rs_comp(&pres->rs_value, &pneed->rs_value))) {
			pres->rs_defin->rs_free(&pres->rs_value); /* ATR_VFLAG_IN_EXECVNODE_FLAG gets preserved */
			pres->rs_defin->rs_set(&pres->rs_value, &pneed->rs_value, SET);
			pres->rs_defin->rs_encode(&pres->rs_value, NULL, pres->rs_defin->rs_name,
					NULL, ATR_ENCODE_CLIENT, &pres->rs_value.at_priv_encoded);
		}
		pneed = (resource *)GET_NEXT(pneed->rs_link);
	}
#endif

	data_size = strlen(have->chunkstr) + 1;
	if (data_size > ret_chunkstr_size ) {
		char *tpbuf;

		tpbuf = realloc(ret_chunkstr, data_size);
		if (tpbuf == NULL) {
			log_err(-1, __func__, "realloc failure");
			resc_limit_free(&map_need);
			return (NULL);
		}
		ret_chunkstr = tpbuf;
		ret_chunkstr_size = data_size;
	}
	ret_chunkstr[0] = '\0';

	chunkstr = strdup(have->chunkstr);
	if (chunkstr == NULL) {
		log_err(errno, __func__, "strdup 1 failure");
		resc_limit_free(&map_need);
		return (NULL);
	}

	for (chunk = parse_plus_spec_r(chunkstr, &last, &hasprn);
	     chunk != NULL;
	     chunk = parse_plus_spec_r(last, &last, &hasprn) ) {

		paren += hasprn;

		if (parse_node_resc(chunk, &noden, &nelem, &pkvp) == 0) {
			int	vnode_in = 0;

			if (((hasprn > 0) && (paren > 0)) || ((hasprn == 0) && (paren == 0))) {
				/* at the beginning of chunk for current host */
				if (!found_paren) {
					strcat(ret_chunkstr, "(");
					found_paren = 1;

				}
				for (j = 0; j < nelem; ++j) {

					buf[0] = '\0';
					map_need_to_have_resources(buf,
						sizeof(buf) - 1, pkvp[j].kv_keyw, pkvp[j].kv_val, &map_need);

					if (buf[0] != '\0') {
						if (!vnode_in) {
							if (entry > 0) {
								strcat(ret_chunkstr, "+");
							}
							strcat(ret_chunkstr, noden);
							entry++;
							vnode_in = 1;
						}
						strcat(ret_chunkstr, buf);
						(void)add_to_vnl(vnlp, noden, pkvp[j].kv_keyw, pkvp[j].kv_val);
					}
				}

				if (paren == 0) { /* have all chunks for current host */

					if (found_paren) {
						strcat(ret_chunkstr, ")");
						found_paren = 0;
					}


				}
			} else {

				if (!found_paren) {
					strcat(ret_chunkstr, "(");
					found_paren = 1;

				}
				for (j = 0; j < nelem; ++j) {
					buf[0] = '\0';
					map_need_to_have_resources(buf, sizeof(buf) - 1, pkvp[j].kv_keyw, pkvp[j].kv_val, &map_need);

					if (buf[0] != '\0') {
						if (!vnode_in) {
							if (entry > 0) {
								strcat(ret_chunkstr, "+");
							}
							strcat(ret_chunkstr, noden);
							entry++;
							vnode_in = 1;
						}
						strcat(ret_chunkstr, buf);
						(void)add_to_vnl(vnlp, noden, pkvp[j].kv_keyw, pkvp[j].kv_val);
					}
				}
			}

			if (paren == 0) { /* have all chunks for current host */

				if (found_paren) {
					strcat(ret_chunkstr, ")");
					found_paren = 0;
				}
			}

		} else {
			log_err(errno, __func__, "parse_node_resc_error");
			free(chunkstr);
			resc_limit_free(&map_need);
			return (NULL);
		}
	}

	free(chunkstr);
	resc_limit_free(&map_need);
	return (ret_chunkstr);
}


/*
 * @brief
 *	Initialize the relnodes_input_t structure used as argument to
 *	pbs_release_nodes_given_nodelist() and pbs_release_nodes_given_select()
 *	functions.
 * @param[out]	r_input	- structure to initialize
 * @return none
 */
void
relnodes_input_init(relnodes_input_t *r_input)
{
	r_input->jobid = NULL;
	r_input->vnodes_data = NULL;
	r_input->execvnode = NULL;
	r_input->exechost = NULL;
	r_input->exechost2 = NULL;
	r_input->schedselect = NULL;
	r_input->p_new_exec_vnode = NULL;
	r_input->p_new_exec_host[0] = NULL;
	r_input->p_new_exec_host[1] = NULL;
	r_input->p_new_schedselect = NULL;
}

/*
 * @brief
 *	Initialize the relnodes_input_select_t structure used as argument to
 *	pbs_release_nodes_given_select() function.
 *
 * @param[out]	r_input	- structure to initialize
 * @return none
 */
void
relnodes_input_select_init(relnodes_input_select_t *r_input)
{
	r_input->select_str = NULL;
	r_input->failed_mom_list = NULL;
	r_input->succeeded_mom_list = NULL;
	r_input->failed_vnodes = NULL;
	r_input->good_vnodes = NULL;
}

/**
 *
 * @brief
 *	Return a subset of the exec_vnode string 'e_vnode'
 *	where only vnode chunks matching the vnode names
 *	in 'vnl_good' (list of healthy vnodes) are shown.
 * @par
 *	For example, given:
 *		e_vnode = (vn1:<r1>=<v1>)+(vn2:<r2>=<v2>)+(vn3:<r3>=<v3>)
 *	and
 *		vnl_fails lists: vn2
 *
 *	then this function returns:
 *		e_vnode = (vn1:<r1>=<v1>)+(vn3:<r3>=<v3>)
 *
 * @param[in]	e_vnode - exec_vnode string
 * @param[in]	vnl_good - some list of names of failed vnodes
 *
 * @return char *
 * @retval != NULL	the exec_vnode string of healthy vnodes
 * @retval == NULL	if error encountered.
 *
 * @note
 *	The returned string points to a statically allocated buffer
 *	that must not be freed, and will get overwritten on the
 *	next call to this function.
 *
 */
static char *
return_available_vnodes(char *e_vnode, vnl_t *vnl_good)
{
	char		*save_ptr;
	char		*pc;
	char		*tmpbuf;
	static	char	*ebuf = NULL;
	static int	ebuf_size = 0;

	if (e_vnode == NULL)
		return NULL;

	tmpbuf = strdup(e_vnode);
	if (tmpbuf == NULL) {
		log_err(errno, __func__, "strdup failed");
		return NULL;
	}

	if (ebuf == NULL) {
		ebuf = malloc(LOG_BUF_SIZE + 1);
		if (ebuf == NULL) {
			log_err(errno, __func__, "malloc failed");
			return NULL;
		}
		ebuf_size = LOG_BUF_SIZE;
	}

	ebuf[0] = '\0';
	for (pc = strtok_r(tmpbuf, "+", &save_ptr); pc != NULL; pc = strtok_r(NULL, "+", &save_ptr)) {
		char *vn = pc;
		char *p;

		p = strchr(pc, ':');
		if (p != NULL) {
			*p = '\0';
			if (*vn == '(')
				vn++;
			if (vn_vnode(vnl_good, vn)) {
				*p = ':';
				if (ebuf[0] != '\0') {
					if (pbs_strcat(&ebuf, &ebuf_size, "+") == NULL) {
						free(tmpbuf);
						return NULL;
					}
				}
				if (pbs_strcat(&ebuf, &ebuf_size, pc) == NULL) {
					free(tmpbuf);
					return NULL;
				}
			} else {
				*p = ':';
			}

		} else {
			if (ebuf[0] != '\0') {
				if (pbs_strcat(&ebuf, &ebuf_size, "+") == NULL) {
					free(tmpbuf);
					return NULL;
				}
			}
			if (pbs_strcat(&ebuf, &ebuf_size, pc) == NULL) {
				free(tmpbuf);
				return NULL;
			}
		}
	}

	free(tmpbuf);
	return (ebuf);
}

/**
 * @brief
 *	Release node resources from a job in such a way it satisfies some
 *	specified select value.
 *
 * @param[in]		r_input	- contains various input including the job id
 * @param[in,out]	r_input2 - contains various input and output parameters
 *				   including the desired 'select' spec, as well
 *				   the resulting new values to job's exec_vnode,
 *				   exec_host, exec_host2, and schedselect.
 * @param[out]		err_msg - gets filled in with the error message if this
 *				  function returns a non-zero value.
 * @param[int]		err_sz - size of the 'err_msg' buffer.
 * @return int
 * @retval 0 - success
 * @retval 1 - fail with 'err_msg' filled in with message.
 */
int
pbs_release_nodes_given_select(relnodes_input_t *r_input, relnodes_input_select_t *r_input2, char *err_msg, int err_msg_sz)
{
	char		*new_exec_vnode = NULL;
	char		*new_exec_host = NULL;
	char		*new_exec_host2 = NULL;
	char		*new_schedselect = NULL;
	char		*noden;
	int		nelem;
	int		paren = 0;
	int		found_paren = 0;
	char		*chunk = NULL;
	char		*chunk1 = NULL;
	char		*chunk2 = NULL;
	int		entry = 0;
	int		h_entry = 0;
	char		buf[LOG_BUF_SIZE];

	struct	key_value_pair *pkvp;
	char		*last = NULL;
	char		*last1 = NULL;
	char		*last2 = NULL;
	char		*last3 = NULL;
        int		hasprn = 0;
        int		hasprn1 = 0;
        int		hasprn2 = 0;
	int		hasprn3;
	char		*exec_vnode = NULL;
	char		*exec_host = NULL;
	char		*exec_host2 = NULL;

	resc_limit_t 	*have = NULL;
	resc_limit_t	*have2 = NULL;
	pbs_list_head	resc_limit_list;
	resc_limit_t	*have0 = NULL;

	char		*selbuf = NULL;
	char		*psubspec;
	int		rc = 1;
	resc_limit_t	need;
	int		snelma;
	static int       snelmt = 0;
	static key_value_pair *skv = NULL;
	rl_entry	*p_entry = NULL;
	int		matched = 0;
	int		snc;
	int		h, i,j, k, l;
	char		*new_chunkstr = NULL;
	/* job vnodes that have been out as their parent moms are non-functioning */
	vnl_t		*vnl_fails = NULL;
	/* job vnodess that have functioning parent moms */
	vnl_t		*vnl_good = NULL;
	vnl_t		*vnl_good_master = NULL;
	char		prev_noden[PBS_MAXNODENAME + 1];
	char		*parent_mom;
	char		*tmpstr;
	char		*chunk_buf = NULL;
	int		chunk_buf_sz = 0;
#ifdef PBS_MOM
	resource_def	*resc_def = NULL;
	momvmap_t 	*vn_vmap = NULL;
#else
	struct pbsnode	*pnode = NULL;
	char		e2buf[PBS_MAXHOSTNAME+1+6+16];
#ifndef PBS_PYTHON
	char		*extra_res = NULL;
	resource	*pres;
	char		*sched_select = NULL;
	char		*chunkschsel = NULL;
	char		*res_in_exec_vnode = NULL;
	char		*lastschsel = NULL;
	int		hasprnschsel = 0;
	char		*tmp_chunk_spec = NULL;
	int		tmp_chunk_ct;
#endif
#endif

	if ((r_input == NULL) || (r_input2 == NULL) || (r_input->jobid == NULL) || (r_input->execvnode == NULL) || (r_input->exechost == NULL) || (r_input->exechost2 == NULL) || (r_input->schedselect == NULL) || (err_msg == NULL) || (err_msg_sz <= 0)) {
		log_err(-1, __func__, "required parameter is null");
		return (1);
	}
	err_msg[0] = '\0';
	resc_limit_init(&need);
	exec_vnode = strdup(r_input->execvnode);
	if (exec_vnode == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodes_exit;
	}

	exec_host = strdup(r_input->exechost);
	if (exec_host == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodes_exit;
	}

	exec_host2 = strdup(r_input->exechost2);
	if (exec_host2 == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodes_exit;
	}

#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
	sched_select = expand_select_spec(r_input->schedselect);
	if (sched_select == NULL) {
		log_err(errno, __func__, "strdup error");
		goto release_nodes_exit;
	}
	if (!(new_schedselect = malloc(strlen(sched_select)))) {
		log_err(errno, __func__, "new_schedselect malloc failed");
		goto release_nodes_exit;
	}
	*new_schedselect = '\0';

	if (!(tmp_chunk_spec = malloc(strlen(r_input->schedselect)))) {
		log_err(errno, __func__, "tmp_chunk_spec malloc failed");
		goto release_nodes_exit;
	}
	*tmp_chunk_spec = '\0';
	res_in_exec_vnode = resources_seen(exec_vnode);
#endif

	chunk_buf_sz = strlen(exec_vnode)+1;
	chunk_buf = (char *) calloc(1, chunk_buf_sz);
	if (chunk_buf == NULL) {
		log_err(errno, __func__, "chunk_buf calloc error");
		goto release_nodes_exit;
	}

	reliable_job_node_print("job failed_mom_list",
		r_input2->failed_mom_list, PBSEVENT_DEBUG3);
	reliable_job_node_print("job succeeded_mom_list",
			r_input2->succeeded_mom_list, PBSEVENT_DEBUG3);

	/* now parse exec_vnode to build up the 'have' resources list */
	CLEAR_HEAD(resc_limit_list);

	/* There's a 1:1:1 mapping among exec_vnode parenthesized entries, exec_host, */
	/* and exec_host2,  */
	entry = 0;	/* exec_vnode entries */
	h_entry = 0;	/* exec_host* entries */
	paren = 0;
	prev_noden[0] = '\0';
	k = 0;
	parent_mom = NULL;
	for (chunk = parse_plus_spec_r(exec_vnode, &last, &hasprn),
	     chunk1 = parse_plus_spec_r(exec_host, &last1, &hasprn1),
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
	     chunkschsel = parse_plus_spec_r(sched_select, &lastschsel, &hasprnschsel),
#endif
	     chunk2 = parse_plus_spec_r(exec_host2,&last2, &hasprn2);
	     (chunk != NULL) && (chunk1 != NULL)
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
		&& (chunkschsel != NULL)
#endif
		&& (chunk2 != NULL);
	     chunk = parse_plus_spec_r(last, &last, &hasprn) ) {

		paren += hasprn;
		strncpy(chunk_buf, chunk, chunk_buf_sz - 1);
		if (parse_node_resc(chunk, &noden, &nelem, &pkvp) == 0) {

#ifdef PBS_MOM
			/* see if previous entry already matches this */
			if ((strcmp(prev_noden, noden) != 0)) {
				vn_vmap = find_vmap_entry(noden);
				if (vn_vmap == NULL) { /* should not happen */

					if ((err_msg != NULL) && (err_msg_sz > 0)) {
						snprintf(err_msg, err_msg_sz, "no vmap entry for %s", noden);
        					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
					}
					goto release_nodes_exit;
				}
				if (vn_vmap->mvm_hostn != NULL) {
					parent_mom = vn_vmap->mvm_hostn;
				} else {
					parent_mom = vn_vmap->mvm_name;
				}
			}

			if (parent_mom == NULL) { /* should not happen */

				if ((err_msg != NULL) && (err_msg_sz > 0)) {
					snprintf(err_msg, err_msg_sz, "no parent_mom for for %s", noden);
        				log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
				}
				goto release_nodes_exit;
			}

			strncpy(prev_noden, noden, PBS_MAXNODENAME);
#else
			e2buf[0] = '\0';
			if (r_input->vnodes_data != NULL) {
				/* see if previous entry already matches this */
				if ((strcmp(prev_noden, noden) != 0)) {
					char key_buf[BUF_SIZE];
					svrattrl *svrattrl_e;

					snprintf(key_buf, BUF_SIZE, "%s.resources_assigned", noden);
					if ((svrattrl_e = find_svrattrl_list_entry(r_input->vnodes_data, key_buf, "host,string")) != NULL) {
						parent_mom = svrattrl_e->al_value;
					}
				}

				strncpy(prev_noden, noden, PBS_MAXNODENAME);
			} else {
				/* see if previous entry already matches this */
				if ((pnode == NULL) ||
					(strcmp(pnode->nd_name, noden) != 0)) {
					pnode = find_nodebyname(noden);
				}

				if (pnode == NULL) { /* should not happen */
					if ((err_msg != NULL) && (err_msg_sz > 0)) {
						snprintf(err_msg, err_msg_sz, "no node entry for %s", noden);
        					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
					}
					goto release_nodes_exit;
				}

				parent_mom = NULL;

				if (chunk2 && *chunk2) {
					char *tmp;
					int  i;
					snprintf(e2buf, sizeof(e2buf), "%s", chunk2);
					tmp = strtok(e2buf, ":/");

					for (i = 0; tmp && (i < pnode->nd_nummoms); i++) {
						if ((strcmp(pnode->nd_moms[i]->mi_host, tmp) == 0)) {
							parent_mom = tmp;
						}
					}
				}
			}

			if (parent_mom == NULL) { /* should not happen */

				if ((err_msg != NULL) && (err_msg_sz > 0)) {
					snprintf(err_msg, err_msg_sz, "no parent_mom for for %s", noden);
    					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_DEBUG, r_input->jobid, err_msg);
				}
				goto release_nodes_exit;
			}
#endif

			if (reliable_job_node_find(r_input2->succeeded_mom_list, parent_mom) != NULL) {
				if (entry > 0) { /* there's something */
						 /* put in previously */
					if (have != NULL) {
						if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, "+") == NULL)
							goto release_nodes_exit;
					}
				}

				if (((hasprn > 0) && (paren > 0)) ||
				     ((hasprn == 0) && (paren == 0))) {
						 /* at the beginning of chunk for current host */
					if (!found_paren) {

						free(have);
						have = (resc_limit_t *)malloc(sizeof(resc_limit_t));
						if (have == NULL) {
							goto release_nodes_exit;
						}
						/* clear "have" counts */
						resc_limit_init(have);

						if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, "(") == NULL)
							goto release_nodes_exit;
						found_paren = 1;

						if (h_entry > 0) {
							/* there's already previous exec_host entry */
							if ((have->host_chunk[0].str != NULL) &&
								have->host_chunk[0].str[0] != '\0') {
								if (pbs_strcat(&have->host_chunk[0].str, &have->host_chunk[0].num, "+") == NULL)
									goto release_nodes_exit;
							}
							if ((have->host_chunk[1].str != NULL) &&
								(have->host_chunk[1].str[0] != '\0')) {
								if (pbs_strcat(&have->host_chunk[1].str, &have->host_chunk[1].num, "+") == NULL)
									goto release_nodes_exit;
							}
						}

						if (pbs_strcat(&have->host_chunk[0].str, &have->host_chunk[0].num, chunk1) == NULL)
							goto release_nodes_exit;
						if (pbs_strcat(&have->host_chunk[1].str, &have->host_chunk[1].num, chunk2) == NULL)
							goto release_nodes_exit;
						h_entry++;
					}
				}
				if (have == NULL) {
					log_err(-1, __func__, "unexpected NULL 'have' value");
					goto release_nodes_exit;
				}

				if (!found_paren) {
					if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, "(") == NULL)
						goto release_nodes_exit;
					found_paren = 1;


					if (h_entry > 0) {
						/* there's already previous */
						/* exec_host entry */
						if ((have->host_chunk[0].str != NULL) &&
								(have->host_chunk[0].str[0] != '\0')) {
							if (pbs_strcat(&have->host_chunk[0].str, &have->host_chunk[0].num, "+") == NULL)
								goto release_nodes_exit;
						}
						if ((have->host_chunk[1].str != NULL) &&
								(have->host_chunk[1].str[0] != '\0')) {
							if (pbs_strcat(&have->host_chunk[1].str, &have->host_chunk[1].num, "+") == NULL)
								goto release_nodes_exit;
						}
					}
					if (pbs_strcat(&have->host_chunk[0].str, &have->host_chunk[0].num, chunk1) == NULL)
						goto release_nodes_exit;

					if (pbs_strcat(&have->host_chunk[1].str, &have->host_chunk[1].num, chunk2) == NULL)
						goto release_nodes_exit;

					h_entry++;
				}
				if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, noden) == NULL)
					goto release_nodes_exit;
				entry++;

				for (j = 0; j < nelem; ++j) {

#ifdef PBS_MOM
					resc_def = find_resc_def(svr_resc_def, pkvp[j].kv_keyw);
					if (resc_def == NULL) {
						continue;
					}
					if (add_to_vnl(&vnl_good, noden, pkvp[j].kv_keyw, pkvp[j].kv_val) != 0) {
						goto release_nodes_exit;
					}
#endif
					snprintf(buf, sizeof(buf),
						":%s=%s", pkvp[j].kv_keyw, pkvp[j].kv_val);
					if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, buf) == NULL)
						goto release_nodes_exit;
					if (strcmp(pkvp[j].kv_keyw, "ncpus") == 0) {
						have->rl_ncpus += atol(pkvp[j].kv_val);
					} else if (strcmp(pkvp[j].kv_keyw, "mem") == 0) {
						have->rl_mem += to_kbsize(pkvp[j].kv_val);
					} else if (strcmp( pkvp[j].kv_keyw, "vmem") == 0) {
						have->rl_vmem += to_kbsize(pkvp[j].kv_val);
					} else if (strcmp( pkvp[j].kv_keyw, "ssinodes")==0) {
						have->rl_ssi  += atol(pkvp[j].kv_val);
					} else if (strcmp( pkvp[j].kv_keyw, "naccelerators") == 0) {
						have->rl_naccels += atol(pkvp[j].kv_val);
					} else if (
						strcmp(pkvp[j].kv_keyw, "accelerator_memory") == 0) {
						have->rl_accel_mem += to_kbsize(pkvp[j].kv_val);
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
					} else {
						rc = resc_limit_insert_other_res(have, pkvp[j].kv_keyw, pkvp[j].kv_val, TRUE);
						if (rc != 0) {
							snprintf(log_buffer, sizeof(log_buffer), "failed to insert resource %s", pkvp[j].kv_keyw);
							log_err(-1, __func__, log_buffer);
							goto release_nodes_exit;
						}
#endif
					}
				}

				if (paren == 0) { /* have all chunks for current host */

					if (found_paren) {
						if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, ")") == NULL)
							goto release_nodes_exit;
						found_paren = 0;
					}

#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
					if (!(have->chunkspec = strdup(chunkschsel + 2))) { /* +2 is to skip past '1:' */
						log_err(errno, __func__, "strdup error");
						goto release_nodes_exit;
					}
					extra_res = return_missing_resources(chunkschsel,
								res_in_exec_vnode);
					if ((extra_res) && (*extra_res)) {
						char *word,*value,*last;
						int x;
						for (x = parse_resc_equal_string(extra_res, &word, &value, &last);
							x == 1;
							x = parse_resc_equal_string(last, &word, &value, &last)) {
							if ((rc = resc_limit_insert_other_res(have, word, value, FALSE))) {
								snprintf(log_buffer, sizeof(log_buffer), "failed to insert resource %s", word);
								log_err(-1, __func__, log_buffer);
								goto release_nodes_exit;
							}
						}
					}

					if (have->rl_ncpus)
						have->rl_res_count++;
					if (have->rl_ssi)
						have->rl_res_count++;
					if (have->rl_mem)
						have->rl_res_count++;
					if (have->rl_vmem)
						have->rl_res_count++;
					if (have->rl_naccels)
						have->rl_res_count++;
					if (have->rl_accel_mem)
						have->rl_res_count++;
#endif
				}
			} else {
				if (paren == 0) { /* have all chunks for current host */

					if (found_paren) {
						if (have == NULL) {
							log_err(-1, __func__, "unexpected NULL 'have' value");
							goto release_nodes_exit;
						}
						if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, ")") == NULL)
							goto release_nodes_exit;
						found_paren = 0;
					}

				}
				/* only save in 'failed_nodes' those nodes that are non in good mom_List but in failed_mom_list */
				if ((r_input2->failed_vnodes != NULL) && (reliable_job_node_find(r_input2->failed_mom_list, parent_mom) != NULL)) {
					for (j = 0; j < nelem; ++j) {
						if (add_to_vnl(&vnl_fails, noden, pkvp[j].kv_keyw, pkvp[j].kv_val) != 0) {
							goto release_nodes_exit;
						}
					}
				}

			}

			if (hasprn < 0) {
				/* matched ')' in chunk, so need to */
				/* balance the parenthesis */
				if (found_paren) {
					if (have == NULL) {
						log_err(-1, __func__, "unexpected NULL 'have' value");
						goto release_nodes_exit;
					}
					if (pbs_strcat(&have->chunkstr, &have->chunkstr_sz, ")") == NULL)
						goto release_nodes_exit;
					found_paren = 0;
				}

			}
		} else {
			log_err(-1, __func__, "parse_node_resc error");
			goto release_nodes_exit;
		}

		if (paren == 0) {
			if (k == 0) {
				have0 = have;
				have = NULL;
			} else if (add_to_resc_limit_list_sorted(&resc_limit_list, have) == 0) {
				have = NULL;
				/* already saved in list  */
			} else if (have != NULL) {
				log_err(-1, __func__, "problem saving 'have' value");
				goto release_nodes_exit;
			}
			chunk1 = parse_plus_spec_r(last1, &last1,
							&hasprn1),
			chunk2 = parse_plus_spec_r(last2, &last2,
							&hasprn2);
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
			chunkschsel = parse_plus_spec_r(lastschsel, &lastschsel,
							&hasprnschsel);
#endif
			k++;
		}
	}
	/* First chunk in the 'have' list must always be the first */
	/* entry since it pertains to the MS */

	if (have0 != NULL) {
		if (add_to_resc_limit_list_as_head(&resc_limit_list, have0) == 0) {
			have0 = NULL; /* already saved in listl  */
		}
	}

	new_exec_vnode = (char *) calloc(1, strlen(r_input->execvnode)+1);
	if (new_exec_vnode == NULL) {
		log_err(-1, __func__, "calloc error");
		goto release_nodes_exit;
	}
	new_exec_vnode[0] = '\0';

	if (r_input->exechost != NULL) {
		new_exec_host = (char *) calloc(1, strlen(r_input->exechost)+1);
		if (new_exec_host == NULL) {
			log_err(-1, __func__, "calloc error");
			goto release_nodes_exit;
		}
		new_exec_host[0] = '\0';
	}

	if (r_input->exechost2 != NULL) {
		new_exec_host2 = (char *) calloc(1, strlen(r_input->exechost2)+1);
		if (new_exec_host2 == NULL) {
			log_err(-1, __func__, "calloc error");
			goto release_nodes_exit;
		}
		new_exec_host2[0] = '\0';
	}

	if (r_input2->select_str == NULL) {
		/* not satisfying some schedselect */
		rc = 0;
		goto release_nodes_exit;
	}

	/* save vnl_good for logging later, as we now try to satisfy */
	/* select_str */
	vnl_good_master = vnl_good;
	vnl_good = NULL;

	selbuf = strdup(r_input2->select_str);
	if (selbuf == NULL) {
		log_err(-1, __func__, "strdup failed");
		goto release_nodes_exit;
	}
	resc_limit_list_print("HAVE", &resc_limit_list, PBSEVENT_DEBUG4);
	reliable_job_node_print("job failed_mom_list", r_input2->failed_mom_list, PBSEVENT_DEBUG4);
	reliable_job_node_print("job succeeded_mom_list", r_input2->succeeded_mom_list, PBSEVENT_DEBUG4);

	/* (1) parse chunk from select spec */
	psubspec = parse_plus_spec_r(selbuf, &last3, &hasprn3);
	h = 0;	/* tracks # of plus entries in select */
	l = 0;	/* tracks # of chunks in new_exec_vnode */
	while (psubspec) {
		rc = parse_chunk_r(psubspec, &snc, &snelma, &snelmt, &skv, NULL);
		/* snc = number of chunks */
		if (rc != 0)
			goto release_nodes_exit;

		for (i = 0; i < snc; ++i) {	   /* for each chunk in select.. */
			char *have_exec_vnode;

			/* clear "need" counts */
			memset(&need, 0, sizeof(need));
			resc_limit_init(&need);

			/* figure out what is "need"ed */
			for (j = 0; j < snelma; ++j) {
				if (strcmp(skv[j].kv_keyw, "ncpus") == 0)
					need.rl_ncpus = atol(skv[j].kv_val);
				else if (strcmp(skv[j].kv_keyw, "ssinodes") == 0)
					need.rl_ssi = atol(skv[j].kv_val);
				else if (strcmp(skv[j].kv_keyw, "mem") == 0)
					need.rl_mem = to_kbsize(skv[j].kv_val);
				else if (strcmp(skv[j].kv_keyw, "vmem") == 0)
					need.rl_vmem = to_kbsize(skv[j].kv_val);
				else if (strcmp(skv[j].kv_keyw, "naccelerators") == 0)
					need.rl_naccels = atol(skv[j].kv_val);
				else if (strcmp(skv[j].kv_keyw, "accelerator_memory") == 0)
					need.rl_accel_mem = to_kbsize(skv[j].kv_val);
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
				else {
					if ((rc = resc_limit_insert_other_res(&need, skv[j].kv_keyw, skv[j].kv_val, FALSE))) {
						sprintf(log_buffer, "failed to insert resource %s", skv[j].kv_keyw);
						log_err(-1, __func__, log_buffer);
						goto release_nodes_exit;
					}
				}
#endif
			}

			/* go through the list of chunk resources */
			/* we have and find a matching chunk */
			/* If none matched, then we return  */
			p_entry = (rl_entry *)GET_NEXT(resc_limit_list);
			matched  = 0; /* set to 1 if an entry is matched for current select chunk */
			k = 0;
			while (p_entry) {
				have2 = p_entry->resc;
				new_chunkstr = satisfy_chunk_need(&need, have2, &vnl_good);
				if (new_chunkstr != NULL) {
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
					append_and_group_sched_sel(new_schedselect, have2->chunkspec, tmp_chunk_spec, &tmp_chunk_ct);
#endif
					if (l > 0) {
						strcat(new_exec_vnode, "+");
						if (have2->host_chunk[0].str) {
							if (new_exec_host != NULL)
								strcat(new_exec_host, "+");
						}
						if (have2->host_chunk[1].str) {
							if (new_exec_host2 != NULL)
								strcat(new_exec_host2, "+");
						}
					}
					strcat(new_exec_vnode, new_chunkstr);
					free(have2->chunkstr);
					have2->chunkstr = NULL;

					if (have2->host_chunk[0].str) {
						if (new_exec_host != NULL)
							strcat(new_exec_host, have2->host_chunk[0].str);
						free(have2->host_chunk[0].str);
						have2->host_chunk[0].str = NULL;
					}

					if (have2->host_chunk[1].str) {
						if (new_exec_host2 != NULL)
							strcat(new_exec_host2, have2->host_chunk[1].str);
						free(have2->host_chunk[1].str);
						have2->host_chunk[1].str = NULL;
					}
					matched = 1;
					l++;
					break;
				}
				k++;
				p_entry = (rl_entry *)GET_NEXT(p_entry->rl_link);
			}
			if (matched == 0) {
				/* did not find a matching chunk */
				/* for current select chunk. */
				snprintf(log_buffer, sizeof(log_buffer),
					"could not satisfy select "
					"chunk (ncpus=%d "
					"ssi=%d "
					"mem=%lld vmem=%lld naccels=%d "
					"accel_mem=%lld)",
					need.rl_ncpus, need.rl_ssi, need.rl_mem,
					need.rl_vmem, need.rl_naccels,
						need.rl_accel_mem);
        			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
				for (pres = (resource *)GET_NEXT(need.rl_other_res);
					pres != NULL;
					pres = (resource *)GET_NEXT(pres->rs_link)) {
    				snprintf(log_buffer, sizeof(log_buffer),
    					"(%s=%s)", pres->rs_defin->rs_name, pres->rs_value.at_priv_encoded->al_value);
           			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
        		}
#endif
        		snprintf(log_buffer, sizeof(log_buffer), "NEED chunks for keep_select (%s)", (r_input2->select_str?r_input2->select_str:""));
        			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
				have_exec_vnode = return_available_vnodes(r_input->execvnode, vnl_good_master);
				snprintf(log_buffer, sizeof(log_buffer), "HAVE chunks from job's exec_vnode: %s", have_exec_vnode ? have_exec_vnode : "none");
        			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
				resc_limit_list_print("HAVE", &resc_limit_list, PBSEVENT_DEBUG3);
				reliable_job_node_print("job failed_mom_list", r_input2->failed_mom_list, PBSEVENT_DEBUG3);
				reliable_job_node_print("job succeeded_mom_list", r_input2->succeeded_mom_list, PBSEVENT_DEBUG3);
				rc = 1;
				goto release_nodes_exit;
			} else if ((h == 0) && (i == 0) && (k != 0)) {
				snprintf(log_buffer, sizeof(log_buffer),
					"could not satisfy 1st "
					"select chunk (ncpus=%d "
					"ssi=%d "
					"mem=%lld vmem=%lld naccels=%d "
					"accel_mem=%lld) "
					" with first available chunk",
					need.rl_ncpus, need.rl_ssi, need.rl_mem,
					need.rl_vmem, need.rl_naccels,
						need.rl_accel_mem);
        			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
				for (pres = (resource *)GET_NEXT(need.rl_other_res);
					pres != NULL;
					pres = (resource *)GET_NEXT(pres->rs_link)) {
					snprintf(log_buffer, sizeof(log_buffer),
						"(%s=%s)", pres->rs_defin->rs_name, pres->rs_value.at_priv_encoded->al_value);
					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
				}
#endif
				snprintf(log_buffer, sizeof(log_buffer), "NEED chunks for keep_select (%s)", (r_input2->select_str?r_input2->select_str:""));
        			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
				have_exec_vnode = return_available_vnodes(r_input->execvnode, vnl_good_master);
				snprintf(log_buffer, sizeof(log_buffer), "HAVE chunks from job's exec_vnode: %s", have_exec_vnode ? have_exec_vnode : "none");
        			log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_JOB, LOG_ERR, r_input->jobid, log_buffer);
				resc_limit_list_print("HAVE", &resc_limit_list, PBSEVENT_DEBUG3);

				reliable_job_node_print("job failed_mom_list", r_input2->failed_mom_list, PBSEVENT_DEBUG3);
				reliable_job_node_print("job succeeded_mom_list", r_input2->succeeded_mom_list, PBSEVENT_DEBUG3);
				rc = 1;
				goto release_nodes_exit;
			}
			resc_limit_free(&need);
		}

		/* do next section of select */
		psubspec = parse_plus_spec_r(last3, &last3, &hasprn3);
		h++;
	}

	if (strcmp(new_exec_vnode, r_input->execvnode) == 0) {
		/* no change, don't bother setting the new_* return values */
		rc = 0;
		goto release_nodes_exit;
	}

#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
	append_and_group_sched_sel(new_schedselect, "", tmp_chunk_spec, &tmp_chunk_ct);
	rc = do_schedselect(new_schedselect, NULL, NULL, NULL, &tmpstr);
	free(new_schedselect);
#else
	rc = do_schedselect(r_input2->select_str, NULL, NULL, NULL, &tmpstr);
#endif
	if (rc != 0) {
		rc = 1;
		goto release_nodes_exit;
	}
	new_schedselect = strdup(tmpstr);
	if (new_schedselect == NULL) {
		log_err(errno, __func__, msg_err_malloc);
		rc = 1;
		goto release_nodes_exit;
	}

	rc = 0;
release_nodes_exit:
	free(exec_vnode);
	free(exec_host);
	free(exec_host2);
#if !(defined(PBS_MOM) || defined(PBS_PYTHON))
	free(sched_select);
	free(res_in_exec_vnode);
	if (tmp_chunk_spec)
		free(tmp_chunk_spec);
#endif
	free(chunk_buf);
	resc_limit_list_free(&resc_limit_list);
	resc_limit_free(have);
	free(have);
	resc_limit_free(&need);
	resc_limit_free(have0);
	free(have0);
	free(selbuf);
	vnl_free(vnl_good_master);

	if ((rc != 0) || (strcmp(r_input->execvnode, new_exec_vnode) == 0)) {
		/* error or if there was no change */
		free(new_exec_vnode);
		free(new_exec_host);
		free(new_exec_host2);
		free(new_schedselect);
		vnl_free(vnl_fails);
		vnl_free(vnl_good);
	} else if (r_input2->select_str == NULL) {
		if (r_input2->failed_vnodes != NULL) {
			*(r_input2->failed_vnodes) = vnl_fails;
		} else {
			vnl_free(vnl_fails);
		}

		if (r_input2->good_vnodes != NULL) {
			*(r_input2->good_vnodes) = vnl_good;
		} else {
			vnl_free(vnl_good);
		}
		free(new_exec_vnode);
		free(new_exec_host);
		free(new_exec_host2);
		free(new_schedselect);

	} else {
		if (r_input2->failed_vnodes != NULL) {
			*(r_input2->failed_vnodes) = vnl_fails;
		} else {
			vnl_free(vnl_fails);
		}

		if (r_input2->good_vnodes != NULL) {
			*(r_input2->good_vnodes) = vnl_good;
		} else {
			vnl_free(vnl_good);
		}
		if (r_input->p_new_exec_vnode != NULL)
			*(r_input->p_new_exec_vnode) = new_exec_vnode;
		if ((r_input->p_new_exec_host[0] != NULL) && (new_exec_host != NULL))
			*(r_input->p_new_exec_host[0]) = new_exec_host;
		if ((r_input->p_new_exec_host[1] != NULL) && (new_exec_host2 != NULL))
			*(r_input->p_new_exec_host[1]) = new_exec_host2;
		if (r_input->p_new_schedselect != NULL)
			*(r_input->p_new_schedselect) = new_schedselect;
	}

	return (rc);
}

/**
 * @brief
 *		strcat_grow
 *
 * @par Functionality:
 *		If the buffer, buf, whose size is lenbuf is too small to cat source,
 *		increase the size of buf by the length of "source" plus an extra
 *		PBS_STRCAT_GROW_INCR bytes.
 *		Makes sure there is at least PBS_STRCAT_GROW_MIN free bytes
 *		in "buff" for those simple one or two byte direct additions..
 *		Assumes both current string in buf and source are null terminated.
 *
 * @param[in]	buf    -	pointer to the address of buffer, may be updated.
 * @param[in] 	curr   -	current point to which source string will be
 *							concatenated.  This is within the current string or the end
 *							of the current string in "buff", may have data after
 *							"curr" in the buffer.
 * @param[in]	lenbuf -	current size of buf, may be updated.
 * @param[in]	source - 	string which is to be concatenated to "curr".
 *
 * @return	int
 * @retval	 0	: success
 * @retval	-1	: realloc failure, out of memory
 *
 * @par Side-effect:	If buffer is increased in size, "buf", "curr" and "lenbuf"
 *						are updated.
 *
 * @par MT-safe:	No
 *
 * @par	Future extension	- This function is currently designed as a drop in
 *	for make_schedselect().  It could be simplified for more general use
 *	by removing the use of "curr".
 */

#define PBS_STRCAT_GROW_MIN  16
#define PBS_STRCAT_GROW_INCR 512
static int
strcat_grow(char **buf, char **curr, size_t *lenbuf, char *source)
{

	size_t  add;
	size_t  currsize;
	ssize_t delta;
	if ((lenbuf == NULL) || (curr == NULL) || (buf == NULL) || (source == NULL))
		return -1;

	currsize = *lenbuf;
	delta = *curr - *buf;	/* offset in buffer */
	add = strlen(source);
	if ((delta + strlen(*curr) + add + PBS_STRCAT_GROW_MIN) >= currsize) {
		/* need to grow buffer */
		char   *newbuf;
		size_t  newlen;

		newlen = currsize + add + PBS_STRCAT_GROW_INCR;

		newbuf = realloc((void *)*buf, newlen);
		if (newbuf) {
			*buf    = newbuf;
			*curr   = newbuf + delta;
			*lenbuf = newlen;
		} else {
			return -1;	/* error */
		}
	}
	(void)strcat(*curr, source);
	return 0;
}
/*
 *
 * @note
 *	The return value *p_sched_select is in a static dynamic memory that
 *	will get overwritten in the next call.
 */
/**
 * @par
 * 		Decode a selection specification, and produce the
 *		the "schedselect" attribute which contains any default resources
 *		missing from the chunks in the select spec.
 *		Also translates the value of any boolean resource to the "formal"
 *		value of "True" or "False" for the Scheduler who needs to know it
 *		is a boolean and not a string or number.
 *
 *	@param[in]	select_val -	the select specification being decoded
 * 	@param[in]	server -	used to obtain server defaults
 * 	@param[in]	destin -	used to obtain queue defaults
 *	@param[out]	presc_in_err -	error information filled in here
 *	@param[out]	p_schedselect -	the resulting schedselect value.
 *
 *	@return	int
 *	@retval	0	: success
 *	@retval	PBSE_Error	: Error Code.
 *
 *	@par MT-safe:	No.
 */
int
do_schedselect(char *select_val, void *server, void *destin, char **presc_in_err, char **p_sched_select)
{
	char        *chunk;
	int	     i;
	int	     firstchunk;
	size_t	     len;
	int 	     nchk;
	int          already_set = 0;
	int 	     nchunk_internally_set;
	int	     nelem;
	static char *outbuf   = NULL;
	struct key_value_pair *pkvp;
	struct key_value_pair *qdkvp;
	int		       qndft;
	struct key_value_pair *sdkvp;
	int		       sndft;
	char		      *quotec;
	resource_def *presc;
	char 	    *pc;
	int	     rc;
	char	    *tb;
	int	     validate_resource_exist = 0;
	static size_t bufsz = 0;
	struct server *pserver = NULL;
	pbs_queue   *pque = NULL;

	if ((select_val == NULL) || (p_sched_select == NULL)) {
		return (PBSE_SYSTEM);
	}

	pserver = server;
	pque = destin;


	/* allocate or realloc bigger the out buffer for parsing */
	if ((len = (strlen(select_val) + 100)) >= (bufsz >> 1)) {
		len = (2 * len) + 500 + bufsz;
		if (bufsz) {
			tb = (char *)realloc(outbuf, len);
			if (tb == NULL)
				return PBSE_SYSTEM;
			outbuf = tb;
		} else {
			outbuf = (char *)malloc(len);
			if (outbuf == NULL)
				return PBSE_SYSTEM;
		}
		bufsz = len;
	}

	if (pque == NULL || pque->qu_qs.qu_type == QTYPE_Execution)
		validate_resource_exist = 1;

	*outbuf = '\0';
	/* copy input, the string will be broken during parsing */
	firstchunk = 1;
	chunk = parse_plus_spec(select_val, &rc); /* break '+' separated substrings */
	if (rc != 0)
		return rc;
	while (chunk) {
		if (firstchunk)
			firstchunk = 0;
		else
			strcat(outbuf, "+");

		if (parse_chunk(chunk, &nchk, &nelem, &pkvp, &nchunk_internally_set) == 0)
		{
			int j;

			/* first check for any invalid resources in the select */
			for (j=0; j<nelem; ++j) {

				/* see if resource is repeated within the chunk - an err */
				for (i=0; i<j; ++i) {
					if (strcmp(pkvp[j].kv_keyw, pkvp[i].kv_keyw) == 0) {
						if (presc_in_err != NULL) {
							if ((*presc_in_err = strdup(pkvp[j].kv_keyw)) == NULL)
								return PBSE_SYSTEM;
						}
						return PBSE_DUPRESC;
					}
				}
				presc = find_resc_def(svr_resc_def, pkvp[j].kv_keyw);
				if (presc) {
					if ((presc->rs_flags & ATR_DFLAG_CVTSLT) == 0) {
						if (presc_in_err != NULL) {
							if ((*presc_in_err = strdup(pkvp[j].kv_keyw)) == NULL)
								return PBSE_SYSTEM;
						}
						return PBSE_INVALSELECTRESC;
					}
				} else if (validate_resource_exist) {
					if (presc_in_err != NULL) {
						if ((*presc_in_err = strdup(pkvp[j].kv_keyw)) == NULL)
							return PBSE_SYSTEM;
					}
					return PBSE_UNKRESC;
				}
			}

			pc = outbuf + strlen(outbuf);

			/* add in any defaults, first from the queue,... */
			/* then add in any defaults from the server */

			if (pque) {
				qndft = pque->qu_nseldft;
				qdkvp = pque->qu_seldft;
				rc = parse_chunk_make_room(nelem, qndft, &pkvp);
				if (rc)
					return rc;
				for (i=0; i<qndft; ++i) {
					for (j=0; j<nelem; ++j) {
						if (strcasecmp(qdkvp[i].kv_keyw, pkvp[j].kv_keyw) == 0)
							break;
					}
					if (j == nelem) {
						/* check to see if the value is "nchunk" */
						/* If nchunk_internally_set is set, then */
						/* the user did not specify a chunk size in the */
						/* select line.  Set nchk to the "nchunk" value  */
						if (strcasecmp(qdkvp[i].kv_keyw, "nchunk") == 0) {
							if (nchunk_internally_set) {
								nchk = atoi(qdkvp[i].kv_val);
								already_set = 1;
							}
						} else {
							/* Add in the defaults from the Queue */
							pkvp[nelem].kv_keyw  = qdkvp[i].kv_keyw;
							pkvp[nelem++].kv_val = qdkvp[i].kv_val;
						}
					}
				}
			}

			if (pserver != NULL) {
				sndft = pserver->sv_nseldft;
				sdkvp = pserver->sv_seldft;
				rc = parse_chunk_make_room(nelem, sndft, &pkvp);
				if (rc)
					return rc;
			} else {
				sndft = 0;
				sdkvp = NULL;
			}
			for (i=0; i<sndft; ++i) {
				for (j=0; j<nelem; ++j) {
					if (strcasecmp(sdkvp[i].kv_keyw, pkvp[j].kv_keyw) == 0)
						break;
				}
				if (j == nelem) {
					/* check to see if the value is "nchunk" */
					/* If nchunk_internally_set is set, then    */
					/* the user did not specify a chunk size in the */
					/* select line, so set nchk to the "nchunk" value  */
					if (strcasecmp(sdkvp[i].kv_keyw, "nchunk") == 0) {
						if (nchunk_internally_set && (!already_set))
							nchk = atoi(sdkvp[i].kv_val);
					} else {
						/* Add in the defaults from the Server */
						pkvp[nelem].kv_keyw  = sdkvp[i].kv_keyw;
						pkvp[nelem++].kv_val = sdkvp[i].kv_val;
					}
				}
			}
			sprintf(pc, "%d", nchk);
			if (nelem > 0) {
				/*
				 * if the resource is known to be of type boolean, then
				 * replace its value with exactly "True" or "False" as
				 * appropriate for the Scheduler.  Then rebuild it in
				 * the out buf.
				 */
				presc = find_resc_def(svr_resc_def, pkvp[0].kv_keyw);
				for (i=0; i<nelem; ++i) {
					strcat(pc, ":");
					if (strcat_grow(&outbuf, &pc, &bufsz, pkvp[i].kv_keyw) == -1)
						return PBSE_SYSTEM;
					strcat(pc, "=");
					presc = find_resc_def(svr_resc_def, pkvp[i].kv_keyw);
					if (presc && (presc->rs_type == ATR_TYPE_BOOL)) {
						j = is_true_or_false(pkvp[i].kv_val);
						if (j == 1)
							strcat(pc, ATR_TRUE);
						else if (j == 0)
							strcat(pc, ATR_FALSE);
						else
							return PBSE_BADATVAL;

					} else {
						if (presc && (presc->rs_type == ATR_TYPE_SIZE)) {
							if (strcat_grow(&outbuf, &pc, &bufsz, pkvp[i].kv_val) == -1)
								return PBSE_SYSTEM;
							tb = pkvp[i].kv_val+strlen(pkvp[i].kv_val) - 1;
							if (*tb != 'b' && *tb != 'w' &&
								*tb != 'B' && *tb != 'W')
								strcat(pc, "b");
						} else if (presc &&
							((presc->rs_type == ATR_TYPE_STR) ||
							(presc->rs_type == ATR_TYPE_ARST))) {
							if (strpbrk(pkvp[i].kv_val, "\"'+:=()")) {
								if (strchr(pkvp[i].kv_val, (int)'"'))
									quotec = "'";
								else
									quotec = "\"";
								strcat(pc, quotec);
								if (strcat_grow(&outbuf, &pc, &bufsz, pkvp[i].kv_val) == -1)
									return PBSE_SYSTEM;
								strcat(pc, quotec);
							} else {
								if (strcat_grow(&outbuf, &pc, &bufsz, pkvp[i].kv_val) == -1)
									return PBSE_SYSTEM;
							}

						} else {
							if (strcat_grow(&outbuf, &pc, &bufsz, pkvp[i].kv_val) == -1)
								return PBSE_SYSTEM;
						}
					}
				}
			}
			else
				return (PBSE_INVALSELECTRESC);

		} else {
			if (presc_in_err != NULL) {
				if ((*presc_in_err = strdup(chunk)) == NULL)
					return PBSE_SYSTEM;
			}
			return (PBSE_UNKRESC);
		}
		chunk = parse_plus_spec(NULL, &rc);
		if (rc != 0)
			return (rc);
	}

	*p_sched_select = outbuf;
	return 0;
}
