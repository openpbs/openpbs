/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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

/**
 * @file    vnparse.c
 *
 *@brief
 * 		vnparse.c - Functions which provide basic operation on the parsing of vnl files.
 *
 * Included functions are:
 *
 *   vn_parse	opening and reading the given file and parsing it into a vnl_t
 *   vn_parse_stream	Read a configuration file.
 *   vn_merge	Merge data from the newly-parse vnode list (new) into a previously-parsed one (cur)
 *   vn_merge2	Merge data from the newly-parse vnode list (new) into a previously-parsed one (cur)
 *   attr_exist	Search for an attribute in a vnode.
 *   vn_vnode	Check if a vnode exists.
 *   vn_exist	Search for a named vnode, then search for an attribute in that vnode.
 *   vn_addvnr	Add the given attribute (attr) and value (attrval) to the vnode with ID id;
 *   id2vnrl	If a vnal_t entry with the given ID (id) exists, return a pointer to it;
 *   attr2vnr	If a vna_t entry with the given ID attribute (attr), return a pointer to it;
 *   vnl_free	free the vnl_t
 *   legal_vnode_char	Check character in a vnode name.
 *   parse_node_token	Parse tokens in the nodes file
 *   vnl_alloc	Handle initial allocation of a vnl_t as well as reallocation when we run out of space.
 *   vnal_alloc	Handle initial allocation of a vnal_t as well as reallocation when we run out of space.
 */
#include	<sys/types.h>
#include	<sys/stat.h>
#include	<assert.h>
#include	<ctype.h>
#include	<errno.h>
#include	<stdio.h>
#include	<string.h>
#include	<stdlib.h>
#ifndef WIN32
#include	<unistd.h>
#endif
#include	<time.h>
#include	"dis.h"
#include	"pbs_error.h"
#include	"log.h"
#include	"placementsets.h"
#ifdef	WIN32
#include	"pbs_config.h"
#endif
#include	"list_link.h"
#include	"attribute.h"
#include	"pbs_nodes.h"
#include	"cmds.h"

#ifdef PBS_MOM
static vnal_t	*vnal_alloc(vnal_t **);
static vnal_t	*id2vnrl(vnl_t *, char *, AVL_IX_REC *);
static vna_t	*attr2vnr(vnal_t *, char *);

static const char	iddelim = ':';
static const char	attrdelim = '=';

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
			sprintf(log_buffer,
				"invalid character in vnode name \"%s\"", vnid);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			vnl_free(vnlp);
			return NULL;
		}
		/* Condition to make sure that vnode name should not exceed
		 * PBS_MAXHOSTNAME i.e. 64 characters. This is because the
		 * corresponding column nd_name in the database table pbs.node
		 * is defined as string of length 64.
		 */
		if (strlen(vnid) > PBS_MAXHOSTNAME) {
			sprintf(log_buffer,
				"Node name \"%s\" is too big", vnid);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
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
 *		names listed in the space-separated 'allow_attribs'.
 *		This overwrites any duplicate attributes with new's values.
 * @note
 *		An entry in 'new' will be matched just before a dot (.) in the name
 *		if one exists.
 *		For example, a 'new' entry of "resources_available.ncpus" will
 *		match with 'allow_attribs' entry of "resources_available".
 *
 * @param[in]	cur - previously parsed vnode list
 * @param[in]	new - newly parsed vnode list
 * @param[in]	allow_attribs - space-separated list of attribute names to
 * 				to match.
 * @return	vnl_t *
 * @retval	cur	- if successful
 * @retval	NULL	- if not successful.
 */
vnl_t *
vn_merge2(vnl_t *cur, vnl_t *new, char *allow_attribs, callfunc_t callback)
{
	unsigned long	i, j;
	char		*vna_name, *dot;
	int		match;

	for (i = 0; i < new->vnl_used; i++) {
		vnal_t	*newreslist = VNL_NODENUM(new, i);

		for (j = 0; j < newreslist->vnal_used; j++) {
			vna_t	*newres = VNAL_NODENUM(newreslist, j);

			vna_name = newres->vna_name;
			dot=strchr(vna_name, (int)'.');
			if (dot)
				*dot = '\0';

			/* match up to but not including dot */
			match = in_string_list(vna_name, ' ', allow_attribs);
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

	cur->vnl_modtime = (cur->vnl_modtime > new->vnl_modtime) ?
		cur->vnl_modtime : new->vnl_modtime;
	return (cur);
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
	return id2vnrl(vnlp, id, NULL);
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
	if ((vnrlp = id2vnrl(vnlp, id, NULL)) == NULL)
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
	union {
		AVL_IX_REC xrp;
		char	buf[PBS_MAXHOSTNAME + sizeof(AVL_IX_REC) + 1];
	} xxrp;
	AVL_IX_REC *rp = &xxrp.xrp;

	if ((callback != NULL) && (callback(id, attr, attrval) == 0))
		return (0);

	if ((newname = strdup(attr)) == NULL) {
		return (-1);
	} else if ((newval = strdup(attrval)) == NULL) {
		free(newname);
		return (-1);
	}

	/* the index was created with string keys */
	snprintf(rp->key, PBS_MAXHOSTNAME, "%s", id);
	if ((vnrlp = id2vnrl(vnlp, id, rp)) == NULL) {
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
		rp->recptr = (AVL_RECPOS)vnlp->vnl_dl.dl_cur;
		if (avl_add_key(rp, &vnlp->vnl_ix) != AVL_IX_OK) {
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
 * @param[out]	rp	-	rectype
 *
 * @return	vnal_t *
 * @retval	a pointer to vnal_t	: entry with the given ID (id) exists
 * @retval	NULL	: does not exists.
 */
static vnal_t *
id2vnrl(vnl_t *vnlp, char *id, AVL_IX_REC *rp)
{
	union {
		AVL_IX_REC xrp;
		char	buf[PBS_MAXHOSTNAME + sizeof(AVL_IX_REC) + 1];
	} xxrp;

	if (rp == NULL) {
		rp = &xxrp.xrp;
		snprintf(rp->key, PBS_MAXHOSTNAME, "%s", id);
	}

	if (vnlp != NULL && avl_find_key(rp, &vnlp->vnl_ix) == AVL_IX_OK) {
		unsigned long	i = (unsigned long)rp->recptr;
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
#endif /* PBS_MOM */
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
		for (i = 0; i < vnlp->vnl_used; i++) {
			vnal_t	*vnrlp = VNL_NODENUM(vnlp, i);

			assert(vnrlp->vnal_list != NULL);
			for (j = 0; j < vnrlp->vnal_used; j++) {
				vna_t	*vnrp = VNAL_NODENUM(vnrlp, j);

				free(vnrp->vna_name);
				free(vnrp->vna_val);
			}
			free(vnrlp->vnal_list);
			free(vnrlp->vnal_id);
		}
		free(vnlp->vnl_list);
#ifdef PBS_MOM
		avl_destroy_index(&vnlp->vnl_ix);
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

#ifdef PBS_MOM

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
		/*
		 * The keylength 0 means use nul terminated strings for keys.
		 */
		avl_create_index(&newchunk->vnl_ix, AVL_NO_DUP_KEYS, 0);
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
#endif /* PBS_MOM */
