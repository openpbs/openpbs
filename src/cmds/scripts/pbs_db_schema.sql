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

/*
 * pbs_schema.sql - contains sql code to re-create the PBS database schema
 *
 */

drop schema pbs cascade; -- Drop any existing schema called pbs
create schema pbs;	 -- Create a new schema called pbs
create extension hstore; -- Create the hstore extension if it does not exit
---------------------- VERSION -----------------------------

/*
 * Table pbs.info holds information about the schema
 * - The schema version, used for migrating and updating PBS
 */
CREATE TABLE pbs.info (
    pbs_schema_version TEXT 		NOT NULL
);

INSERT INTO pbs.info values('1.4.0'); /* schema version */

---------------------- SERVER ------------------------------

/*
 * Table pbs.server holds server instance information
 */
CREATE TABLE pbs.server (
    sv_numjobs		INTEGER		NOT NULL,
    sv_numque		INTEGER		NOT NULL,
    sv_jobidnumber	BIGINT		NOT NULL,
    sv_svraddr		BIGINT		NOT NULL,
    sv_svrport		INTEGER		NOT NULL,
    sv_savetm		TIMESTAMP	NOT NULL,
    sv_creattm		TIMESTAMP	NOT NULL,
    attributes		hstore		NOT NULL DEFAULT ''	
);
---------------------- SCHED -------------------------------

/*
 * Table pbs.scheduler holds scheduler instance information
 */
CREATE TABLE pbs.scheduler (
    sched_name		TEXT		NOT NULL,
    sched_savetm	TIMESTAMP	NOT NULL,
    sched_creattm	TIMESTAMP	NOT NULL,
    attributes		hstore		NOT NULL default '',	
    CONSTRAINT scheduler_pk PRIMARY KEY (sched_name)
);

---------------------- NODE --------------------------------

/*
 * Table pbs.mominfo_time holds information about the generation and time of 
 * the host to vnode map
 */
CREATE TABLE pbs.mominfo_time (
    mit_time		BIGINT,
    mit_gen		INTEGER
);

/*
 * Table pbs.node holds information about PBS nodes
 */
CREATE TABLE pbs.node (
    nd_name		TEXT		NOT NULL,
    mom_modtime		BIGINT,
    nd_hostname		TEXT		NOT NULL,
    nd_state		INTEGER		NOT NULL,
    nd_ntype		INTEGER		NOT NULL,
    nd_pque		TEXT,
    nd_index		INTEGER		NOT NULL,
    nd_savetm		TIMESTAMP	NOT NULL,
    nd_creattm		TIMESTAMP	NOT NULL,
    attributes		hstore		NOT NULL default '',
    CONSTRAINT pbsnode_pk PRIMARY KEY (nd_name)
);
CREATE INDEX nd_idx_cr
ON pbs.node
( nd_creattm );

---------------------- QUEUE -------------------------------

/*
 * Table pbs.queue holds queue information
 */
CREATE TABLE pbs.queue (
    qu_name		TEXT		NOT NULL,
    qu_type		INTEGER		NOT NULL,
    qu_ctime		TIMESTAMP	NOT NULL,
    qu_mtime		TIMESTAMP	NOT NULL,
    attributes		hstore		NOT NULL default '',
    CONSTRAINT queue_pk PRIMARY KEY (qu_name)
);
CREATE INDEX que_idx_cr
ON pbs.queue
( qu_ctime );


---------------------- RESERVATION -------------------------

/*
 * Table pbs.resv holds reservation information
 */
CREATE TABLE pbs.resv (
    ri_resvID		TEXT		NOT NULL,
    ri_queue		TEXT		NOT NULL,
    ri_state		INTEGER		NOT NULL,
    ri_substate		INTEGER		NOT NULL,
    ri_type		INTEGER		NOT NULL,
    ri_stime		BIGINT		NOT NULL,
    ri_etime		BIGINT		NOT NULL,
    ri_duration		BIGINT		NOT NULL,
    ri_tactive		INTEGER		NOT NULL,
    ri_svrflags		INTEGER		NOT NULL,
    ri_numattr		INTEGER		NOT NULL,
    ri_resvTag		INTEGER		NOT NULL,
    ri_un_type		INTEGER		NOT NULL,
    ri_fromsock		INTEGER		NOT NULL,
    ri_fromaddr		BIGINT		NOT NULL,
    ri_savetm		TIMESTAMP	NOT NULL,
    ri_creattm		TIMESTAMP	NOT NULL,
    attributes		hstore		NOT NULL default '',
    CONSTRAINT resv_pk PRIMARY KEY (ri_resvID)
);


---------------------- JOB ---------------------------------

/*
 * Table pbs.job holds job information
 */
CREATE TABLE pbs.job (
    ji_jobid		TEXT		NOT NULL,
    ji_state		INTEGER		NOT NULL,
    ji_substate		INTEGER		NOT NULL,
    ji_svrflags		INTEGER		NOT NULL,
    ji_numattr		INTEGER		NOT NULL,
    ji_ordering		INTEGER		NOT NULL,
    ji_priority		INTEGER		NOT NULL,
    ji_stime		BIGINT,
    ji_endtbdry		BIGINT,
    ji_queue		TEXT		NOT NULL,
    ji_destin		TEXT,
    ji_un_type		INTEGER		NOT NULL,
    ji_momaddr		BIGINT,
    ji_momport		INTEGER,
    ji_exitstat		INTEGER,
    ji_quetime		BIGINT,
    ji_rteretry		BIGINT,
    ji_fromsock		INTEGER,
    ji_fromaddr		BIGINT,
    ji_4jid		TEXT,
    ji_4ash		TEXT,
    ji_credtype		INTEGER,
    ji_qrank		INTEGER		NOT NULL,
    ji_savetm		TIMESTAMP	NOT NULL,
    ji_creattm		TIMESTAMP	NOT NULL,
    attributes		hstore		NOT NULL default '',
    CONSTRAINT jobid_pk PRIMARY KEY (ji_jobid)
);

CREATE INDEX job_rank_idx
ON pbs.job
( ji_qrank );


/*
 * Table pbs.job_scr holds the job script 
 */
CREATE TABLE pbs.job_scr (
    ji_jobid		TEXT		NOT NULL,
    script		TEXT
);
CREATE INDEX job_scr_idx ON pbs.job_scr (ji_jobid);

---------------------- END OF SCHEMA -----------------------

