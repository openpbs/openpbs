/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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

/*
 * pbs_schema.sql - contains sql code to re-create the PBS database schema
 *
 */

drop schema pbs cascade; -- Drop any existing schema called pbs
create schema pbs;	 -- Create a new schema called pbs

---------------------- VERSION -----------------------------

/*
 * Table pbs.info holds information about the schema
 * - The schema version, used for migrating and updating PBS
 */
CREATE TABLE pbs.info (
    pbs_schema_version TEXT 		NOT NULL
);

INSERT INTO pbs.info values('1.2.0'); /* schema version */

/*
 * Sequence pbs.svr_id_seq is used to create svr_ids for new server entries.
 * The svr hostname (sv_hostname column) is associated with a 
 * sever_id (sv_name) column. This column serves as the id for the server, 
 * used for all subsequent queries. These "id" values are created from the
 * following sequence generator whenever a new server database is created
 * (typically at new installation).
 */
CREATE SEQUENCE pbs.svr_id_seq;


---------------------- SERVER ------------------------------

/*
 * Table pbs.server holds server instance information
 */
CREATE TABLE pbs.server (
    sv_name		TEXT		NOT NULL, /* the server id value */
    sv_hostname		TEXT		NOT NULL, /* the actual server hostname - can change */
    sv_numjobs		INTEGER		NOT NULL,
    sv_numque		INTEGER		NOT NULL,
    sv_jobidnumber	INTEGER		NOT NULL,
    sv_svraddr		BIGINT		NOT NULL,
    sv_svrport		INTEGER		NOT NULL,
    sv_savetm		TIMESTAMP	NOT NULL,
    sv_creattm		TIMESTAMP	NOT NULL,
    CONSTRAINT server_pk PRIMARY KEY (sv_name)
);


/*
 * Table pbs.svr_attr holds server attribute information
 */
CREATE TABLE pbs.server_attr (
    sv_name		TEXT		NOT NULL,
    attr_name		TEXT		NOT NULL,
    attr_resource	TEXT,
    attr_value		TEXT,
    attr_flags		INTEGER		NOT NULL
);
CREATE INDEX svr_attr_idx ON pbs.server_attr (sv_name, attr_name);

/*
 * Foreign key constraint between server and its attributes
 */
ALTER TABLE pbs.server_attr ADD CONSTRAINT server_attr_fk
FOREIGN KEY (sv_name)
REFERENCES pbs.server (sv_name)
ON DELETE CASCADE
ON UPDATE NO ACTION
NOT DEFERRABLE;

---------------------- SCHED -------------------------------

/*
 * Table pbs.scheduler holds scheduler instance information
 */
CREATE TABLE pbs.scheduler (
    sched_name		TEXT		NOT NULL,
    sched_sv_name	TEXT		NOT NULL,
    sched_savetm	TIMESTAMP	NOT NULL,
    sched_creattm	TIMESTAMP	NOT NULL,
    CONSTRAINT scheduler_pk PRIMARY KEY (sched_name)
);


/*
 * Table pbs.svr_attr holds scheduler attribute information
 */
CREATE TABLE pbs.scheduler_attr (
    sched_name		TEXT		NOT NULL,
    attr_name		TEXT		NOT NULL,
    attr_resource	TEXT,
    attr_value		TEXT,
    attr_flags		INTEGER		NOT NULL
);
CREATE INDEX sched_attr_idx ON pbs.scheduler_attr (sched_name, attr_name);

/*
 * Foreign key constraint between scheduler and its attributes
 */
ALTER TABLE pbs.scheduler_attr ADD CONSTRAINT scheduler_attr_fk
FOREIGN KEY (sched_name)
REFERENCES pbs.scheduler (sched_name)
ON DELETE CASCADE
ON UPDATE NO ACTION
NOT DEFERRABLE;

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
    CONSTRAINT pbsnode_pk PRIMARY KEY (nd_name)
);
CREATE INDEX nd_idx_cr
ON pbs.node
( nd_creattm );


/*
 * Table pbs.node_attr holds node_attribute information
 */
CREATE TABLE pbs.node_attr (
    nd_name		TEXT		NOT NULL,
    attr_name		TEXT		NOT NULL,
    attr_resource	TEXT,
    attr_value		TEXT,
    attr_flags		INTEGER		NOT NULL
);
CREATE INDEX node_attr_idx ON pbs.node_attr (nd_name, attr_name);


/*
 * Foreign key constraint between node and its attributes
 */
ALTER TABLE pbs.node_attr ADD CONSTRAINT node_attr_fk
FOREIGN KEY (nd_name)
REFERENCES pbs.node (nd_name)
ON DELETE CASCADE
ON UPDATE NO ACTION
NOT DEFERRABLE;


---------------------- QUEUE -------------------------------

/*
 * Table pbs.queue holds queue information
 */
CREATE TABLE pbs.queue (
    qu_name		TEXT		NOT NULL,
    qu_sv_name		TEXT		NOT NULL,
    qu_type		INTEGER		NOT NULL,
    qu_ctime		TIMESTAMP	NOT NULL,
    qu_mtime		TIMESTAMP	NOT NULL,
    CONSTRAINT queue_pk PRIMARY KEY (qu_name)
);
CREATE INDEX que_idx_cr
ON pbs.queue
( qu_ctime );


CREATE TABLE pbs.queue_attr (
    qu_name		TEXT		NOT NULL,
    attr_name		TEXT		NOT NULL,
    attr_resource	TEXT,
    attr_value		TEXT,
    attr_flags		INTEGER		NOT NULL
);
CREATE INDEX queue_attr_idx ON pbs.queue_attr (qu_name, attr_name);

/*
 * Foreign key constraint between queue and its attributes
 */
ALTER TABLE pbs.queue_attr ADD CONSTRAINT queue_attr_fk
FOREIGN KEY (qu_name)
REFERENCES pbs.queue (qu_name)
ON DELETE CASCADE
ON UPDATE NO ACTION
NOT DEFERRABLE;


/*
 * Foreign key constraint between queue and parent server
 */
ALTER TABLE pbs.queue ADD CONSTRAINT que_svr_fk
FOREIGN KEY (qu_sv_name)
REFERENCES pbs.server (sv_name)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;

---------------------- RESERVATION -------------------------

/*
 * Table pbs.resv holds reservation information
 */
CREATE TABLE pbs.resv (
    ri_resvID		TEXT		NOT NULL,
    ri_sv_name		TEXT		NOT NULL,
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
    CONSTRAINT resv_pk PRIMARY KEY (ri_resvID)
);

CREATE INDEX resv_idx_cr
ON pbs.resv
( ri_creattm );

CREATE TABLE pbs.resv_attr (
    ri_resvID		TEXT		NOT NULL,
    attr_name		TEXT		NOT NULL,
    attr_resource	TEXT,
    attr_value		TEXT,
    attr_flags		INTEGER		NOT NULL
);
CREATE INDEX resv_attr_idx ON pbs.resv_attr (ri_resvID, attr_name);

/*
 * Foreign key constraint between resv and its attributes
 */
ALTER TABLE pbs.resv_attr ADD CONSTRAINT resv_attr_fk
FOREIGN KEY (ri_resvID)
REFERENCES pbs.resv (ri_resvID)
ON DELETE CASCADE
ON UPDATE NO ACTION
NOT DEFERRABLE;

/*
 * Foreign key constraint between resv and parent server
 */
ALTER TABLE pbs.resv ADD CONSTRAINT resv_svr_fk
FOREIGN KEY (ri_sv_name)
REFERENCES pbs.server (sv_name)
ON DELETE NO ACTION
ON UPDATE NO ACTION
NOT DEFERRABLE;

---------------------- JOB ---------------------------------

/*
 * Table pbs.job holds job information
 */
CREATE TABLE pbs.job (
    ji_jobid		TEXT		NOT NULL,
    ji_sv_name		TEXT		NOT NULL,
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
    ji_creattm		TIMESTAMP	NOT NULL
);
CREATE INDEX ji_jobid_idx
ON pbs.job
( ji_jobid );

CREATE INDEX job_rank_idx
ON pbs.job
( ji_qrank );


/*
 * Table pbs.subjob holds the subjob information
 */
CREATE TABLE pbs.subjob_track (
    ji_jobid		TEXT		NOT NULL,
    trk_index		INTEGER,
    trk_status		INTEGER,
    trk_error		INTEGER,
    trk_exitstat	INTEGER,
    trk_substate	INTEGER,
    trk_stgout		INTEGER
);

CREATE INDEX subjob_jobid_idx 
ON pbs.subjob_track 
(ji_jobid, trk_index);

CREATE INDEX subjob_track_idx
ON pbs.subjob_track
( trk_index );

/*
 * Table pbs.job_scr holds the job script 
 */
CREATE TABLE pbs.job_scr (
    ji_jobid		TEXT		NOT NULL,
    script		TEXT
);
CREATE INDEX job_src_idx ON pbs.job_scr (ji_jobid);


/*
 * Table pbs.job_attr holds the job attributes 
 */
CREATE TABLE pbs.job_attr (
    ji_jobid		TEXT		NOT NULL,
    attr_name		TEXT		NOT NULL,
    attr_resource	TEXT,
    attr_value		TEXT,
    attr_flags		INTEGER		NOT NULL
);
CREATE INDEX job_attr_idx ON pbs.job_attr (ji_jobid, attr_name, attr_resource);

---------------------- END OF SCHEMA -----------------------

