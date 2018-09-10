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
 * @file	mom_vnode.c
 */
#include	<sys/types.h>
#include	<assert.h>
#include	<errno.h>
#include	<stdio.h>
#include	<unistd.h>
#include	<limits.h>
#include	"pbs_config.h"
#include	"pbs_internal.h"
#include	"libpbs.h"
#include	"log.h"
#include	"server_limits.h"
#include	"attribute.h"
#include	"placementsets.h"
#include	"resource.h"
#include	"pbs_nodes.h"
#include	"mom_mach.h"
#include	"mom_vnode.h"
#include	"libutil.h"
#include	"hook_func.h"
#if	defined(MOM_CPUSET) && (CPUSET_VERSION >= 4)
#include	<resmon.h>
#include	<bitmask.h>
#endif	/* MOM_CPUSET && CPUSET_VERSION >= 4 */

#ifndef	_POSIX_ARG_MAX
#define	_POSIX_ARG_MAX	4096	/* largest value standards guarantee */
#endif

extern char		mom_host[];
extern unsigned int	pbs_mom_port;
extern unsigned int	pbs_rm_port;
extern vnl_t		*vnlp;					/* vnode list */
#if	defined(MOM_CPUSET)
extern int		do_memreserved_adjustment;
#if	(CPUSET_VERSION >= 4)
static struct bitmask	*cpu_mask = NULL;
static struct bitmask	*mem_mask = NULL;
#endif	/* CPUSET_VERSION >= 4 */
#endif	/* MOM_CPUSET */

static void		*cpuctx;
static AVL_IX_REC	*pe;
static void		cpu_inuse(unsigned int, job *, int);
static void		*new_ctx(void);
static mom_vninfo_t	*new_vnid(const char *, void *);
static void		truncate_and_log(const char *, char *, int);
static mom_vninfo_t	*vnid2mominfo(const char *, const void *);
#if	defined(MOM_CPUSET) && (CPUSET_VERSION >= 4)
static long		execmax = _POSIX_ARG_MAX;

static int		cpumask_add(unsigned int);
static int		memmask_add(unsigned int);
#endif	/* MOM_CPUSET && CPUSET_VERSION >= 4 */

enum res_op	{ RES_DECR, RES_INCR, RES_SET };

/**
 * @brief
 *	Log debugging information pertaining to each CPU that we are managing.
 *	Each CPU may be in one of three states:  free for use, in use by a job,
 *	or in use but not assigned to a job (the last of these is used for CPUs
 *	declared unusable by cpunum_outofservice()).
 *
 * @return Void
 *
 */
void
mom_CPUs_report(void)
{
	AVL_IX_DESC	*pix;
	int		ret;
	char		reportbuf[LOG_BUF_SIZE];
	int		bufspace;	/* space remaining in reportbuf[] */

	if ((pix = cpuctx) != NULL) {
		char	*p;

		avl_first_key(pix);

		if (pe == NULL) {
			pe = malloc(sizeof(AVL_IX_REC) + PBS_MAXNODENAME + 1);
			if (pe == NULL) {
				log_err(errno, __func__, "malloc pe failed");
				return;
			}
		}
		while ((ret = avl_next_key(pe, pix)) == AVL_IX_OK) {
			unsigned int	i;
			int		first;
			mominfo_t	*mip;
			mom_vninfo_t	*mvp;

			mip = (mominfo_t *) pe->recptr;
			assert(mip != NULL);
			assert(mip->mi_data != NULL);

			mvp = (mom_vninfo_t *) mip->mi_data;
			p = reportbuf;
			bufspace = sizeof(reportbuf);
			ret = snprintf(p, bufspace, "%s:  cpus = ", mvp->mvi_id);
			if (ret >= bufspace) {
				truncate_and_log(__func__, reportbuf,
					sizeof(reportbuf));
				continue;
			}
			p += ret, bufspace -= ret;
			for (i = 0, first = 1; i < mvp->mvi_ncpus; i++) {
				if (first) {
					first = 0;
				} else {
					if (bufspace < 1) {
						truncate_and_log(__func__, reportbuf,
							sizeof(reportbuf));
						goto line_done;
					}
					sprintf(p, ",");
					p++, bufspace--;
				}

				ret = snprintf(p, bufspace, "%d",
					mvp->mvi_cpulist[i].mvic_cpunum);
				if (ret >= bufspace) {
					truncate_and_log(__func__, reportbuf,
						sizeof(reportbuf));
					goto line_done;
				}
				p += ret, bufspace -= ret;

				if (MVIC_CPUISFREE(mvp, i))
					ret = snprintf(p, bufspace, " (free)");
				else {
					if (mvp->mvi_cpulist[i].mvic_job == NULL)
						ret = snprintf(p, bufspace,
							" (inuse, no job)");
					else
						ret = snprintf(p, bufspace,
							" (inuse, job %s)",
							mvp->mvi_cpulist[i].mvic_job->ji_qs.ji_jobid);
				}
				if (ret >= bufspace) {
					truncate_and_log(__func__, reportbuf,
						sizeof(reportbuf));
					goto line_done;
				}
				p += ret, bufspace -= ret;
			}
			log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, reportbuf);
line_done:
			;
		}

		assert(ret == AVL_EOIX);
	}
}

/**
 * @brief
 *	In case of buffer overflow, we log what we can and indicate with an
 *	ellipsis at the end that the line overflowed.
 *
 * @param[in] id - id for log msg
 * @param[in] buf - buffer holding log msg
 * @param[in] bufsize - buffer size
 *
 * @return Void
 *
 */
static void
truncate_and_log(const char *id, char *buf, int bufsize)
{
	buf[bufsize - 4] = buf[bufsize - 3] = buf[bufsize - 2] = '.';
	buf[bufsize - 1] = '\0';
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, id, buf);
}

/**
 * @brief
 *	Log debugging information containing a description of the vnode list
 *	in 'vnl'.
 *	(a rather complicated structure described in "placementsets.h").
 *
 * @param[in]	vnl  - vnode list we're interested in
 * @param[in] 	header - heading of the log message
 *
 * @return void
 *
 */
void
mom_vnlp_report(vnl_t *vnl, char *header)
{
	int		i;
	char		reportbuf[LOG_BUF_SIZE+1];
	char		*p = NULL;
	vnl_t		*vp;
	char		attrprefix[] = ", attrs[]:  ";
	int		bytes_left;

	if (vnl == NULL)
		return;

	vp = vnl;

	for (i = 0; i < vp->vnl_used; i++) {
		vnal_t	*vnalp;
		int j, k;

		vnalp = VNL_NODENUM(vp, i);
		bytes_left = LOG_BUF_SIZE;
		p = reportbuf;
		k = snprintf(p, bytes_left, "vnode %s:  nelem %lu", vnalp->vnal_id,
			vnalp->vnal_used);
		if (k < 0)
			break;
		bytes_left -= k;
		if (bytes_left <= 0)
			break;
		p += k;
		if (vnalp->vnal_used > 0) {
			k = snprintf(p, bytes_left, "%s", attrprefix);
			if (k < 0)
				break;
			bytes_left -= k;
			if (bytes_left <= 0)
				break;
			p += k;
		}
		for (j = 0; j < vnalp->vnal_used; j++) {
			vna_t		*vnap;

			vnap = VNAL_NODENUM(vnalp, j);
			if (j > 0) {
				snprintf(p, bytes_left, ", ");
				bytes_left -= 2;
				if (bytes_left <= 0)
					break;
				p += 2;
			}
			k = snprintf(p, bytes_left, "\"%s\" = \"%s\"", vnap->vna_name,
				vnap->vna_val);
			if (k < 0)
				break;
			bytes_left -= k;
			if (bytes_left <= 0)
				break;
			p += k;
		}
		log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, header?header:__func__, reportbuf);
		p = NULL;
	}
	if (p != NULL) { /* log any remaining item */
		log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, header?header:__func__, reportbuf);
	}
}

/**
 * @brief
 *	Add a range of CPUs (an element of the form M or M-N where M and N are
 *	nonnegative integers) to the given mvi.  If any CPUs are already present
 *	in mvp->mvi_cpulist[], they are preserved and their state is unchanged.
 *
 * @param[in] mvp - pointer to mom_vninfo_t
 * @param[in] cpurange - cpu range
 *
 * @return Void
 *
 */
static void
add_CPUrange(mom_vninfo_t *mvp, char *cpurange)
{
	char		*p;
	unsigned int	from, to;
	unsigned int	cpunum;
	unsigned int	i, ncpus;
	static int	chunknum = 0;

	if ((p = strchr(cpurange, '-')) != NULL) {

		*p = '\0';
		from = strtoul(cpurange, NULL, 0);
		to = strtoul(p + 1, NULL, 0);
		if (from > to) {
			sprintf(log_buffer, "chunk %d:  lhs (%u) > rhs (%u)",
				chunknum, from, to);
			log_err(PBSE_SYSTEM, __func__, log_buffer);
			return;
		}
	} else {
		from = to = strtoul(cpurange, NULL, 0);
		chunknum++;
	}

	for (cpunum = from, ncpus = mvp->mvi_ncpus; cpunum <= to; cpunum++) {
#ifdef	DEBUG
		/*
		 *	It's not obvious in reading the code that when we get
		 *	to the "for" loop below, mvp->mvi_cpulist is non-NULL.
		 *	It happens because the first time we add any CPUs to
		 *	this vnode's CPU list, ncpus will be 0 and we do a
		 *	realloc(NULL, ...) to allocate the initial storage.
		 */
		if (ncpus > 0)
			assert(mvp->mvi_cpulist != NULL);
#endif	/* DEBUG */
		for (i = 0; i < ncpus; i++)
			if (cpunum == mvp->mvi_cpulist[i].mvic_cpunum)
				break;

		if (i >= ncpus) {	/* CPU cpunum not in mvi_cpulist[] */
			mom_mvic_t	*l;

			l = realloc(mvp->mvi_cpulist,
				(ncpus + 1) * sizeof(mom_mvic_t));
			if (l == NULL) {
				log_err(errno, __func__, "malloc failure");
				return;
			} else
				mvp->mvi_cpulist = l;
			mvp->mvi_cpulist[ncpus].mvic_cpunum = cpunum;
			cpuindex_free(mvp, ncpus);
			mvp->mvi_ncpus++;
			mvp->mvi_acpus++;
			ncpus = mvp->mvi_ncpus;
#if	defined(MOM_CPUSET) && (CPUSET_VERSION >= 4)
			if (cpumask_add(cpunum) != 0)
				return;
#endif	/* MOM_CPUSET && CPUSET_VERSION >= 4 */
		}
	}
}

/**
 * @brief
 *	cpuindex_free() and cpuindex_inuse() are ``context-sensitive'' functions
 *	that mark as free or busy a CPU which is referred to by an index that is
 *	relative to the vnode to which it's attached.  That is, physical CPU 17
 *	may be referred to as index 3 relative to vnode "foo".
 *
 * @param[in] mvp - pointer to mom_vninfo_t structure
 * @param[in] cpuindex - cpu index
 *
 * @return Void
 *
 */
void
cpuindex_free(mom_vninfo_t *mvp, unsigned int cpuindex)
{
	char		buf[BUFSIZ];

	assert(mvp != NULL);
	assert(cpuindex <= mvp->mvi_ncpus);
	sprintf(buf, "vnode %s:  mark CPU %u free", mvp->mvi_id,
		mvp->mvi_cpulist[cpuindex].mvic_cpunum);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, buf);

	mvp->mvi_cpulist[cpuindex].mvic_flags = MVIC_FREE;
	mvp->mvi_cpulist[cpuindex].mvic_job = NULL;
}

/**
 * @brief
 *      cpuindex_free() and cpuindex_inuse() are ``context-sensitive'' functions
 *      that mark as free or busy a CPU which is referred to by an index that is
 *      relative to the vnode to which it's attached.  That is, physical CPU 17
 *      may be referred to as index 3 relative to vnode "foo".
 *
 * @param[in] mvp - pointer to mom_vninfo_t structure
 * @param[in] cpuindex - cpu index
 * @param[in] pjob - pointer to job structure
 *
 * @return Void
 *
 */
void
cpuindex_inuse(mom_vninfo_t *mvp, unsigned int cpuindex, job *pjob)
{
	char		buf[BUFSIZ];

	assert(mvp != NULL);
	assert(cpuindex <= mvp->mvi_ncpus);
	if (pjob == NULL) {
		sprintf(buf, "vnode %s:  mark CPU %u inuse", mvp->mvi_id,
			mvp->mvi_cpulist[cpuindex].mvic_cpunum);
	} else {
		sprintf(buf, "vnode %s:  mark CPU %u inuse by job %s",
			mvp->mvi_id, mvp->mvi_cpulist[cpuindex].mvic_cpunum,
			pjob->ji_qs.ji_jobid);
	}
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, buf);

	mvp->mvi_cpulist[cpuindex].mvic_flags = MVIC_ASSIGNED;
	mvp->mvi_cpulist[cpuindex].mvic_job = pjob;
}

#if	defined(MOM_CPUSET)
/**
 * @brief
 *	cpunum_free() is a context-free function to mark a CPU as available.
 *	It must previously have been marked as inuse via cpuindex_inuse().
 *	This function is used to recover from failure of make_cpuset().
 *
 * @param[in] cpunum - number of cpu
 *
 * @return Void
 *
 */
void
cpunum_free(unsigned int cpunum)
{
	AVL_IX_DESC	*pix;
	int		ret;
	char		buf[BUFSIZ];

	sprintf(buf, "mark CPU %u free", cpunum);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, buf);

	if ((pix = cpuctx) != NULL) {
		avl_first_key(pix);

		if (pe == NULL) {
			pe = malloc(sizeof(AVL_IX_REC) + PBS_MAXNODENAME + 1);
			if (pe == NULL) {
				log_err(errno, __func__, "malloc pe failed");
				return;
			}
		}
		while ((ret = avl_next_key(pe, pix)) == AVL_IX_OK) {
			unsigned int	i;
			mominfo_t	*mip;
			mom_vninfo_t	*mvp;

			mip = (mominfo_t *) pe->recptr;
			assert(mip != NULL);
			assert(mip->mi_data != NULL);

			mvp = (mom_vninfo_t *) mip->mi_data;
			for (i = 0; i < mvp->mvi_ncpus; i++)
				if (mvp->mvi_cpulist[i].mvic_cpunum == cpunum) {
					cpuindex_free(mvp, i);
					return;
				}
		}

		assert(ret == AVL_EOIX);

		sprintf(log_buffer, "CPU %u not found in cpuctx", cpunum);
		log_err(PBSE_SYSTEM, __func__, log_buffer);
	}
}

/**
 * @brief
 *	cpunum_inuse() is a ``context-free'' function that marks a CPU
 *	(which is referred to by its physical CPU number) as being in use.
 *	It must be called with a non-NULL job pointer.
 *
 * @param[in] cpunum - number of cpu
 * @param[in] pjob - pointer to job structure
 *
 * @return Void
 *
 */
void
cpunum_inuse(unsigned int cpunum, job *pjob)
{
	assert(pjob != NULL);
	cpu_inuse(cpunum, pjob, 0);
}
#endif	/* MOM_CPUSET */

/**
 * @brief
 *	Find the vnode with ID vnid and adjust (decrement, increment, or set)
 *	the value of resource res by the amount adjval
 *
 * @param[in] vp - pointer to vnl_t structure
 * @param[in] vnid - vnode id
 * @param[in] res - resource name
 * @param[in] op - enum for resource option
 *
 * @return Void
 *
 */
static void
resadj(vnl_t *vp, const char *vnid, const char *res, enum res_op op,
	unsigned int adjval)
{
	int		i, j;

	sprintf(log_buffer, "vnode %s, resource %s, res_op %d, adjval %u",
		vnid, res, (int) op, adjval);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, log_buffer);
	for (i = 0; i < vp->vnl_used; i++) {
		vnal_t	*vnalp;

		vnalp = VNL_NODENUM(vp, i);
		if (strcmp(vnalp->vnal_id, vnid) != 0)
			continue;
		for (j = 0; j < vnalp->vnal_used; j++) {
			vna_t *vnap;

			vnap = VNAL_NODENUM(vnalp, j);
			if (strcmp(vnap->vna_name, res) == 0) {
				unsigned int resval;
				char valbuf[BUFSIZ];

				resval = strtoul(vnap->vna_val, NULL, 0);
				switch ((int) op) {
					case RES_DECR:
						resval -= adjval;
						break;
					case RES_INCR:
						resval += adjval;
						break;
					case RES_SET:
						resval = adjval;
						break;
					default:
						sprintf(log_buffer, "unknown res_op %d",
							(int) op);
						log_event(PBSEVENT_ERROR, 0, LOG_ERR, __func__,
							log_buffer);
						return;
				}

				/*
				 *	Deal with two things that should never
				 *	happen:  first, the result of adjusting
				 *	the resource value should never be
				 *	negative.  Second, BUFSIZ should always
				 *	be sufficient to hold any unsigned
				 *	quantity PBS deals with.
				 */
				if (((int) resval) < 0) {
					log_event(PBSEVENT_ERROR, 0, LOG_ERR,
						__func__, "res underflow");
					return;
				}
				if (snprintf(valbuf, sizeof(valbuf), "%u",
					resval) >= sizeof(valbuf)) {
					log_event(PBSEVENT_ERROR, 0, LOG_ERR,
						__func__, "res overflow");
					return;
				}

				/*
				 *	We now replace the current value with
				 *	the adjusted one.  This may involve
				 *	surgery on the vna_t.
				 */
				if (op == RES_DECR) {
					/*
					 *	Since the resource value is now
					 *	smaller than before, it ought to
					 *	fit in the space that holds the
					 *	current value.
					 */
					strcpy(vnap->vna_val, valbuf);
				} else {
					char	*vna_newval = strdup(valbuf);

					if (vna_newval != NULL) {
						free(vnap->vna_val);
						vnap->vna_val = vna_newval;
					} else {
						log_event(PBSEVENT_ERROR, 0,
							LOG_ERR, __func__,
							"vna_newval strdup failed");
					}
				}
				return;
			}
		}
	}

	sprintf(log_buffer, "vnode %s, resource %s not found", vnid, res);
	log_event(PBSEVENT_DEBUG, 0, LOG_DEBUG, __func__, log_buffer);
}

/**
 * @brief
 *	cpunum_outofservice() is a ``context-free'' function that marks a CPU
 *	(which is referred to by its physical CPU number) as being unusable.
 *
 * @param[in] cpunum - number of cpu
 *
 * @return Void
 *
 */
void
cpunum_outofservice(unsigned int cpunum)
{
	char		buf[BUFSIZ];

	sprintf(buf, "mark CPU %u out of service", cpunum);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, buf);

	cpu_inuse(cpunum, NULL, 1);
}

/**
 * @brief
 *	Common code for cpunum_inuse() and cpunum_outofservice():  to find
 *	the given CPU in our list of CPUs per vnode, we walk the list of
 *	mom_vninfo_t structures and for each of those, the attached CPU lists
 *	looking for a match.  If taking a CPU out of service, cpu_inuse() must
 *	also adjust the "resources_available.ncpus" for the vnode that contains
 *	the CPU being taken out of service.
 *
 * @param[in] cpunum - number of cpu
 * @param[in] pjob - pointer to job structure
 * @param[in] outofserviceflag - flag value to indicate whether cpu out of service
 *
 * @return - Void
 *
 */
static void
cpu_inuse(unsigned int cpunum, job *pjob, int outofserviceflag)
{
	static char	ra_ncpus[] = "resources_available.ncpus";
	AVL_IX_DESC	*pix;
	int		ret;

	pix = cpuctx;
	if (pix == NULL)
		return;

	avl_first_key(pix);

	if (pe == NULL) {
		pe = malloc(sizeof(AVL_IX_REC) + PBS_MAXNODENAME + 1);
		if (pe == NULL) {
			log_err(errno, __func__, "malloc pe failed");
			return;
		}
	}
	while ((ret = avl_next_key(pe, pix)) == AVL_IX_OK) {
		unsigned int	i;
		mominfo_t	*mip;
		mom_vninfo_t	*mvp;

		mip = (mominfo_t *) pe->recptr;
		assert(mip != NULL);
		assert(mip->mi_data != NULL);

		mvp = (mom_vninfo_t *) mip->mi_data;
		for (i = 0; i < mvp->mvi_ncpus; i++)
			if (mvp->mvi_cpulist[i].mvic_cpunum == cpunum) {
				if (MVIC_CPUISFREE(mvp, i)) {
					cpuindex_inuse(mvp, i, pjob);
					if (outofserviceflag != 0) {
						assert(vnlp != NULL);
						assert(mvp->mvi_id != NULL);
						resadj(vnlp, mvp->mvi_id,
							ra_ncpus, RES_DECR,
							1);
						mvp->mvi_acpus--;
					}
				}
				return;
			}
	}

	assert(ret == AVL_EOIX);

	/*
	 *	If we get here, we didn't find the CPU in question.
	 *	Requests to mark a CPU for which we have no record
	 *	out of service may be benign;  we may never have
	 *	known about it because we were never told about it
	 *	in a vnode definitions file, and the caller may
	 *	simply not have checked first.  So, we silently
	 *	ignore those requests.  However, if we're asked
	 *	to mark a CPU in use but haven't heard of it, that's
	 *	an error.
	 */
	if (outofserviceflag == 0) {
		sprintf(log_buffer, "CPU %u not found in cpuctx", cpunum);
		log_err(PBSE_SYSTEM, __func__, log_buffer);
	}
}

#if	defined(MOM_CPUSET)
/**
 * @brief
 *	We maintain the mom_vnodeinfo data for use in constructing CPU sets and
 *	must ensure that the CPU information is correctly reflected in the
 *	vnodes' "resources_available.ncpus" attribute values before those are
 *	passed back to the server.  mom_vnodeinfo data are authoritative since
 *	they must remain unchanged across MoM reconfiguration operations (e.g.
 *	SIGHUP).  This function updates those attribute values in the vnode
 *	attribute lists hanging off the list of vnodes (see "placementsets.h")
 *	that is used in constructing the IS_UPDATE2 response to server IS_HELLO
 *	messages.
 *
 * @return Void
 *
 */
void
cpu_raresync(void)
{
	static char	ra_ncpus[] = "resources_available.ncpus";
	AVL_IX_DESC	*pix;
	int		ret;

	if ((pix = cpuctx) != NULL) {
		avl_first_key(pix);

		if (pe == NULL) {
			pe = malloc(sizeof(AVL_IX_REC) + PBS_MAXNODENAME + 1);
			if (pe == NULL) {
				log_err(errno, __func__, "malloc pe failed");
				return;
			}
		}
		while ((ret = avl_next_key(pe, pix)) == AVL_IX_OK) {
			unsigned int	i;
			mominfo_t	*mip;
			mom_vninfo_t	*mvp;

			mip = (mominfo_t *) pe->recptr;
			assert(mip != NULL);
			assert(mip->mi_data != NULL);

			mvp = (mom_vninfo_t *) mip->mi_data;
			for (i = 0; i < mvp->mvi_ncpus; i++)
				resadj(vnlp, mvp->mvi_id, ra_ncpus, RES_SET,
					mvp->mvi_acpus);
		}

		assert(ret == AVL_EOIX);
	}
}
#endif	/* MOM_CPUSET */

/**
 * @brief
 *	Add a list of CPUs (one or more elements separated by ',' and of the
 *	form M or M-N where M and N are nonnegative integers) to the given mvi.
 *
 * @param[in] mvp - pointer to mom_vninfo_t structure which holds per mom info
 * @param[in] cpulist - cpu list seperated by ','.
 *
 * @return Void
 *
 */
static void
add_CPUlist(mom_vninfo_t *mvp, char *cpulist)
{
	char	*p;

	if ((p = strtok(cpulist, ",")) != NULL) {
		add_CPUrange(mvp, p);
		while ((p = strtok(NULL, ",")) != NULL)
			add_CPUrange(mvp, p);
	}
}

/**
 * @brief
 *	Add the given wad of data (really a mominfo_t structure) to the given
 *	vnode ID, returning 1 if successful or 0 on failure.  An entry with the
 *	given vnode ID should not already be present;  users of this function
 *	should first check this using find_mominfo(), calling add_mominfo()
 *	only if find_mominfo() returned NULL.
 *
 * @param[in] ctx - new vnode
 * @param[in] vnid - vnode id
 * @param[in] data - info about vnode
 *
 * @return int
 * @retval 1 Failure
 * @retval 0 Success
 *
 */
static int
add_mominfo(void *ctx, const char *vnid, void *data)
{

	sprintf(log_buffer, "ctx %p, vnid %s, data %p", ctx, vnid, data);
	log_event(PBSEVENT_DEBUG3, 0, LOG_DEBUG, __func__, log_buffer);

	assert(find_vmapent_byID(ctx, vnid) == NULL);

	if (add_vmapent_byID(ctx, vnid, data) == 0)
		return (0);
	else
		return (1);
}


/**
 * @brief
 *	Return a pointer to the mominfo_t data associated with a given vnode ID,
 *	or NULL if no vnode with the given ID is present.
 *
 * @param[in] vnid - vnode id
 *
 * @return structure
 * @retval structure handle to mominfo_t
 *
 */
mominfo_t *
find_mominfo(const char *vnid)
{
	if (cpuctx == NULL) {
		log_err(PBSE_SYSTEM, __func__, "CPU context not initialized");
		return NULL;
	} else
		return (find_vmapent_byID(cpuctx, vnid));

}

/**
 * @brief
 *	This function is called from vn_addvnr() before vn_addvnr() inserts a
 *	new name/value pair.  If we return zero, the insertion of the given
 *	<ID, name, value> tuple will not occur (but processing of the file
 *	will continue normally);  if we return nonzero, the insertion of
 *	the given tuple will occur (and again, processing continues normally).
 *
 *	Currently we use this function to perform these actions:
 *
 *		for the "cpus" attribute, build a list of the CPUs belonging
 *		to given vnodes
 *
 *		for the "mems" attribute, to record the memory node number of
 *		the memory board belonging to a given vnode (note that in
 *		contrast to CPUs, of which there may be more than one, the
 *		model for memory is that of a single (logical) memory board
 *		per vnode)
 *
 *		for the "sharing" attribute, we simply remember the attribute
 *		value for later use in make_cpuset(), q.v.
 *
 *		for the "resources_available.mem" attribute, set a flag that
 *		tells us to remember to do the memreserved adjustment
 *
 * @param[in] vnid - vnode id
 * @param[in] attr - attributes
 * @param[in] attrval - attribute value
 *
 * @return int
 * @retval -1     Failure
 * @retval  0,1   Success
 *
 */
int
vn_callback(const char *vnid, char *attr, char *attrval)
{
	static void		*ctx = NULL;
#if	defined(MOM_CPUSET)
	static char		memres[] = "resources_available.mem";

	/*
	 *	If we're setting the memory on a vnode, turn on a flag telling
	 *	us to remember to do the memreserved adjustment.
	 */
	if ((do_memreserved_adjustment == 0) && (strcmp(attr, memres) == 0)) {
		do_memreserved_adjustment = 1;
		return (1);
	}
#endif	/* MOM_CPUSET */

	if (strcmp(attr, "cpus") == 0) {
		mom_vninfo_t	*mvp;

		sprintf(log_buffer, "vnid %s, attr %s, val %s",
			vnid, attr, attrval);
		log_event(PBSEVENT_DEBUG3, 0, 0, __func__, log_buffer);

		if ((ctx == NULL) && ((ctx = new_ctx()) == NULL))
			return (-1);
		if ((mvp = vnid2mominfo(vnid, ctx)) == NULL)
			return (0);

		add_CPUlist(mvp, attrval);
		return (0);
	} else if (strcmp(attr, "mems") == 0) {
		mom_vninfo_t	*mvp;

		sprintf(log_buffer, "vnid %s, attr %s, val %s",
			vnid, attr, attrval);
		log_event(PBSEVENT_DEBUG3, 0, 0, __func__, log_buffer);

		if ((ctx == NULL) && ((ctx = new_ctx()) == NULL))
			return (-1);
		if ((mvp = vnid2mominfo(vnid, ctx)) == NULL)
			return (0);

		mvp->mvi_memnum = atoi(attrval);
#if	defined(MOM_CPUSET) && (CPUSET_VERSION >= 4)
		if (memmask_add(mvp->mvi_memnum) != 0)
			return (-1);
#endif	/* MOM_CPUSET && CPUSET_VERSION >= 4 */
		return (0);
	} else if (strcmp(attr, "sharing") == 0) {
		mom_vninfo_t	*mvp;

		if ((ctx == NULL) && ((ctx = new_ctx()) == NULL))
			return (-1);
		if ((mvp = vnid2mominfo(vnid, ctx)) == NULL)
			return (0);

		mvp->mvi_sharing = str_to_vnode_sharing(attrval);
		return (1);

	} else
		return (1);
}

/**
 * @brief
 *	returns new vnode
 *
 * @return vnode on Success or NULL on failure
 *
 */
static void *
new_ctx(void)
{
	if (!create_vmap(&cpuctx)) {
		log_err(PBSE_SYSTEM, __func__, "create_vmap failed");
		return NULL;
	} else
		return (cpuctx);
}

/**
 * @brief
 *	returns pointer to vnode info (mom_vninfo_t).
 *
 * @param[in] vnid - vnode id
 * @param[in] ctx - vnode info
 *
 * @return structure handle
 * @retval pointer to mom_vninfo_t
 *
 */
static mom_vninfo_t *
vnid2mominfo(const char *vnid, const void *ctx)
{
	mominfo_t	*mip;
	mom_vninfo_t	*mvp;

	assert(vnid != NULL);
	assert(ctx != NULL);

	if ((mip = find_vmapent_byID((void *)ctx, vnid)) != NULL) {
		sprintf(log_buffer, "found vnid %s", vnid);
		log_event(PBSEVENT_DEBUG3, 0, 0, __func__, log_buffer);

		mvp = mip->mi_data;
		assert(mvp != NULL);
	} else
		if ((mvp = new_vnid(vnid, (void *)ctx)) == NULL)
			return NULL;

	return (mvp);
}

/**
 * @brief
 *	create new vnode id for vnode
 *
 * @param[in] vnid - vnode id
 * @param[in] ctx - vnode info
 *
 * @return structure handle
 * @retval pointer to mom_vninfo_t
 *
 */
static mom_vninfo_t *
new_vnid(const char *vnid, void *ctx)
{
	mominfo_t	*mip;
	mom_vninfo_t	*mvp;
	char		*newid;

	sprintf(log_buffer, "no vnid %s - creating", vnid);
	log_event(PBSEVENT_DEBUG3, 0, 0, __func__, log_buffer);

	if ((mip = malloc(sizeof(mominfo_t))) == NULL) {
		log_err(errno, __func__, "malloc mominfo_t");
		return NULL;
	}
	if ((mvp = malloc(sizeof(mom_vninfo_t))) == NULL) {
		free(mip);
		log_err(errno, __func__, "malloc vninfo_t");
		return NULL;
	}
	if ((newid = strdup(vnid)) == NULL) {
		free(mvp);
		free(mip);
		log_err(errno, __func__, "strdup vnid");
		return NULL;
	}

	snprintf(mip->mi_host, sizeof(mip->mi_host), "%s", mom_host);
	mip->mi_port = pbs_mom_port;
	mip->mi_rmport = pbs_rm_port;
	mip->mi_data = mvp;
	mip->mi_action = NULL;
	mip->mi_num_action = 0;
	mvp->mvi_id = newid;
	mvp->mvi_ncpus = mvp->mvi_acpus = 0;
	mvp->mvi_cpulist = NULL;
	mvp->mvi_memnum = (unsigned int) -1;	/* uninitialized data marker */

	if (!add_mominfo(ctx, vnid, mip)) {
		sprintf(log_buffer, "add_mom_data %s failed",
			vnid);
		log_err(PBSE_SYSTEM, __func__, log_buffer);
		return NULL;
	}

	return (mvp);
}

#if	defined(MOM_CPUSET) && (CPUSET_VERSION >= 4)
/**
 * @brief
 *	Add a CPU to the mask of CPUs that is constructed while reading
 *	vnode definitions files.
 *
 * @param[in] cpunum - number of cpus
 *
 * @return   int
 * @retval   0    Success
 * @retval  -1    Failure
 *
 */
static int
cpumask_add(unsigned int cpunum)
{
	if (cpu_mask == NULL) {
		if (cpus_nbits == 0)
			cpus_nbits = cpuset_cpus_nbits();
		cpu_mask = bitmask_alloc(cpus_nbits);
		if (cpu_mask == NULL) {
			log_err(PBSE_SYSTEM, __func__, "bitmask_alloc failed");
			return (-1);
		} else
			bitmask_clearall(cpu_mask);
	}
	assert(cpunum < bitmask_nbits(cpu_mask));
	(void) bitmask_setbit(cpu_mask, cpunum);

	return (0);
}

/**
 * @brief
 *	Add a memory node to the memory mask that is constructed while reading
 *	vnode definitions files.
 *
 * @param[in] memnum - memory board node id
 *
 * @return    int
 * @retval    0     Success
 * @retval   -1     Failure
 *
 */
static int
memmask_add(unsigned int memnum)
{
	if (mem_mask == NULL) {
		if (mems_nbits == 0)
			mems_nbits = cpuset_mems_nbits();
		mem_mask = bitmask_alloc(mems_nbits);
		if (mem_mask == NULL) {
			log_err(PBSE_SYSTEM, __func__, "bitmask_alloc failed");
			return (-1);
		} else
			bitmask_clearall(mem_mask);
	}
	assert(memnum < bitmask_nbits(mem_mask));
	(void) bitmask_setbit(mem_mask, memnum);

	return (0);
}

/**
 * @brief
 *	get_cpubits() and get_membits() initialize memory bitmasks used to
 *	represent the CPUs (resp. memory boards) discovered while parsing
 *	vnode definitions files.
 *
 * @param[in] m - pointer to bitmask structure
 *
 * @return Void
 *
 */
void
get_cpubits(struct bitmask *m)
{
	assert(m != NULL);
	if (cpu_mask != NULL) {
		assert(bitmask_nbits(m) == bitmask_nbits(cpu_mask));
		(void) bitmask_copy(m, cpu_mask);
	} else {
		bitmask_clearall(m);
		log_err(PBSE_SYSTEM, __func__, "cpu_mask not yet initialized");
	}
}

/**
 * @brief
 *      get_cpubits() and get_membits() initialize memory bitmasks used to
 *      represent the CPUs (resp. memory boards) discovered while parsing
 *      vnode definitions files.
 *
 * @param[in] m - pointer to bitmask structure
 *
 * @return Void
 *
 */
void
get_membits(struct bitmask *m)
{
	assert(m != NULL);
	if (mem_mask != NULL) {
		assert(bitmask_nbits(m) == bitmask_nbits(mem_mask));
		(void) bitmask_copy(m, mem_mask);
	} else {
		bitmask_clearall(m);
		log_err(PBSE_SYSTEM, __func__, "mem_mask not yet initialized");
	}
}

/**
 * @brief
 *	In response to an unrecoverable error, derive the list of vnodes
 *	assigned to the given job that belong to this mom and use the list
 *	to construct and issue a command to offline them.
 *
 * @param[in] pjob - pointer to job structure
 *
 * @return Void
 *
 */
void
offline_job_vnodes(job *pjob)
{
	int			i;
	hnodent			*hn;
	char			*jid = pjob->ji_qs.ji_jobid;
	static char		*cmdbuf = NULL;
	static char		*cmdprefix = "qmgr -c 'set node ";
	static char		*cmdsuffix = "state += offline'";
	int			suffixlen = strlen(cmdsuffix) + 1;
	char			linebuf[_POSIX_ARG_MAX];
	char			*vnodeptr;	/* vnode within cmdbuf */

	if (cmdbuf == NULL) {
		cmdbuf = malloc(execmax);
		if (cmdbuf == NULL) {
			log_joberr(errno, __func__, "cmdbuf malloc", jid);
			return;
		}
	}
	if (snprintf(cmdbuf, execmax, "%s/bin/%s",
		pbs_conf.pbs_exec_path, cmdprefix) >= execmax) {
		log_joberr(-1, __func__, "cmdbuf overflow", jid);
		return;
	}
	vnodeptr = cmdbuf + strlen(cmdbuf);	/* assume ' ' at cmdprefix end */

	for (i = 0, hn = &pjob->ji_hosts[pjob->ji_nodeid];
		i < hn->hn_vlnum; i++) {
		host_vlist_t	*hv;

		hv = &hn->hn_vlist[i];
		if ((hv->hv_mem > 0) || (hv->hv_ncpus > 0)) {
			size_t	len = strlen(hv->hv_vname);

			if (len >= sizeof(linebuf)) {
				sprintf(log_buffer, "vnode name too long (%lu)",
					len);
				log_joberr(-1, __func__, log_buffer, jid);
				return;
			}

			/* cmdbuf length + vnode name length + ' ' + suffixlen */
			if (strlen(cmdbuf) + len + 1 + suffixlen > execmax) {
				log_joberr(-1, __func__, "cmdbuf overflow", jid);
				return;
			}
			sprintf(linebuf, "%s %s", hv->hv_vname, cmdsuffix);
			(void) strcat(cmdbuf, linebuf);

			if (system(cmdbuf) == -1) {
				log_joberr(errno, __func__,
					"attempt to offline job vnode(s) failed",
					jid);
			} else {
				sprintf(log_buffer, "vnode %s offlined",
					hv->hv_vname);
				log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_JOB,
					LOG_ALERT, jid, log_buffer);
			}
			*vnodeptr = '\0';	/* truncate to cmdprefix */
		}
	}
}

/**
 * @brief
 *	In response to an unrecoverable error (normally after calling the
 *	offline_job_host() function above), requeue a job - perhaps it
 *	will have better luck running on a set of vnodes other than those
 *	just offlined.
 *
 * @param[in] pjob - pointer to job structure
 *
 * @return Void
 *
 */
void
requeue_job(job *pjob)
{
	char			*jid = pjob->ji_qs.ji_jobid;
	static char		*cmdbuf = NULL;

	if (cmdbuf == NULL) {
		cmdbuf = malloc(execmax);
		if (cmdbuf == NULL) {
			log_joberr(errno, __func__, "cmdbuf malloc", jid);
			return;
		}
	}
	if (snprintf(cmdbuf, execmax, "%s/bin/%s %s",
		pbs_conf.pbs_exec_path, "qrerun", jid) >= execmax) {
		log_joberr(-1, __func__, "cmdbuf overflow", jid);
		return;
	}

	if (system(cmdbuf) == -1)
		log_joberr(errno, __func__, "attempt to requeue job failed", jid);
	else
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_JOB, LOG_NOTICE, jid,
			"requeued");
}
#endif	/* MOM_CPUSET && CPUSET_VERSION >= 4 */
