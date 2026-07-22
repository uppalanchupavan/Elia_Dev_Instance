##==============================================================================
#*   Launch Point NAME: SAGA_VALIDATESECWO_ONSAVE
#* 
#*   PURPOSE: To validate Secondary Incompatible WO for New Work orders
#*
#*   REVISIONS:
#*   Ver        Date              Author                             Description
#*   ---------  ---------- ---  ---------- ---------------  -----------------------------------
#*   1          29/08/2025      Pavan Uppalanchu          MAS-2670 :Manual Workorder creation rules
#*	 2          26/11/2025      Pavan Uppalanchu          MAS - 5104 To Validate Assetype and Jobplan on WOrkorder record
#*   3          29/11/2025      Pavan Uppalanchu          MAS -6408 To validat WO Incompatibilities on saving wo record 
#*   4          11/02/2026      Pavan Uppalanchu          MAS -6883 To throw warning message when saving secondary WO record if already exists 
#*
#***************************** End Standard Header ****************************
#================================================================================

# Maximo Automation Script: SAGA_VALIDATESECWO_ONSAVE (Secondary Incompatible Validation for new WO records)
# Launch Point: Object
# Triggered by: User when creating New WO record.
# Purpose: 
''' 
On workorder save, validate if there exists an incompatible workorder:
If yes, create the workorder in PA state.
Else in Approved state.
If the workorder exists with the same job plan and overlapping date,
throw an error message to the user on workorder save that- Workorder already exists with the same jobplan and the overlapping date.
'''


from java.util import Calendar, Date # Import Calendar and Date for date manipulation
from psdi.server import MXServer
from psdi.mbo import MboConstants

def normalizeDate(dateObj):
    if dateObj is None:
        return None
    cal = Calendar.getInstance()
    cal.setTime(dateObj)
    cal.set(Calendar.HOUR_OF_DAY, 0)
    cal.set(Calendar.MINUTE, 0)
    cal.set(Calendar.SECOND, 0)
    cal.set(Calendar.MILLISECOND, 0)
    return cal.getTime()

# POC Launch Point: 
if launchPoint =="EG_WORKORDER.OBJ.BEFORESAVE":
    jpnumMboSet = mbo.getMboSet("WO_REV_JOBPLAN")
    if (not jpnumMboSet.isEmpty()):
        jpLaborSet = jpnumMboSet.getMbo(0).getMboSet("JOBLABOR")
        if (not jpLaborSet.isEmpty()):
            
            counter = 0
            while (jpLaborSet.getMbo(counter)):
                jpLaborMbo = jpLaborSet.getMbo(counter)
                formulaSet = jpLaborMbo.getMboSet("EG_FORMULA")
                if(not formulaSet.isEmpty()):
                    counter2 = 0
                    while(formulaSet.getMbo(counter2)):
                        scriptName = formulaSet.getMbo(counter2).getString("EG_AUTOSCRIPT")
                        
                        service.invokeScript(scriptName)
                        counter2 = counter2+1
                counter = counter+1
                
            
if launchPoint =="SAGA_VALIDATESECWO_ONSAVE" and interactive :
    mxs = MXServer.getMXServer()
    userInfo = mbo.getThisMboSet().getUserInfo()
       
    currentWonum = mbo.getString("WONUM")
    currentJpnum = mbo.getString("JPNUM")
    currentOrgid = mbo.getString("ORGID")
    currentSiteid = mbo.getString("SITEID")

            # Get current WO's dates and normalize to Date. Igoring time.
            
    #normalizedCurrentTargetStart = normalizeDate(mbo.getDate("TARGSTARTDATE"))
    normalizedCurrentScheduleStart = normalizeDate(mbo.getDate("SCHEDSTART"))
    normalizedCurrentScheduleFinish = normalizeDate(mbo.getDate("SCHEDFINISH"))

    SecondaryWoSet = mxs.getMboSet("WORKORDER", userInfo)
            # Query WORKORDER for a record with the corresponding secondary job plan and same organization
    SecondaryWoSet.setWhere("JPNUM = '%s' AND ORGID = '%s' AND SITEID = '%s' AND (STATUS = '%s' OR STATUS = '%s')  AND WONUM != '%s' AND SAGA_PRIMARYWO IS NOT NULL  AND SAGA_PRIMARYWO !=WONUM " % (currentJpnum, currentOrgid,currentSiteid,'APPR','PA',currentWonum))
    SecondaryWoSet.reset()
    if  not SecondaryWoSet.isEmpty():
        SecondaryWoMbo = SecondaryWoSet.moveFirst()
        while SecondaryWoMbo:
            #normalizedSecondaryTargetStart = normalizeDate(SecondaryWoMbo.getDate("TARGSTARTDATE"))
            normalizedSecondaryScheduleStart = normalizeDate(SecondaryWoMbo.getDate("SCHEDSTART"))
            normalizedSecondaryScheduleFinish = normalizeDate(SecondaryWoMbo.getDate("SCHEDFINISH"))
            
            if normalizedCurrentScheduleFinish is not None and normalizedCurrentScheduleStart is not None and normalizedSecondaryScheduleFinish is not None and normalizedSecondaryScheduleStart is not None:
                if (normalizedCurrentScheduleFinish.equals(normalizedSecondaryScheduleFinish) and normalizedCurrentScheduleStart.equals(normalizedSecondaryScheduleStart)):
                    #errorgroup='workorder'
                    #errorkey ='saga_secwoerror'
                    params=[SecondaryWoMbo.getString("WONUM")]
                    service.warning("workorder", "saga_secwoerror", params)
            SecondaryWoMbo = SecondaryWoSet.moveNext()
    else:
        if mbo.isNew():
            mbo.changeStatus("APPR", MXServer.getMXServer().getDate(), "New WO APPR: [EG_WORKORDER.OBJ.BEFORESAVE]", MboConstants.NOACCESSCHECK)
            
            
                    
                    
if launchPoint == 'EG_WOINCOMPATIBILITIES':

    def check_jobplan_incompatibility():
        VALID_STATUSES = ['PA', 'APPR']
        
        current_wonum = mbo.getString("WONUM")
        currentJpnum = mbo.getString("JPNUM")
        currentOrgid = mbo.getString("ORGID")
        currentSiteid = mbo.getString("SITEID")
        current_wo_status = mbo.getString("STATUS")
        current_woassetnum = mbo.getString("ASSETNUM")
        normalizedCurrentScheduleStart = normalizeDate(mbo.getDate("SCHEDSTART"))
        normalizedCurrentScheduleFinish = normalizeDate(mbo.getDate("SCHEDFINISH"))
        
        # Lists to keep track of fields for the CURRENT WO in real-time
        current_wo_primaries = []
        current_wo_secondaries = []
        
        # --- 1. CLEANUP EXISTING ENTRIES ---
        cleanup_where = "(PRIMARYWONUM='%s' OR SECONDARYWONUM='%s') AND SITEID='%s'" % (current_wonum, current_wonum, currentSiteid)
        WOIncompatibility_cleanup_Set = mbo.getMboSet("$CLEANUP_EG_WONUMINCOMPATIBILITIES", "EG_WONUMINCOMPATIBILITIES", cleanup_where)
            
        cleanup_mbo = WOIncompatibility_cleanup_Set.moveFirst()
        while cleanup_mbo:
            cleanup_mbo.delete(MboConstants.NOACCESSCHECK)
            cleanup_mbo = WOIncompatibility_cleanup_Set.moveNext()
            
        if not currentJpnum or not normalizedCurrentScheduleStart or not normalizedCurrentScheduleFinish or not current_woassetnum or current_wo_status not in VALID_STATUSES:
            # 1. Clear fields on the CURRENT WO
            mbo.setValue("EG_PRIMARYWORKORDER", "", MboConstants.NOACCESSCHECK)
            mbo.setValue("EG_SECONDARYWORKORDER", "", MboConstants.NOACCESSCHECK)
            
            # 2. DISASSOCIATE OTHER WOs: Find any WO currently pointing to this WONUM
            disassoc_where = "(EG_PRIMARYWORKORDER LIKE '%{0}%' OR EG_SECONDARYWORKORDER LIKE '%{0}%') AND SITEID='{1}'".format(current_wonum, currentSiteid)
            other_wo_set = mbo.getMboSet("$DISASSOC_WOS", "WORKORDER", disassoc_where)
            
            other_wo = other_wo_set.moveFirst()
            while other_wo:
                # Clean the Primary list on the other WO if our WONUM is in it
                exist_prim = other_wo.getString("EG_PRIMARYWORKORDER")
                if exist_prim and current_wonum in exist_prim:
                    prim_list = [x.strip() for x in exist_prim.split(",") if x.strip() and x.strip() != current_wonum]
                    other_wo.setValue("EG_PRIMARYWORKORDER", ",".join(prim_list), MboConstants.NOACCESSCHECK)
                
                # Clean the Secondary list on the other WO if our WONUM is in it
                exist_sec = other_wo.getString("EG_SECONDARYWORKORDER")
                if exist_sec and current_wonum in exist_sec:
                    sec_list = [x.strip() for x in exist_sec.split(",") if x.strip() and x.strip() != current_wonum]
                    other_wo.setValue("EG_SECONDARYWORKORDER", ",".join(sec_list), MboConstants.NOACCESSCHECK)
                    
                other_wo = other_wo_set.moveNext()
                
            return
        
        
        # --- 2. MATCH JOB PLAN INCOMPATIBILITIES ---
        incompat_where_template = """ (PRIMARYJPNUM = '%s' OR SECONDARYJPNUM = '%s') AND ( (orgid = '%s' AND siteid = '%s') OR  (orgid = '%s' AND (siteid IS NULL OR siteid = '')) OR  ((orgid IS NULL OR orgid = '') AND (siteid IS NULL OR siteid = '')) )"""
        incompat_where = incompat_where_template % (currentJpnum, currentJpnum, currentOrgid, currentSiteid, currentOrgid)
        
        incompat_set = mbo.getMboSet("$CHECK_EG_JOBPLANINCOMPATIBILITIES", "EG_JOBPLANINCOMPATIBILITIES", incompat_where)
        
        incompat_mbo = incompat_set.moveFirst()
        while incompat_mbo:
            primary_jp = incompat_mbo.getString("PRIMARYJPNUM")
            secondary_jp = incompat_mbo.getString("SECONDARYJPNUM")
            
            conflicting_jp = ""
            if primary_jp == currentJpnum:
                conflicting_jp = secondary_jp
            elif secondary_jp == currentJpnum:
                conflicting_jp = primary_jp
            
            if conflicting_jp:
                status_in_clause = "', '".join(VALID_STATUSES)
                wo_where = "JPNUM = '%s' AND ORGID = '%s' AND SITEID = '%s' AND ASSETNUM = '%s' AND STATUS IN ('%s')" % (conflicting_jp, currentOrgid, currentSiteid, current_woassetnum, status_in_clause)
                
                wo_set = mbo.getMboSet("$CONFLICT_WO_" + conflicting_jp, "WORKORDER", wo_where)
                wo_set.setLogLargFetchResultDisabled(True)
                
                conflicting_wo_mbo = wo_set.moveFirst()
                while conflicting_wo_mbo:
                    conflicting_wonum = conflicting_wo_mbo.getString("WONUM")
                    conflicting_wo_status = conflicting_wo_mbo.getString("STATUS")
                    conflicting_wo_ScheduleStart = normalizeDate(conflicting_wo_mbo.getDate("SCHEDSTART"))
                    conflicting_wo_ScheduleFinish = normalizeDate(conflicting_wo_mbo.getDate("SCHEDFINISH"))
                    
                    if normalizedCurrentScheduleFinish.equals(conflicting_wo_ScheduleFinish) and normalizedCurrentScheduleStart.equals(conflicting_wo_ScheduleStart):
                        if conflicting_wo_status in VALID_STATUSES: 
                            if not (current_wo_status == "APPR" and conflicting_wo_status == "APPR"):
                                
                                intended_primary_wo = None
                                intended_secondary_wo = None
                                
                                if primary_jp == currentJpnum:
                                    # Current WO is Primary, Conflicting WO is Secondary
                                    intended_primary_wo = current_wonum
                                    intended_secondary_wo = conflicting_wonum
                                    if conflicting_wonum not in current_wo_secondaries:
                                        current_wo_secondaries.append(conflicting_wonum)
                                        
                                elif secondary_jp == currentJpnum:
                                    # Current WO is Secondary, Conflicting WO is Primary
                                    intended_primary_wo = conflicting_wonum
                                    intended_secondary_wo = current_wonum
                                    if conflicting_wonum not in current_wo_primaries:
                                        current_wo_primaries.append(conflicting_wonum)
                                    
                                    if interactive:
                                        # Check if another record already matches our conflict requirements
                                        chk_where = "JPNUM='%s' AND ASSETNUM='%s' AND SITEID='%s' AND STATUS IN ('%s') AND WONUM !='%s'" % (secondary_jp, current_woassetnum, currentSiteid, status_in_clause, current_wonum)
                                        dup_wo_set = mbo.getMboSet("$DUP_SEC_CHECK", "WORKORDER", chk_where)
                                        
                                        # List to catch ALL Incompatible exisitng WO records
                                        conflicting_wos_found = []                                        
                                        has_existing_secondary = False
                                        dup_wo = dup_wo_set.moveFirst()
                                        while dup_wo:
                                            d_start = normalizeDate(dup_wo.getDate("SCHEDSTART"))
                                            d_finish = normalizeDate(dup_wo.getDate("SCHEDFINISH"))
                                            dup_wo_status = dup_wo.getString("STATUS")
                                            
                                            # YOUR EXACT LOGIC: Compare Primary Status vs Existing Duplicate Status
                                            # If BOTH are APPR, they are compatible, so we skip them!
                                            if not (conflicting_wo_status == "APPR" and dup_wo_status == "APPR"):
                                                if normalizedCurrentScheduleStart.equals(d_start) and normalizedCurrentScheduleFinish.equals(d_finish):
                                                    dup_wonum = dup_wo.getString("WONUM")
                                                    if dup_wonum not in conflicting_wos_found:
                                                        conflicting_wos_found.append(dup_wonum)
                                            dup_wo = dup_wo_set.moveNext()
                                            
                                        if conflicting_wos_found:
                                            wos_display_str = ", ".join(conflicting_wos_found)
                                            # Custom duplicate warning if it matches the criteria
                                            service.setWarning("workorder", "eg_dup_secwo_error", [wos_display_str])
                                        else:
                                        
                                            params = [intended_primary_wo]
                                            service.setWarning("workorder", "saga_secwoerror", params)
                                        
                                if intended_primary_wo and intended_secondary_wo:
                                    # Write to the Incompatibility Table
                                    wo_incompat_set = mbo.getMboSet("$ADD_EG_WONUMINCOMPATIBILITIES", "EG_WONUMINCOMPATIBILITIES", "1=0")
                                    new_incompat = wo_incompat_set.add(MboConstants.NOACCESSCHECK)
                                    
                                    new_incompat.setValue("PRIMARYWONUM", intended_primary_wo, MboConstants.NOACCESSCHECK)
                                    new_incompat.setValue("SECONDARYWONUM", intended_secondary_wo, MboConstants.NOACCESSCHECK)
                                    new_incompat.setValue("ORGID", currentOrgid, MboConstants.NOACCESSCHECK)
                                    new_incompat.setValue("SITEID", currentSiteid, MboConstants.NOACCESSCHECK)
                                    
                                    # --- DIRECT UPDATE TO THE OTHER (CONFLICTING) WORK ORDER ---
                                    # This saves us from having to query the cache later.
                                    other_wo_set = mbo.getMboSet("$DIRECT_UPD_WO_" + conflicting_wonum, "WORKORDER", "WONUM='%s' AND SITEID='%s'" % (conflicting_wonum, currentSiteid))
                                    other_wo = other_wo_set.getMbo(0)
                                    if other_wo:
                                        if primary_jp == currentJpnum:
                                            # The other WO is a secondary. Update its primary reference list.
                                            exist_val = other_wo.getString("EG_PRIMARYWORKORDER")
                                            vals = [x.strip() for x in exist_val.split(",") if x.strip()] if exist_val else []
                                            if current_wonum not in vals:
                                                vals.append(current_wonum)
                                                other_wo.setValue("EG_PRIMARYWORKORDER", ",".join(vals), MboConstants.NOACCESSCHECK)
                                        else:
                                            # The other WO is a primary. Update its secondary reference list.
                                            exist_val = other_wo.getString("EG_SECONDARYWORKORDER")
                                            vals = [x.strip() for x in exist_val.split(",") if x.strip()] if exist_val else []
                                            if current_wonum not in vals:
                                                vals.append(current_wonum)
                                                other_wo.setValue("EG_SECONDARYWORKORDER", ",".join(vals), MboConstants.NOACCESSCHECK)
                    
                    conflicting_wo_mbo = wo_set.moveNext()
            
            incompat_mbo = incompat_set.moveNext()
            
        # --- 3. DIRECT UPDATE TO THE CURRENT WORK ORDER ---
        mbo.setValue("EG_PRIMARYWORKORDER", ",".join(current_wo_primaries), MboConstants.NOACCESSCHECK)
        mbo.setValue("EG_SECONDARYWORKORDER", ",".join(current_wo_secondaries), MboConstants.NOACCESSCHECK)
        
    check_jobplan_incompatibility()