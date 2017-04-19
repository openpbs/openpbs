/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>   
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "pbs_ecl.h"

      ecl_attribute_def ecl_svr_attr_def[] = {

   /* SRV_ATR_State */

	{
		ATTR_status,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_SvrHost */	

	{
		ATTR_SvrHost,
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_scheduling */

	{
		ATTR_scheduling,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_max_running */

	{
		ATTR_maxrun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_max_queued */

	{
		ATTR_max_queued,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_max_queued_res */

	{
		ATTR_max_queued_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_max_run */

	{
		ATTR_max_run,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_max_run_res */

	{
		ATTR_max_run_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_max_run_soft */

	{
		ATTR_max_run_soft,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_max_run_res_soft */

	{
		ATTR_max_run_res_soft,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_MaxUserRun */

	{
		ATTR_maxuserrun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_MaxGrpRun */	

	{
		ATTR_maxgrprun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_MaxUserRes */

	{
		ATTR_maxuserres,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SVR_ATR_MaxGroupRes */  

	{
		ATTR_maxgroupres,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SVR_ATR_MaxUserRunSoft */ 

	{
		ATTR_maxuserrunsoft,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_MaxGrpRunSoft */

	{
		ATTR_maxgrprunsoft,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_MaxUserResSoft */ 

	{
		ATTR_maxuserressoft,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SVR_ATR_MaxGroupResSoft */

	{
		ATTR_maxgroupressoft,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SVR_ATR_PNames */

	{
		ATTR_PNames,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_TotalJobs */

	{
		ATTR_total,
		READ_ONLY,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_JobsByState */

	{
		ATTR_count,
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_acl_host_enable */	

	{
		ATTR_aclhten,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_acl_hosts */	

	{
		ATTR_aclhost,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_acl_Resvhost_enable */

	{
		ATTR_aclResvhten,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_acl_Resvhosts */

	{
		ATTR_aclResvhost,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_acl_ResvGroup_enable */

	{
		ATTR_aclResvgren,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_acl_ResvGroups */

	{
		ATTR_aclResvgroup,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_AclUserEnabled *//* User ACL to be used */

	{
		ATTR_acluren,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_AclUsers */		/* User Acess Control List */

	{
		ATTR_acluser,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_AclResvUserEnabled */	/* User ACL for reservation requests*/

	{
		ATTR_aclResvuren,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_AclResvUsers */		/* Resv User Access Control List */

	{
		ATTR_aclResvuser,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_AclRoot */		/* List of which roots may execute jobs */

	{
		ATTR_aclroot,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_managers */

	{
		ATTR_managers,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_mgr_opr_acl_check	
	},
   /* SRV_ATR_operators */

	{
		ATTR_operators,
		MGR_ONLY_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_mgr_opr_acl_check	
	},
   /* SRV_ATR_dflt_que */

	{
		ATTR_dfltque,
		NO_USER_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_log_events */

	{
		ATTR_logevents,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_mailfrom */

	{
		ATTR_mailfrom,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_query_others */

	{
		ATTR_queryother,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_resource_avail */

	{
		ATTR_rescavail,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
  /* SRV_ATR_resource_deflt */

	{
		ATTR_rescdflt,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SVR_ATR_DefaultChunk */ 

	{
		ATTR_DefaultChunk,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SRV_ATR_ResourceMax */

	{
		ATTR_rescmax,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SRV_ATR_resource_assn */

	{
		ATTR_rescassn,
		READ_ONLY,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SRV_ATR_resource_cost */

	{
		ATTR_resccost,
		MGR_ONLY_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* SRV_ATR_sys_cost */	

	{
		ATTR_syscost,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_scheduler_iteration */	

	{
		ATTR_schedit,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_Comment */

	{
		ATTR_comment,
		NO_USER_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_DefNode */

	{
		ATTR_defnode,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_NodeOrder */	

	{
		ATTR_nodepack,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_FlatUID */

	{
		ATTR_FlatUID,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_FLicenses */

	{
		ATTR_FLicenses,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_ResvEnable */

	{
		ATTR_ResvEnable,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_NodeFailReq */

	{
		ATTR_nodefailrq,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_maxarraysize */

	{
		ATTR_maxarraysize,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_ReqCredEnable */

	{
		ATTR_ReqCredEnable,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_ReqCred */

	{
		ATTR_ReqCred,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_credname	
	},
   /* SRV_ATR_NodeGroupEnable */

	{
		ATTR_NodeGroupEnable,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_NodeGroupKey */

	{
		ATTR_NodeGroupKey,
		NO_USER_SET,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_ssignon_enable */

	{
		ATTR_ssignon_enable,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_dfltqdelargs */

	{
		ATTR_dfltqdelargs,
		NO_USER_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_dfltqsubargs */ 

	{
		ATTR_dfltqsubargs,
		NO_USER_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_rpp_retry */

	{
		ATTR_rpp_retry,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},
   /* SRV_ATR_rpp_highwater */

	{
		ATTR_rpp_highwater,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_non_zero_positive	
	},
   /* SRV_ATR_license_location */

	{
		ATTR_license_location,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_pbs_license_info */

	{
		ATTR_pbs_license_info,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_license_min */

	{
		ATTR_license_min,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_minlicenses	
	},
   /* SRV_ATR_license_max */

	{
		ATTR_license_max,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_maxlicenses	
	},
   /* SRV_ATR_license_linger */

	{
		ATTR_license_linger,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_licenselinger	
	},
   /* SRV_ATR_license_count */

	{
		ATTR_license_count,
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_version */

	{
		"pbs_version",
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_job_sort_formula */

	{
		ATTR_job_sort_formula,
		READ_WRITE,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_EligibleTimeEnable */

	{
		ATTR_EligibleTimeEnable,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_resv_retry_init */

	{
		ATTR_resv_retry_init,
		ATR_DFLAG_MGWR | ATR_DFLAG_MGRD,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},
   /* SRV_ATR_resv_retry_cutoff */

	{
		ATTR_resv_retry_cutoff,
		ATR_DFLAG_MGWR | ATR_DFLAG_MGRD,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_JobHistoryEnable */

	{
		ATTR_JobHistoryEnable,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_JobHistoryDuration */

	{
		ATTR_JobHistoryDuration,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_ProvisionEnable */	

	{
		ATTR_ProvisionEnable,
		ATR_DFLAG_SvWR|ATR_DFLAG_MGRD,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_max_concurrent_prov */

	{
		ATTR_max_concurrent_prov,
		MGR_ONLY_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_provision_timeout */	

	{
		ATTR_provision_timeout,
		ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_resv_post_processing */

	{
		ATTR_resv_post_processing,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SRV_ATR_BackfillDepth */

	{
		ATTR_backfill_depth,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},
   /* SRV_ATR_JobRequeueTimeout */

	{
		ATTR_job_requeue_timeout,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_queued_jobs_threshold */

	{
		ATTR_queued_jobs_threshold,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_queued_jobs_threshold_res */

	{
		ATTR_queued_jobs_threshold_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* SVR_ATR_jobscript_max_size */

	{
		ATTR_jobscript_max_size,
		MGR_ONLY_SET,
		ATR_TYPE_SIZE,
		verify_datatype_size,
		verify_value_non_zero_positive	
	},

	};
	int   ecl_svr_attr_size = sizeof(ecl_svr_attr_def) / sizeof(ecl_attribute_def);
