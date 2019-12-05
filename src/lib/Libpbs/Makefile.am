
#
# Copyright (C) 1994-2020 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# For a copy of the commercial license terms and conditions,
# go to: (http://www.pbspro.com/UserArea/agreement.html)
# or contact the Altair Legal Department.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.
#

lib_LTLIBRARIES = libpbs.la

libpbs_la_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	-I$(top_srcdir)/src/lib/Libtpp \
	@KRB5_CFLAGS@

#
# There are specific rules that must be followed when updating the library
# version. The value is completely independent of the product version. Refer
# to the following article prior to modifying the library version:
# https://autotools.io/libtool/version.html
#
pkgconfig_DATA = pbs.pc

libpbs_la_LDFLAGS = -version-info 0:0:0 @KRB5_LIBS@

libpbs_la_LIBADD= \
	-lcrypto \
	-lpthread

libpbs_la_SOURCES = \
	../Libattr/attr_fn_arst.c \
	../Libattr/attr_fn_b.c \
	../Libattr/attr_fn_c.c \
	../Libattr/attr_fn_f.c \
	../Libattr/attr_fn_hold.c \
	../Libattr/attr_fn_intr.c \
	../Libattr/attr_fn_l.c \
	../Libattr/attr_fn_ll.c \
	../Libattr/attr_fn_size.c \
	../Libattr/attr_fn_str.c \
	../Libattr/attr_fn_time.c \
	../Libattr/attr_fn_unkn.c \
	../Libattr/attr_func.c \
	../Libattr/attr_resc_func.c \
	../Libattr/Long_.c \
	../Libattr/LTostr.c \
	../Libattr/resc_map.c \
	../Libattr/uLTostr.c \
	../Libattr/strToL.c \
	../Libattr/strTouL.c \
	../Libcmds/batch_status.c \
	../Libcmds/check_job_script.c \
	../Libcmds/chk_Jrange.c \
	../Libcmds/ck_job_name.c \
	../Libcmds/cnt2server.c \
	../Libcmds/cvtdate.c \
	../Libcmds/get_attr.c \
	../Libcmds/get_dataservice_usr.c \
	../Libcmds/get_server.c \
	../Libcmds/isjobid.c \
	../Libcmds/locate_job.c \
	../Libcmds/parse_at.c \
	../Libcmds/parse_depend.c \
	../Libcmds/parse_destid.c \
	../Libcmds/parse_equal.c \
	../Libcmds/parse_jobid.c \
	../Libcmds/parse_stage.c \
	../Libcmds/pbs_json.c \
	../Libcmds/prepare_path.c \
	../Libcmds/prt_job_err.c \
	../Libcmds/set_attr.c \
	../Libcmds/set_resource.c \
	../Libdis/dis_helpers.c \
	../Libdis/dis.c \
	../Libdis/dis_.h \
	../Libdis/discui_.c \
	../Libdis/discul_.c \
	../Libdis/disi10d_.c \
	../Libdis/disi10l_.c \
	../Libdis/disiui_.c \
	../Libdis/disp10d_.c \
	../Libdis/disp10l_.c \
	../Libdis/disrcs.c \
	../Libdis/disrd.c \
	../Libdis/disrf.c \
	../Libdis/disrfcs.c \
	../Libdis/disrfst.c \
	../Libdis/disrl.c \
	../Libdis/disrl_.c \
	../Libdis/disrsc.c \
	../Libdis/disrsi.c \
	../Libdis/disrsi_.c \
	../Libdis/disrsl.c \
	../Libdis/disrsl_.c \
	../Libdis/disrss.c \
	../Libdis/disrst.c \
	../Libdis/disruc.c \
	../Libdis/disrui.c \
	../Libdis/disrul.c \
	../Libdis/disrus.c \
	../Libdis/diswcs.c \
	../Libdis/diswf.c \
	../Libdis/diswl_.c \
	../Libdis/diswsi.c \
	../Libdis/diswsl.c \
	../Libdis/diswui.c \
	../Libdis/diswui_.c \
	../Libdis/diswul.c \
	../Libdis/ps_dis.c \
	../Libdis/diswull.c \
	../Libdis/disrull.c \
	../Libdis/discull_.c \
	../Libdis/disrsll_.c \
	../Libecl/ecl_verify.c \
	../Libecl/ecl_verify_datatypes.c \
	../Libecl/ecl_verify_values.c \
	../Libecl/ecl_verify_object_name.c \
	../Libecl/pbs_client_thread.c \
	../Libifl/advise.c \
	../Libifl/auth.c \
	../Libifl/conn_table.c \
	../Libifl/dec_Authen.c \
	../Libifl/dec_CopyHookFile.c \
	../Libifl/dec_DelHookFile.c \
	../Libifl/dec_JobCred.c \
	../Libifl/dec_JobFile.c \
	../Libifl/dec_JobId.c \
	../Libifl/dec_Manage.c \
	../Libifl/dec_MsgJob.c \
	../Libifl/dec_MoveJob.c \
	../Libifl/dec_UserCred.c \
	../Libifl/dec_QueueJob.c \
	../Libifl/dec_Reg.c \
	../Libifl/dec_ReqExt.c \
	../Libifl/dec_ReqHdr.c \
	../Libifl/dec_Resc.c \
	../Libifl/dec_RunJob.c \
	../Libifl/dec_Shut.c \
	../Libifl/dec_Sig.c \
	../Libifl/dec_Status.c \
	../Libifl/dec_Track.c \
	../Libifl/dec_attrl.c \
	../Libifl/dec_attropl.c \
	../Libifl/dec_rpyc.c \
	../Libifl/dec_svrattrl.c \
	../Libifl/dec_ModifyResv.c \
	../Libifl/dec_PreemptJobs.c \
	../Libifl/enc_CopyHookFile.c \
	../Libifl/enc_CpyFil.c \
	../Libifl/enc_DelHookFile.c \
	../Libifl/enc_JobCred.c \
	../Libifl/enc_JobFile.c \
	../Libifl/enc_JobId.c \
	../Libifl/enc_UserCred.c \
	../Libifl/enc_Manage.c \
	../Libifl/enc_MsgJob.c \
	../Libifl/enc_MoveJob.c \
	../Libifl/enc_QueueJob.c \
	../Libifl/enc_Reg.c \
	../Libifl/enc_ReqExt.c \
	../Libifl/enc_ReqHdr.c \
	../Libifl/enc_RunJob.c \
	../Libifl/enc_Shut.c \
	../Libifl/enc_Sig.c \
	../Libifl/enc_Status.c \
	../Libifl/enc_Track.c \
	../Libifl/enc_attrl.c \
	../Libifl/enc_attropl.c \
	../Libifl/enc_reply.c \
	../Libifl/enc_SubmitResv.c \
	../Libifl/enc_ModifyResv.c \
	../Libifl/enc_PreemptJobs.c \
	../Libifl/enc_svrattrl.c \
	../Libifl/entlim_parse.c \
	../Libifl/get_hostname.c \
	../Libifl/get_svrport.c \
	../Libifl/grunt_parse.c \
	../Libifl/int_hook.c \
	../Libifl/int_jcred.c \
	../Libifl/int_manager.c \
	../Libifl/int_manage2.c \
	../Libifl/int_msg2.c \
	../Libifl/int_rdrpy.c \
	../Libifl/int_sig2.c \
	../Libifl/int_status2.c \
	../Libifl/int_submit.c \
	../Libifl/int_submit_resv.c \
	../Libifl/int_status.c \
	../Libifl/int_ucred.c \
	../Libifl/int_cred.c \
	../Libifl/enc_Cred.c \
	../Libifl/dec_Cred.c \
	../Libifl/int_modify_resv.c \
	../Libifl/int_preempt_jobs.c \
	../Libifl/list_link.c \
	../Libifl/PBS_attr.c \
	../Libifl/pbs_authors.c \
	../Libifl/pbs_get_attribute_errors.c \
	../Libifl/pbs_geterrmg.c \
	../Libifl/pbs_geterrno.c \
	../Libifl/pbs_loadconf.c \
	../Libifl/pbs_quote_parse.c \
	../Libifl/pbs_statfree.c \
	../Libifl/pbsD_alterjo.c \
	../Libifl/pbsD_asyrun.c \
	../Libifl/pbsD_connect.c \
	../Libifl/pbsD_deljob.c \
	../Libifl/pbsD_holdjob.c \
	../Libifl/pbsD_locjob.c \
	../Libifl/pbsD_manager.c \
	../Libifl/pbsD_movejob.c \
	../Libifl/pbsD_msgjob.c \
	../Libifl/pbsD_orderjo.c \
	../Libifl/pbsD_rerunjo.c \
	../Libifl/pbsD_resc.c \
	../Libifl/pbsD_rlsjob.c \
	../Libifl/pbsD_runjob.c \
	../Libifl/pbsD_selectj.c \
	../Libifl/pbsD_sigjob.c \
	../Libifl/pbsD_stagein.c \
	../Libifl/pbsD_stathost.c \
	../Libifl/pbsD_statjob.c \
	../Libifl/pbsD_statnode.c \
	../Libifl/pbsD_statque.c \
	../Libifl/pbsD_statsrv.c \
	../Libifl/pbsD_statsched.c \
	../Libifl/pbsD_submit.c \
	../Libifl/pbsD_termin.c \
	../Libifl/pbsD_submit_resv.c \
	../Libifl/pbsD_stathook.c \
	../Libifl/pbsD_delresv.c \
	../Libifl/pbsD_statresv.c \
	../Libifl/pbsD_confirmresv.c \
	../Libifl/pbsD_defschreply.c \
	../Libifl/pbsD_statrsc.c \
	../Libifl/pbsD_modify_resv.c \
	../Libifl/pbsD_Preempt_Jobs.c \
	../Libifl/ifl_impl.c \
	../Libifl/ifl_pointers.c \
	../Libifl/rpp.c \
	../Libifl/strsep.c \
	../Libifl/tcp_dis.c \
	../Libifl/tm.c \
	../Libifl/xml_encode_decode.c \
	../Liblog/pbs_messages.c \
	../Libsec/cs_standard.c \
	../Libutil/misc_utils.c \
	../Libutil/pbs_secrets.c \
	../Libutil/pbs_aes_encrypt.c \
	../Libnet/hnls.c \
	ecl_job_attr_def.c \
	ecl_svr_attr_def.c \
	ecl_sched_attr_def.c \
	ecl_node_attr_def.c \
	ecl_queue_attr_def.c \
	ecl_resc_def_all.c \
	ecl_resv_attr_def.c

CLEANFILES = \
	ecl_job_attr_def.c \
	ecl_svr_attr_def.c \
	ecl_sched_attr_def.c \
	ecl_node_attr_def.c \
	ecl_queue_attr_def.c \
	ecl_resc_def_all.c \
	ecl_resv_attr_def.c

ecl_job_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_job_attr_def.xml
	@echo Generating $@ from $< ; \
	$(PYTHON) $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_job_attr_def.xml \
		-s /dev/null -e $@ -a job

ecl_svr_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_svr_attr_def.xml
	@echo Generating $@ from $< ; \
	$(PYTHON) $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_svr_attr_def.xml \
		-s /dev/null -e $@ -a server

ecl_node_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_node_attr_def.xml
	@echo Generating $@ from $< ; \
	$(PYTHON) $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_node_attr_def.xml \
		-s /dev/null -e $@ -a node

ecl_queue_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_queue_attr_def.xml
	@echo Generating $@ from $< ; \
	$(PYTHON) $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_queue_attr_def.xml \
		-s /dev/null -e $@ -a queue

ecl_resv_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_resv_attr_def.xml
	@echo Generating $@ from $< ; \
	$(PYTHON) $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_resv_attr_def.xml \
		-s /dev/null -e $@ -a resv

ecl_sched_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_sched_attr_def.xml
	@echo Generating $@ from $< ; \
	$(PYTHON) $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_sched_attr_def.xml \
		-s /dev/null -e $@ -a sched

ecl_resc_def_all.c: $(top_srcdir)/src/lib/Libattr/master_resc_def_all.xml
	@echo Generating $@ from $< ; \
	$(PYTHON) $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_resc_def_all.xml \
		-s /dev/null -e $@ -a resc
