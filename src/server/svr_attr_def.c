/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>   
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "list_link.h"
      #include "attribute.h"
      #include "pbs_nodes.h"
      #include "svrfunc.h"
      #include "pbs_error.h"
      #include "pbs_python.h"


      long reserve_retry_init = RESV_RETRY_INIT;
      long reserve_retry_cutoff = RESV_RETRY_CUTOFF;

      attribute_def svr_attr_def[] = {


   /* SRV_ATR_State */

	{
		ATTR_status,
		decode_null,
		encode_svrstate,
		set_null,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_SvrHost */	

	{
		ATTR_SvrHost,
		decode_null,
		encode_str,
		set_null,
		comp_str,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_scheduling */

	{
		ATTR_scheduling,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		poke_scheduler,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_max_running */

	{
		ATTR_maxrun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_max_queued */

	{
		ATTR_max_queued,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_ct,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_max_queued_res */

	{
		ATTR_max_queued_res,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_max_run */

	{
		ATTR_max_run,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_max_run_res */

	{
		ATTR_max_run_res,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_max_run_soft */

	{
		ATTR_max_run_soft,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_max_run_res_soft */

	{
		ATTR_max_run_res_soft,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_MaxUserRun */

	{
		ATTR_maxuserrun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_MaxGrpRun */	

	{
		ATTR_maxgrprun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_MaxUserRes */

	{
		ATTR_maxuserres,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_MaxGroupRes */  

	{
		ATTR_maxgroupres,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_MaxUserRunSoft */ 

	{
		ATTR_maxuserrunsoft,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_MaxGrpRunSoft */

	{
		ATTR_maxgrprunsoft,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_MaxUserResSoft */ 

	{
		ATTR_maxuserressoft,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_MaxGroupResSoft */

	{
		ATTR_maxgroupressoft,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_PNames */

	{
		ATTR_PNames,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_TotalJobs */

	{
		ATTR_total,
		decode_null,
		encode_l,
		set_null,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_JobsByState */

	{
		ATTR_count,
		decode_null,
		encode_str,
		set_null,
		comp_str,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_acl_host_enable */	

	{
		ATTR_aclhten,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_acl_hosts */	

	{
		ATTR_aclhost,
		decode_arst,
		encode_arst,
		set_hostacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_acl_Resvhost_enable */

	{
		ATTR_aclResvhten,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_acl_Resvhosts */

	{
		ATTR_aclResvhost,
		decode_arst,
		encode_arst,
		set_hostacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_acl_ResvGroup_enable */

	{
		ATTR_aclResvgren,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_acl_ResvGroups */

	{
		ATTR_aclResvgroup,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_AclUserEnabled *//* User ACL to be used */

	{
		ATTR_acluren,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_AclUsers */		/* User Acess Control List */

	{
		ATTR_acluser,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_AclResvUserEnabled */	/* User ACL for reservation requests*/

	{
		ATTR_aclResvuren,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_AclResvUsers */		/* Resv User Access Control List */

	{
		ATTR_aclResvuser,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_AclRoot */		/* List of which roots may execute jobs */

	{
		ATTR_aclroot,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_managers */

	{
		ATTR_managers,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		manager_oper_chk,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_operators */

	{
		ATTR_operators,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		manager_oper_chk,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_dflt_que */

	{
		ATTR_dfltque,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		default_queue_chk,
		NO_USER_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_log_events */

	{
		ATTR_logevents,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_log_events,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_mailfrom */

	{
		ATTR_mailfrom,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_query_others */

	{
		ATTR_queryother,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_resource_avail */

	{
		ATTR_rescavail,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

  /* SRV_ATR_resource_deflt */

	{
		ATTR_rescdflt,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		action_resc_dflt_svr,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_DefaultChunk */ 

	{
		ATTR_DefaultChunk,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		deflt_chunk_action,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_ResourceMax */

	{
		ATTR_rescmax,
		decode_resc,
		encode_resc,
		set_resources_min_max,
		comp_resc,
		free_resc,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_resource_assn */

	{
		ATTR_rescassn,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_resource_cost */

	{
		ATTR_resccost,
		decode_rcost,
		encode_rcost,
		set_rcost,
		NULL_FUNC,
		free_rcost,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_sys_cost */	

	{
		ATTR_syscost,
		decode_l,
		encode_l,
		set_l,
		NULL_FUNC,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_scheduler_iteration */	

	{
		ATTR_schedit,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_Comment */

	{
		ATTR_comment,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_DefNode */

	{
		ATTR_defnode,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_NodeOrder */	

	{
		ATTR_nodepack,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_FlatUID */

	{
		ATTR_FlatUID,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_FLicenses */

	{
		ATTR_FLicenses,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_ResvEnable */

	{
		ATTR_ResvEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_NodeFailReq */

	{
		ATTR_nodefailrq,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_node_fail_requeue,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_maxarraysize */

	{
		ATTR_maxarraysize,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_ReqCredEnable */

	{
		ATTR_ReqCredEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_ReqCred */

	{
		ATTR_ReqCred,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		cred_name_okay,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_NodeGroupEnable */

	{
		ATTR_NodeGroupEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		check_for_bgl_nodes,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_NodeGroupKey */

	{
		ATTR_NodeGroupKey,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		is_valid_resource,
		NO_USER_SET,
		ATR_TYPE_ARST,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_ssignon_enable */

	{
		ATTR_ssignon_enable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		ssignon_transition_okay,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_dfltqdelargs */

	{
		ATTR_dfltqdelargs,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_dfltqsubargs */ 

	{
		ATTR_dfltqsubargs,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		force_qsub_daemons_update_action,
		NO_USER_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_rpp_retry */

	{
		ATTR_rpp_retry,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_rpp_retry,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_rpp_highwater */

	{
		ATTR_rpp_highwater,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_rpp_highwater,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_license_location */

	{
		ATTR_license_location,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_pbs_license_info */

	{
		ATTR_pbs_license_info,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		set_license_location,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_license_min */

	{
		ATTR_license_min,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_license_min,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_license_max */

	{
		ATTR_license_max,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_license_max,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_license_linger */

	{
		ATTR_license_linger,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_license_linger,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_license_count */

	{
		ATTR_license_count,
		decode_null,
		encode_str,
		set_null,
		comp_str,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_version */

	{
		"pbs_version",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_job_sort_formula */

	{
		ATTR_job_sort_formula,
		decode_formula,
		encode_str,
		set_str,
		comp_str,
		free_str,
		validate_job_formula,
		READ_WRITE,
		ATR_TYPE_STR,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_EligibleTimeEnable */

	{
		ATTR_EligibleTimeEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		eligibletime_action,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_resv_retry_init */

	{
		ATTR_resv_retry_init,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_reserve_retry_init,
		ATR_DFLAG_MGWR | ATR_DFLAG_MGRD,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_resv_retry_cutoff */

	{
		ATTR_resv_retry_cutoff,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_reserve_retry_cutoff,
		ATR_DFLAG_MGWR | ATR_DFLAG_MGRD,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_JobHistoryEnable */

	{
		ATTR_JobHistoryEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		set_job_history_enable,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_JobHistoryDuration */

	{
		ATTR_JobHistoryDuration,
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		set_job_history_duration,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_ProvisionEnable */	

	{
		ATTR_ProvisionEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR|ATR_DFLAG_MGRD,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_max_concurrent_prov */

	{
		ATTR_max_concurrent_prov,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		svr_max_conc_prov_action,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_provision_timeout */	

	{
		ATTR_provision_timeout,
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_resv_post_processing */

	{
		ATTR_resv_post_processing,
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_BackfillDepth */

	{
		ATTR_backfill_depth,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		action_backfill_depth,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},

   /* SRV_ATR_JobRequeueTimeout */

	{
		ATTR_job_requeue_timeout,
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		at_non_zero_time,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SERVER
	},
#include "site_svr_attr_def.h"
   /* SVR_ATR_queued_jobs_threshold */

	{
		ATTR_queued_jobs_threshold,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_ct,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_queued_jobs_threshold_res */

	{
		ATTR_queued_jobs_threshold_res,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_SERVER
	},

   /* SVR_ATR_jobscript_max_size */

	{
		ATTR_jobscript_max_size,
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		action_jobscript_max_size,
		MGR_ONLY_SET,
		ATR_TYPE_SIZE,
		PARENT_TYPE_SERVER
	},

	};
