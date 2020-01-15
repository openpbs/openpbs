# coding: utf-8

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

from ptl.lib.pbs_ifl_mock import *

api_to_cli = {
    ATTR_a: 'a',
    ATTR_c: 'c',
    ATTR_e: 'e',
    ATTR_g: 'W group_list=',
    ATTR_h: 'h',
    ATTR_j: 'j',
    ATTR_J: 'J',
    ATTR_k: 'k',
    ATTR_l: 'l',
    ATTR_m: 'm',
    ATTR_o: 'o',
    ATTR_p: 'p',
    ATTR_q: 'q',
    ATTR_R: 'R',
    ATTR_r: 'r',
    ATTR_u: 'u',
    ATTR_v: 'v',
    ATTR_A: 'A',
    ATTR_M: 'M',
    ATTR_N: 'N',
    ATTR_S: 'S',
    ATTR_W: 'W',
    ATTR_array_indices_submitted: 'J',
    ATTR_depend: 'W depend=',
    ATTR_inter: 'I',
    ATTR_sandbox: 'W sandbox=',
    ATTR_stagein: 'W stagein=',
    ATTR_stageout: 'W stageout=',
    ATTR_resvTag: 'reserve_Tag',
    ATTR_resv_start: 'R',
    ATTR_resv_end: 'E',
    ATTR_resv_duration: 'D',
    ATTR_resv_state: 'reserve_state',
    ATTR_resv_substate: 'reserve_substate',
    ATTR_auth_u: 'U',
    ATTR_auth_g: 'G',
    ATTR_auth_h: 'Authorized_Hosts',
    ATTR_pwd: 'pwd',
    ATTR_cred: 'cred',
    ATTR_nodemux: 'no_stdio_sockets',
    ATTR_umask: 'W umask=',
    ATTR_block: 'W block=',
    ATTR_convert: 'W qmove=',
    ATTR_DefaultChunk: 'default_chunk',
    ATTR_X11_cookie: 'forward_x11_cookie',
    ATTR_X11_port: 'forward_x11_port',
    ATTR_resv_standing: '',
    ATTR_resv_count: 'reserve_count',
    ATTR_resv_idx: 'reserve_index',
    ATTR_resv_rrule: 'r',
    ATTR_resv_execvnodes: 'reserve_execvnodes',
    ATTR_resv_timezone: '',
    ATTR_ctime: 'c',
    ATTR_estimated: 't',
    ATTR_exechost: 'exec_host',
    ATTR_exechost2: 'exec_host2',
    ATTR_execvnode: 'exec_vnode',
    ATTR_resv_nodes: 'resv_nodes',
    ATTR_mtime: 'm',
    ATTR_qtime: 'q',
    ATTR_session: 'session_id',
    ATTR_jobdir: 'jobdir',
    ATTR_euser: 'euser',
    ATTR_egroup: 'egroup',
    ATTR_project: 'P',
    ATTR_hashname: 'hashname',
    ATTR_hopcount: 'hop_count',
    ATTR_security: 'security',
    ATTR_sched_hint: 'sched_hint',
    ATTR_SchedSelect: 'schedselect',
    ATTR_substate: 'substate',
    ATTR_name: 'N',
    ATTR_owner: 'Job_Owner',
    ATTR_used: 'resources_used',
    ATTR_state: 's',
    ATTR_queue: 'q',
    ATTR_server: 'server',
    ATTR_maxrun: 'max_running',
    ATTR_max_run: 'max_run',
    ATTR_max_run_res: 'max_run_res',
    ATTR_max_run_soft: 'max_run_soft',
    ATTR_max_run_res_soft: 'max_run_res_soft',
    ATTR_total: 'total_jobs',
    ATTR_comment: 'W comment=',
    ATTR_cookie: 'cookie',
    ATTR_qrank: 'queue_rank',
    ATTR_altid: 'alt_id',
    ATTR_altid2: 'alt_id2',
    ATTR_acct_id: 'accounting_id',
    ATTR_array: 'J',
    ATTR_array_id: 'array_id',
    ATTR_array_index: 'array_index',
    ATTR_array_state_count: 'array_state_count',
    ATTR_array_indices_remaining: 'array_indices_remaining',
    ATTR_etime: 'e',
    ATTR_gridname: 'gridname',
    ATTR_refresh: 'last_context_refresh',
    ATTR_ReqCredEnable: 'require_cred_enable',
    ATTR_ReqCred: 'require_cred',
    ATTR_runcount: 'W run_count=',
    ATTR_stime: 's',
    ATTR_pset: 'pset',
    ATTR_executable: 'executable',
    ATTR_Arglist: 'argument_list',
    ATTR_version: 'pbs_version',
    ATTR_eligible_time: 'g',
    ATTR_accrue_type: 'accrue_type',
    ATTR_sample_starttime: 'sample_starttime',
    ATTR_job_kill_delay: 'job_kill_delay',
    ATTR_history_timestamp: 'history_timestamp',
    ATTR_stageout_status: 'Stageout_status',
    ATTR_exit_status: 'Exit_status',
    ATTR_submit_arguments: 'Submit_arguments',
    ATTR_resv_name: 'Reserve_Name',
    ATTR_resv_owner: 'Reserve_Owner',
    ATTR_resv_type: 'reserve_type',
    ATTR_resv_Tag: 'reservation_Tag',
    ATTR_resv_ID: 'reserve_ID',
    ATTR_resv_retry: 'reserve_retry',
    ATTR_aclgren: 'acl_group_enable',
    ATTR_aclgroup: 'acl_groups',
    ATTR_aclhten: 'acl_host_enable',
    ATTR_aclhost: 'acl_hosts',
    ATTR_acluren: 'acl_user_enable',
    ATTR_acluser: 'acl_users',
    ATTR_altrouter: 'alt_router',
    ATTR_chkptmin: 'checkpoint_min',
    ATTR_enable: 'enabled',
    ATTR_fromroute: 'from_route_only',
    ATTR_HasNodes: 'hasnodes',
    ATTR_killdelay: 'kill_delay',
    ATTR_maxgrprun: 'max_group_run',
    ATTR_maxgrprunsoft: 'max_group_run_soft',
    ATTR_maxque: 'max_queuable',
    ATTR_max_queued: 'max_queued',
    ATTR_max_queued_res: 'max_queued_res',
    ATTR_maxuserrun: 'max_user_run',
    ATTR_maxuserrunsoft: 'max_user_run_soft',
    ATTR_qtype: 'queue_type',
    ATTR_rescassn: 'resources_assigned',
    ATTR_rescdflt: 'resources_default',
    ATTR_rescmax: 'resources_max',
    ATTR_rescmin: 'resources_min',
    ATTR_rndzretry: 'rendezvous_retry',
    ATTR_routedest: 'route_destinations',
    ATTR_routeheld: 'route_held_jobs',
    ATTR_routewait: 'route_waiting_jobs',
    ATTR_routeretry: 'route_retry_time',
    ATTR_routelife: 'route_lifetime',
    ATTR_rsvexpdt: 'reserved_expedite',
    ATTR_rsvsync: 'reserved_sync',
    ATTR_start: 'started',
    ATTR_count: 'state_count',
    ATTR_number: 'number_jobs',
    ATTR_SvrHost: 'server_host',
    ATTR_aclroot: 'acl_roots',
    ATTR_managers: 'managers',
    ATTR_dfltque: 'default_queue',
    ATTR_defnode: 'default_node',
    ATTR_locsvrs: 'location_servers',
    ATTR_logevents: 'log_events',
    ATTR_logfile: 'log_file',
    ATTR_mailfrom: 'mail_from',
    ATTR_nodepack: 'node_pack',
    ATTR_nodefailrq: 'node_fail_requeue',
    ATTR_operators: 'operators',
    ATTR_queryother: 'query_other_jobs',
    ATTR_resccost: 'resources_cost',
    ATTR_rescavail: 'resources_available',
    ATTR_maxuserres: 'max_user_res',
    ATTR_maxuserressoft: 'max_user_res_soft',
    ATTR_maxgroupres: 'max_group_res',
    ATTR_maxgroupressoft: 'max_group_res_soft',
    ATTR_maxarraysize: 'max_array_size',
    ATTR_PNames: 'pnames',
    ATTR_schedit: 'scheduler_iteration',
    ATTR_scheduling: 'scheduling',
    ATTR_status: 'server_state',
    ATTR_syscost: 'system_cost',
    ATTR_FlatUID: 'flatuid',
    ATTR_FLicenses: 'FLicenses',
    ATTR_ResvEnable: 'resv_enable',
    ATTR_aclResvgren: 'acl_resv_group_enable',
    ATTR_aclResvgroup: 'acl_resv_groups',
    ATTR_aclResvhten: 'acl_resv_host_enable',
    ATTR_aclResvhost: 'acl_resv_hosts',
    ATTR_aclResvuren: 'acl_resv_user_enable',
    ATTR_aclResvuser: 'acl_resv_users',
    ATTR_NodeGroupEnable: 'node_group_enable',
    ATTR_NodeGroupKey: 'node_group_key',
    ATTR_ssignon_enable: 'single_signon_password_enable',
    ATTR_dfltqdelargs: 'default_qdel_arguments',
    ATTR_dfltqsubargs: 'default_qsub_arguments',
    ATTR_rpp_retry: 'rpp_retry',
    ATTR_rpp_highwater: 'rpp_highwater',
    ATTR_pbs_license_info: 'pbs_license_info',
    ATTR_license_min: 'pbs_license_min',
    ATTR_license_max: 'pbs_license_max',
    ATTR_license_linger: 'pbs_license_linger_time',
    ATTR_license_count: 'license_count',
    ATTR_job_sort_formula: 'job_sort_formula',
    ATTR_EligibleTimeEnable: 'eligible_time_enable',
    ATTR_resv_retry_init: 'reserve_retry_init',
    ATTR_resv_retry_cutoff: 'reserve_retry_cutoff',
    ATTR_JobHistoryEnable: 'job_history_enable',
    ATTR_JobHistoryDuration: 'job_history_duration',
    ATTR_max_concurrent_prov: 'max_concurrent_provision',
    ATTR_resv_post_processing: 'resv_post_processing_time',
    ATTR_backfill_depth: 'backfill_depth',
    ATTR_job_requeue_timeout: 'job_requeue_timeout',
    ATTR_SchedHost: 'sched_host',
    ATTR_sched_cycle_len: 'sched_cycle_length',
    ATTR_do_not_span_psets: 'do_not_span_psets',
    ATTR_soft_time: 'Wsoft_limit_time',
    ATTR_power_provisioning: 'power_provisioning',
    ATTR_max_job_sequence_id: 'max_job_sequence_id',
    ATTR_tolerate_node_failures: 'Wtolerate_node_failures=',
    ATTR_NODE_Host: 'Host',
    ATTR_NODE_Mom: 'Mom',
    ATTR_NODE_Port: 'Port',
    ATTR_NODE_state: 'state',
    ATTR_NODE_ntype: 'ntype',
    ATTR_NODE_jobs: 'jobs',
    ATTR_NODE_resvs: 'resv',
    ATTR_NODE_resv_enable: 'resv_enable',
    ATTR_NODE_np: 'np',
    ATTR_NODE_pcpus: 'pcpus',
    ATTR_NODE_properties: 'properties',
    ATTR_NODE_NoMultiNode: 'no_multinode_jobs',
    ATTR_NODE_No_Tasks: 'no_tasks',
    ATTR_NODE_Sharing: 'sharing',
    ATTR_NODE_HPCBP_User_name: 'hpcbp_user_name',
    ATTR_NODE_HPCBP_WS_address: 'hpcbp_webservice_address',
    ATTR_NODE_HPCBP_Stage_protocol: 'hpcbp_stage_protocol',
    ATTR_NODE_HPCBP_enable: 'hpcbp_enable',
    ATTR_NODE_ProvisionEnable: 'provision_enable',
    ATTR_NODE_current_aoe: 'current_aoe',
    ATTR_NODE_in_multivnode_host: 'in_multivnode_host',
    ATTR_NODE_License: 'license',
    ATTR_NODE_LicenseInfo: 'license_info',
    ATTR_NODE_TopologyInfo: 'topology_info',
    ATTR_NODE_last_used_time: 'last_used_time',
    ATTR_NODE_last_state_change_time: 'last_state_change_time',
    ATTR_RESC_TYPE: 'type',
    ATTR_RESC_FLAG: 'flag',
    SHUT_QUICK: 't quick',
    SHUT_DELAY: 't delay',
    SHUT_IMMEDIATE: 't immediate',
    SHUT_WHO_SCHED: 's',
    SHUT_WHO_MOM: 'm',
    SHUT_WHO_SECDRY: 'f',
    SHUT_WHO_IDLESECDRY: 'i',
    SHUT_WHO_SECDONLY: 'F',
}


def convert_api_to_cli(attrs):
    ret = []
    for a in attrs:
        if '.' in a:
            (attribute, resource) = a.split('.')
            ret.append(api_to_cli[attribute] + resource)
        else:
            ret.append(api_to_cli[a])
    return ret
