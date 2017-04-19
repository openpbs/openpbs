/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

     #include <pbs_config.h>   
     #include "pbs_ifl.h"
     #include "pbs_ecl.h"

     /* ordered by guess to put ones most often used at front */

     ecl_attribute_def ecl_resv_attr_def[] = { 

   /*RESV_ATR_resv_name*/

	{
		ATTR_resv_name,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_jobname	
	},
   /*RESV_ATR_resv_owner*/

	{
		ATTR_resv_owner,
		READ_ONLY | ATR_DFLAG_SSET | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_resv_type*/

	{
		ATTR_resv_type,
		ATR_DFLAG_MGRD | ATR_DFLAG_SELEQ,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_state*/	

	{
		ATTR_resv_state,
		ATR_DFLAG_RDACC | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_substate*/	

	{
		ATTR_resv_substate,
		ATR_DFLAG_RDACC | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_reserve_Tag*/

	{
		ATTR_resv_Tag,
		ATR_DFLAG_Creat | READ_ONLY,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_reserveID*/

	{
		ATTR_resv_ID,
		ATR_DFLAG_Creat | ATR_DFLAG_SvWR | READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_start*/

	{
		ATTR_resv_start,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_end*/

	{
		ATTR_resv_end,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_duration*/

	{
		ATTR_resv_duration,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_queue*/

	{
		ATTR_queue,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resource */	

	{
		ATTR_l,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_MOM,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* RESV_ATR_SchedSelect */

	{
		ATTR_SchedSelect,
		ATR_DFLAG_MGRD,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resc_used */

	{
		ATTR_used,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resv_nodes */

	{
		ATTR_resv_nodes,
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_userlst */

	{
		ATTR_u,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_user_list	
	},
   /* RESV_ATR_grouplst */

	{
		ATTR_g,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_user_list	
	},
   /* RESV_ATR_auth_u */

	{
		ATTR_auth_u,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_authorized_users	
	},
   /* RESV_ATR_auth_g */

	{
		ATTR_auth_g,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_authorized_users	
	},
   /* RESV_ATR_auth_h */	

	{
		ATTR_auth_h,
		READ_WRITE | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_at_server */

	{
		ATTR_server,
		READ_ONLY | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_account */

	{
		ATTR_A,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_ctime */

	{
		ATTR_ctime,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_mailpnts */

	{
		ATTR_m,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_mailpoints	
	},
   /* RESV_ATR_mailuser */

	{
		ATTR_M,
		READ_WRITE | ATR_DFLAG_ALTRUN | ATR_DFLAG_SELEQ,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_mailusers	
	},
   /* RESV_ATR_mtime */

	{
		ATTR_mtime,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_hashname */

	{
		ATTR_hashname,
		ATR_DFLAG_MGRD | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_hopcount */

	{
		ATTR_hopcount,
		ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_priority */

	{
		ATTR_p,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_priority	
	},
   /* RESV_ATR_interactive */

	{
		ATTR_inter,
		READ_WRITE,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_variables */	

	{
		ATTR_v,
		READ_WRITE | ATR_DFLAG_SELEQ | ATR_DFLAG_MOM,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_euser */

	{
		ATTR_euser,
		ATR_DFLAG_MGRD,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_egroup */

	{
		ATTR_egroup,
		ATR_DFLAG_MGRD,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_convert  */ 

	{
		ATTR_convert,
		READ_WRITE,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resv_standing */ 

	{
		ATTR_resv_standing,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resv_rrule */ 

	{
		ATTR_resv_rrule,
		READ_WRITE,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /*RESV_ATR_resv_idx*/

	{
		ATTR_resv_idx,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resv_count */ 

	{
		ATTR_resv_count,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resv_execvnodes */

	{
		ATTR_resv_execvnodes,
		READ_WRITE,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_resv_timezone */

	{
		ATTR_resv_timezone,
		READ_WRITE,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* RESV_ATR_retry */

	{
		ATTR_resv_retry,
		READ_WRITE,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},

	};
	int   ecl_resv_attr_size = sizeof(ecl_resv_attr_def) / sizeof(ecl_attribute_def);
