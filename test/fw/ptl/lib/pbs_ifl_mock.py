# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of both the OpenPBS software ("OpenPBS")
# and the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# OpenPBS is free software. You can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# OpenPBS is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# PBS Pro is commercially licensed software that shares a common core with
# the OpenPBS software.  For a copy of the commercial license terms and
# conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
# Altair Legal Department.
#
# Altair's dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of OpenPBS and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair's trademarks, including but not limited to "PBS™",
# "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
# subject to Altair's trademark licensing policies.


MGR_OBJ_NONE = -1
MGR_OBJ_SERVER = 0
MGR_OBJ_QUEUE = 1
MGR_OBJ_JOB = 2
MGR_OBJ_NODE = 3
MGR_OBJ_RESV = 4
MGR_OBJ_RSC = 5
MGR_OBJ_SCHED = 6
MGR_OBJ_HOST = 7
MGR_OBJ_HOOK = 8
MGR_OBJ_PBS_HOOK = 9

MGR_CMD_NONE = 10
MGR_CMD_CREATE = 11
MGR_CMD_DELETE = 12
MGR_CMD_SET = 13
MGR_CMD_UNSET = 14
MGR_CMD_LIST = 15
MGR_CMD_PRINT = 16
MGR_CMD_ACTIVE = 17
MGR_CMD_IMPORT = 18
MGR_CMD_EXPORT = 19

MSG_OUT = 1
MSG_ERR = 2

ATTR_a = 'Execution_Time'
ATTR_c = 'Checkpoint'
ATTR_e = 'Error_Path'
ATTR_g = 'group_list'
ATTR_h = 'Hold_Types'
ATTR_j = 'Join_Path'
ATTR_J = 'array_indices_submitted'
ATTR_k = 'Keep_Files'
ATTR_l = 'Resource_List'
ATTR_m = 'Mail_Points'
ATTR_o = 'Output_Path'
ATTR_p = 'Priority'
ATTR_q = 'destination'
ATTR_R = 'Remove_Files'
ATTR_r = 'Rerunable'
ATTR_u = 'User_List'
ATTR_v = 'Variable_List'
ATTR_A = 'Account_Name'
ATTR_M = 'Mail_Users'
ATTR_N = 'Job_Name'
ATTR_S = 'Shell_Path_List'
ATTR_W = 'Additional_Attributes'  # Not in pbs_ifl.h
ATTR_array_indices_submitted = ATTR_J
ATTR_max_run_subjobs = 'max_run_subjobs'
ATTR_depend = 'depend'
ATTR_inter = 'interactive'
ATTR_sandbox = 'sandbox'
ATTR_stagein = 'stagein'
ATTR_stageout = 'stageout'
ATTR_resvTag = 'reserve_Tag'
ATTR_resv_start = 'reserve_start'
ATTR_resv_end = 'reserve_end'
ATTR_resv_duration = 'reserve_duration'
ATTR_resv_alter_revert = 'reserve_alter_revert'
ATTR_resv_state = 'reserve_state'
ATTR_resv_substate = 'reserve_substate'
ATTR_del_idle_time = 'delete_idle_time'
ATTR_auth_u = 'Authorized_Users'
ATTR_auth_g = 'Authorized_Groups'
ATTR_auth_h = 'Authorized_Hosts'
ATTR_cred = 'cred'
ATTR_nodemux = 'no_stdio_sockets'
ATTR_umask = 'umask'
ATTR_block = 'block'
ATTR_convert = 'qmove'
ATTR_DefaultChunk = 'default_chunk'
ATTR_X11_cookie = 'forward_x11_cookie'
ATTR_X11_port = 'forward_x11_port'
ATTR_resv_standing = 'reserve_standing'
ATTR_resv_count = 'reserve_count'
ATTR_resv_idx = 'reserve_index'
ATTR_resv_rrule = 'reserve_rrule'
ATTR_resv_execvnodes = 'reserve_execvnodes'
ATTR_resv_timezone = 'reserve_timezone'
ATTR_ctime = 'ctime'
ATTR_estimated = 'estimated'
ATTR_exechost = 'exec_host'
ATTR_exechost2 = 'exec_host2'
ATTR_execvnode = 'exec_vnode'
ATTR_resv_nodes = 'resv_nodes'
ATTR_mtime = 'mtime'
ATTR_qtime = 'qtime'
ATTR_session = 'session_id'
ATTR_jobdir = 'jobdir'
ATTR_job = 'reserve_job'
ATTR_euser = 'euser'
ATTR_egroup = 'egroup'
ATTR_project = 'project'
ATTR_hashname = 'hashname'
ATTR_hopcount = 'hop_count'
ATTR_security = 'security'
ATTR_sched_hint = 'sched_hint'
ATTR_SchedSelect = 'schedselect'
ATTR_substate = 'substate'
ATTR_name = 'Job_Name'
ATTR_owner = 'Job_Owner'
ATTR_used = 'resources_used'
ATTR_state = 'job_state'
ATTR_queue = 'queue'
ATTR_server = 'server'
ATTR_maxrun = 'max_running'
ATTR_max_run = 'max_run'
ATTR_max_run_res = 'max_run_res'
ATTR_max_run_soft = 'max_run_soft'
ATTR_max_run_res_soft = 'max_run_res_soft'
ATTR_total = 'total_jobs'
ATTR_comment = 'comment'
ATTR_cookie = 'cookie'
ATTR_qrank = 'queue_rank'
ATTR_altid = 'alt_id'
ATTR_altid2 = 'alt_id2'
ATTR_metaid = 'meta_id'
ATTR_acct_id = 'accounting_id'
ATTR_array = 'array'
ATTR_array_id = 'array_id'
ATTR_array_index = 'array_index'
ATTR_array_state_count = 'array_state_count'
ATTR_array_indices_remaining = 'array_indices_remaining'
ATTR_etime = 'etime'
ATTR_gridname = 'gridname'
ATTR_refresh = 'last_context_refresh'
ATTR_ReqCredEnable = 'require_cred_enable'
ATTR_ReqCred = 'require_cred'
ATTR_runcount = 'run_count'
ATTR_stime = 'stime'
ATTR_executable = 'executable'
ATTR_Arglist = 'argument_list'
ATTR_version = 'pbs_version'
ATTR_eligible_time = 'eligible_time'
ATTR_accrue_type = 'accrue_type'
ATTR_sample_starttime = 'sample_starttime'
ATTR_job_kill_delay = 'job_kill_delay'
ATTR_history_timestamp = 'history_timestamp'
ATTR_stageout_status = 'Stageout_status'
ATTR_exit_status = 'Exit_status'
ATTR_submit_arguments = 'Submit_arguments'
ATTR_resv_name = 'Reserve_Name'
ATTR_resv_owner = 'Reserve_Owner'
ATTR_resv_Tag = 'reservation_Tag'
ATTR_resv_ID = 'reserve_ID'
ATTR_resv_retry = 'reserve_retry'
ATTR_aclgren = 'acl_group_enable'
ATTR_aclgroup = 'acl_groups'
ATTR_aclhten = 'acl_host_enable'
ATTR_aclhost = 'acl_hosts'
ATTR_acluren = 'acl_user_enable'
ATTR_acluser = 'acl_users'
ATTR_altrouter = 'alt_router'
ATTR_chkptmin = 'checkpoint_min'
ATTR_enable = 'enabled'
ATTR_fromroute = 'from_route_only'
ATTR_HasNodes = 'hasnodes'
ATTR_killdelay = 'kill_delay'
ATTR_maxgrprun = 'max_group_run'
ATTR_maxgrprunsoft = 'max_group_run_soft'
ATTR_maxque = 'max_queuable'
ATTR_max_queued = 'max_queued'
ATTR_max_queued_res = 'max_queued_res'
ATTR_maxuserrun = 'max_user_run'
ATTR_maxuserrunsoft = 'max_user_run_soft'
ATTR_qtype = 'queue_type'
ATTR_rescassn = 'resources_assigned'
ATTR_rescdflt = 'resources_default'
ATTR_rescmax = 'resources_max'
ATTR_rescmin = 'resources_min'
ATTR_rndzretry = 'rendezvous_retry'
ATTR_routedest = 'route_destinations'
ATTR_routeheld = 'route_held_jobs'
ATTR_routewait = 'route_waiting_jobs'
ATTR_routeretry = 'route_retry_time'
ATTR_routelife = 'route_lifetime'
ATTR_rsvexpdt = 'reserved_expedite'
ATTR_rsvsync = 'reserved_sync'
ATTR_start = 'started'
ATTR_count = 'state_count'
ATTR_number = 'number_jobs'
ATTR_SvrHost = 'server_host'
ATTR_aclroot = 'acl_roots'
ATTR_managers = 'managers'
ATTR_dfltque = 'default_queue'
ATTR_defnode = 'default_node'
ATTR_locsvrs = 'location_servers'
ATTR_logevents = 'log_events'
ATTR_logfile = 'log_file'
ATTR_mailfrom = 'mail_from'
ATTR_nodepack = 'node_pack'
ATTR_nodefailrq = 'node_fail_requeue'
ATTR_operators = 'operators'
ATTR_queryother = 'query_other_jobs'
ATTR_resccost = 'resources_cost'
ATTR_rescavail = 'resources_available'
ATTR_maxuserres = 'max_user_res'
ATTR_maxuserressoft = 'max_user_res_soft'
ATTR_maxgroupres = 'max_group_res'
ATTR_maxgroupressoft = 'max_group_res_soft'
ATTR_maxarraysize = 'max_array_size'
ATTR_PNames = 'pnames'
ATTR_schedit = 'scheduler_iteration'
ATTR_scheduling = 'scheduling'
ATTR_status = 'server_state'
ATTR_syscost = 'system_cost'
ATTR_FlatUID = 'flatuid'
ATTR_FLicenses = 'FLicenses'
ATTR_ResvEnable = 'resv_enable'
ATTR_aclResvgren = 'acl_resv_group_enable'
ATTR_aclResvgroup = 'acl_resv_groups'
ATTR_aclResvhten = 'acl_resv_host_enable'
ATTR_aclResvhost = 'acl_resv_hosts'
ATTR_aclResvuren = 'acl_resv_user_enable'
ATTR_aclResvuser = 'acl_resv_users'
ATTR_NodeGroupEnable = 'node_group_enable'
ATTR_NodeGroupKey = 'node_group_key'
ATTR_dfltqdelargs = 'default_qdel_arguments'
ATTR_dfltqsubargs = 'default_qsub_arguments'
ATTR_rpp_retry = 'rpp_retry'
ATTR_rpp_highwater = 'rpp_highwater'
ATTR_rpp_max_pkt_check = 'rpp_max_pkt_check'
ATTR_pbs_license_info = 'pbs_license_info'
ATTR_license_min = 'pbs_license_min'
ATTR_license_max = 'pbs_license_max'
ATTR_license_linger = 'pbs_license_linger_time'
ATTR_license_count = 'license_count'
ATTR_job_sort_formula = 'job_sort_formula'
ATTR_EligibleTimeEnable = 'eligible_time_enable'
ATTR_resv_retry_init = 'reserve_retry_init'
ATTR_resv_retry_time = 'reserve_retry_time'
ATTR_JobHistoryEnable = 'job_history_enable'
ATTR_JobHistoryDuration = 'job_history_duration'
ATTR_max_concurrent_prov = 'max_concurrent_provision'
ATTR_resv_post_processing = 'resv_post_processing_time'
ATTR_backfill_depth = 'backfill_depth'
ATTR_job_requeue_timeout = 'job_requeue_timeout'
ATTR_SchedHost = 'sched_host'
ATTR_sched_cycle_len = 'sched_cycle_length'
ATTR_do_not_span_psets = 'do_not_span_psets'
ATTR_soft_time = 'soft_limit_time'
ATTR_power_provisioning = 'power_provisioning'
ATTR_max_job_sequence_id = 'max_job_sequence_id'
ATTR_rel_list = 'resource_released_list'
ATTR_released = 'resources_released'
ATTR_restrict_res_to_release_on_suspend = 'restrict_res_to_release_on_suspend'
ATTR_sched_preempt_enforce_resumption = 'sched_preempt_enforce_resumption'
ATTR_tolerate_node_failures = 'tolerate_node_failures'
ATTR_HOOK_type = 'type'
ATTR_HOOK_enable = 'enable'
ATTR_HOOK_event = 'event'
ATTR_HOOK_alarm = 'alarm'
ATTR_HOOK_order = 'order'
ATTR_HOOK_debug = 'debug'
ATTR_HOOK_fail_action = 'fail_action'
ATTR_HOOK_user = 'user'
ATTR_NODE_Host = 'Host'
ATTR_NODE_Mom = 'Mom'
ATTR_NODE_Port = 'Port'
ATTR_NODE_state = 'state'
ATTR_NODE_svr_inst_id = "server_instance_id"
ATTR_NODE_ntype = 'ntype'
ATTR_NODE_jobs = 'jobs'
ATTR_NODE_resvs = 'resv'
ATTR_NODE_resv_enable = 'resv_enable'
ATTR_NODE_np = 'np'
ATTR_NODE_pcpus = 'pcpus'
ATTR_NODE_properties = 'properties'
ATTR_NODE_NoMultiNode = 'no_multinode_jobs'
ATTR_NODE_No_Tasks = 'no_tasks'
ATTR_NODE_Sharing = 'sharing'
ATTR_NODE_HPCBP_User_name = 'hpcbp_user_name'
ATTR_NODE_HPCBP_WS_address = 'hpcbp_webservice_address'
ATTR_NODE_HPCBP_Stage_protocol = 'hpcbp_stage_protocol'
ATTR_NODE_HPCBP_enable = 'hpcbp_enable'
ATTR_NODE_ProvisionEnable = 'provision_enable'
ATTR_NODE_current_aoe = 'current_aoe'
ATTR_NODE_in_multivnode_host = 'in_multivnode_host'
ATTR_NODE_License = 'license'
ATTR_NODE_LicenseInfo = 'license_info'
ATTR_NODE_TopologyInfo = 'topology_info'
ATTR_NODE_last_used_time = 'last_used_time'
ATTR_NODE_last_state_change_time = 'last_state_change_time'
ATTR_sched_server_dyn_res_alarm = 'server_dyn_res_alarm'
ATTR_RESC_TYPE = 'type'
ATTR_RESC_FLAG = 'flag'

SHUT_IMMEDIATE = 0x0
SHUT_DELAY = 0x01
SHUT_QUICK = 0x02
SHUT_WHO_SCHED = 0x10
SHUT_WHO_MOM = 0x20
SHUT_WHO_SECDRY = 0x40
SHUT_WHO_IDLESECDRY = 0x80
SHUT_WHO_SECDONLY = 0x100

USER_HOLD = 'u'
OTHER_HOLD = 'o'
SYSTEM_HOLD = 's'
BAD_PASSWORD_HOLD = 'p'


class attropl:

    def __init__(self):
        self.name = None
        self.value = None
        self.attribute = None
        self.next = None
        self.resource = None
        self.op = None


class attrl:

    def __init__(self):
        self.name = None
        self.value = None
        self.attribute = None
        self.next = None
        self.resource = None
        self.op = None


class batch_status:

    def __init__(self):
        self.next = None
        self.name = None
        self.attribs = None
        self.text = None


class ecl_attrerr:

    def __init__(self):
        self.ecl_attribute = None
        self.ecl_errcode = None
        self.ecl_errmsg = None


class ecl_attribute_errors:

    def __init(self):
        self.ecl_numerrors = None
        self.ecl_attrerr = None


def pbs_asyrunjob(c, jobid, attrib, extend):
    pass


def pbs_alterjob(c, jobid, attrib, extend):
    pass


def pbs_connect(c):
    pass


def pbs_connect_extend(c, extend):
    pass


def pbs_default(void):
    pass


def pbs_deljob(c, jobid, extend):
    pass


def pbs_disconnect(c):
    pass


def pbs_geterrmsg(c):
    pass


def pbs_holdjob(c, jobid, hold, extend):
    pass


def pbs_locjob(c, jobid, extend):
    pass


def pbs_manager(c, cmd, type, id, attropl, extend):
    pass


def pbs_movejob(c, jobid, destin, extend):
    pass


def pbs_msgjob(c, jobid, file, msg, extend):
    pass


def pbs_orderjob(c, jobid1, jobid2, extend):
    pass


def pbs_rerunjob(c, jobid, extend):
    pass


def pbs_rlsjob(c, jobid, hold, extend):
    pass


def pbs_runjob(c, jobid, loc, extend):
    pass


def pbs_selectjob(c, attropl, extend):
    pass


def pbs_sigjob(c, jobid, sig, extend):
    pass


def pbs_statfree(batch_status):
    pass


def pbs_statjob(c, jobid, attrl, extend):
    pass


def pbs_selstat(c, attropl, attrl, extend):
    pass


def pbs_statque(c, q, attrl, extend):
    pass


def pbs_statserver(c, attrl, extend):
    pass


def pbs_statsched(c, attrl, extend):
    pass


def pbs_stathost(c, id, attrl, extend):
    pass


def pbs_statnode(c, id, attrl, extend):
    pass


def pbs_statvnode(c, id, attrl, extend):
    pass


def pbs_statresv(c, id, attrl, extend):
    pass


def pbs_stathook(c, id, attrl, s1):
    pass


def pbs_statrsc(c, id, attrl, extend):
    pass


def pbs_get_attributes_in_error(c):
    pass


def pbs_submit(c, attropl, script, destin, extend):
    pass


def pbs_submit_resv(c, attropl, jobid):
    pass


def pbs_delresv(c, id, extend):
    pass


def pbs_terminate(c, manner, extend):
    pass


def pbs_modify_resv(c, resvid, attrib, extend):
    pass
