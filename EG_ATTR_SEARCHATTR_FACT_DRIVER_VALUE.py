##==============================================================================
#*   Launch Point NAME: EG_ATTR_SEARCHATTR_FACT_DRIVER_VALUE
#* 
#*   PURPOSE: To build WhereClause for Assettype/Spec/Factors
#*
#*   REVISIONS:
#*   Ver        Date              Author                             Description
#*   ---------  ---------- ---  ---------- ---------------  -----------------------------------
#*   1          29/12/2025      Pavan Uppalanchu          MAS-6743 :Advance Filter for Asset Application
#*   2          06/07/2026      Pavan Uppalanchu        Rev 1 : Getting distinct values for Factors and Drivers
#*
#***************************** End Standard Header ****************************

from psdi.mbo import MboConstants
from psdi.server import MXServer
from psdi.security import ConnectionKey
from psdi.util import MXException
from java.sql import SQLException
 
wcs = service.webclientsession()
app = wcs.getCurrentApp()
appBean = app.getAppBean()
appName = service.webclientsession().getCurrentAppId()
 
#AssetType= appBean.getQbe ("ASSETTYPE").upper()

        
if launchPoint =="EG_FACTOR_DRIVER_VALUE":
    if appName == "asset" and app.onListTab():
        
        # Get input values
        field = "EG_FACTOR_DRIVER_VALUE"
        fieldValue = mbo.getString('EG_DRIVER_OR_FACTOR_DESC')
        site = mbo.getUserInfo().getInsertSite()
        asset_type = mbo.getString("EG_ASSETTYPE")
        
        # Convert to uppercase if not None
        if site:
            site = site.upper()
        if asset_type:
            asset_type = asset_type.upper()
        if field and field.strip() != ""  and asset_type:
            # Initialize connection variables
            conn = None
            stmt = None
            try:

                service.log("=== START: Field=" + field + ", Site=" + str(site) + ", Type=" + asset_type)
                # ================================================================
                # STEP 0: Cleanup existing cache records
                # ================================================================
                distinctValues_cleanup_Set = MXServer.getMXServer().getMboSet("EG_SEARCHATTRDISTINCTVALUE", mbo.getUserInfo())
                cleanup_where = "EG_FIELDNAME = '" + field.replace("'", "''") + "'"
                distinctValues_cleanup_Set.setWhere(cleanup_where)
                if not distinctValues_cleanup_Set.isEmpty():
                    service.log("Deleting " + str(distinctValues_cleanup_Set.count()) + " existing cache records")
                    distinctValues_cleanup_Set.deleteAll()
                    distinctValues_cleanup_Set.save()
                distinctValues_cleanup_Set.close()
                service.log("Starting sync for field: " + field)
                # ================================================================
                # Get database connection (ONCE at the beginning)
                # ================================================================
                mxServer = MXServer.getMXServer()
                connectionKey = mxServer.getSystemUserInfo().getConnectionKey()
                conn = mxServer.getDBManager().getConnection(connectionKey)
                if conn is None:
                    raise Exception("Failed to obtain database connection")
                service.log("Database connection established successfully")
                # ================================================================
                # STEP 1: Determine which sites to process
                # ================================================================
                sites_to_process = []
                if site and site.strip() != "":
                    sites_to_process.append(site.strip())
                    service.log("Processing single site: " + site)
                else:
                    service.log("No SITEID provided - processing all sites")
                    # Query to get all sites
                    site_sql = "SELECT DISTINCT SITEID FROM MAXIMO.ASSET WHERE SITEID IS NOT NULL AND ASSETTYPE = '" + asset_type.replace("'", "''") + "' ORDER BY SITEID"
                    stmt_sites = conn.createStatement()
                    rs = stmt_sites.executeQuery(site_sql)
                    while rs.next():
                        site_id = rs.getString(1)
                        if site_id and site_id.strip():
                            sites_to_process.append(site_id.strip().upper())
                    rs.close()
                    stmt_sites.close()
                    service.log("Found " + str(len(sites_to_process)) + " sites to process")
                # ================================================================
                # STEP 2: Batch insert using INSERT INTO ... SELECT
                # ================================================================
                total_inserted = 0
                for current_site in sites_to_process:
                    service.log("=== Processing site: " + current_site)
                    try:
                        siteSet = MXServer.getMXServer().getMboSet("SITE", mbo.getUserInfo())
                        siteSet.setWhere("SITEID='" + current_site.replace("'", "''") + "'")
                        siteSet.reset()
                        orgid = None
                        if not siteSet.isEmpty():
                            orgid = siteSet.getMbo(0).getString("ORGID")
                        siteSet.close()
                        
                        asset_sub_where = "WHERE SITEID = '" + current_site.replace("'", "''") + "' AND ASSETTYPE = '" + asset_type.replace("'", "''") + "'"
                        factor_driver_desc_where = " WHERE DESCRIPTION = '" + fieldValue.replace("'", "''") + "' "
                        target_asset_type_val = "'" + asset_type.replace("'", "''") + "'"
                        
                        # ============================================================
                        # Batch INSERT with sequence and duplicate prevention
                        # ============================================================
                        
                        insert_union_sql = """
INSERT INTO MAXIMO.EG_SEARCHATTRDISTINCTVALUE 
(EG_SEARCHATTRDISTINCTVALUEID, EG_FIELDNAME, EG_FIELDVALUE, EG_DRIVER_FACTOR_VALUE, SITEID, ORGID, ASSETTYPE, HASLD)
SELECT 
    NEXT VALUE FOR MAXIMO.EG_SEARCHATTRDISTINCTVALUEIDSE AS EG_SEARCHATTRDISTINCTVALUEID,
    '{field}' AS EG_FIELDNAME,
    '{fieldValue}' AS EG_FIELDVALUE,
    UNIFIED_DATA.VALUE AS EG_DRIVER_FACTOR_VALUE,
    '{site}' AS SITEID,
    '{orgid}' AS ORGID,
    {target_asset_type} AS ASSETTYPE,
    0 AS HASLD
FROM (
    /* Table source 1: Factors */
    SELECT DISTINCT VALUE AS VALUE
    FROM MAXIMO.AHFACTORSCORE
    WHERE VALUE IS NOT NULL and OWNERRECORDID IN (
            SELECT ASSETID FROM MAXIMO.ASSET {asset_sub} )
     AND FACTORID IN (SELECT FACTORID FROM MAXIMO.AHFACTORLIB {factor_driver_desc} )
    
    UNION
    
    /* Table source 2: Drivers */
    SELECT DISTINCT VALUE AS VALUE FROM MAXIMO.AHDRIVERSCORE
    WHERE VALUE IS NOT NULL and OWNERRECORDID IN (
        SELECT ASSETID FROM MAXIMO.ASSET {asset_sub} )
     AND DRIVERID IN (SELECT DRIVERID FROM MAXIMO.AHDRIVERLIB {factor_driver_desc} )
    
    UNION
    
    /* Table source 3: Methodology */
    SELECT DISTINCT VALUE AS VALUE
    FROM MAXIMO.AHDRIVERSCORE
    WHERE VALUE IS NOT NULL and OWNERRECORDID IN (
        SELECT ASSETID FROM MAXIMO.ASSET {asset_sub} )
     AND DRIVERID IN (SELECT METHODNAME FROM MAXIMO.AHMETHODOLOGY {factor_driver_desc} )
    
) UNIFIED_DATA
""".format(
    field=field.replace("'", "''"), 
    fieldValue=fieldValue.replace("'", "''"),  # Added to prevent KeyError
    site=current_site, 
    orgid=orgid, 
    target_asset_type=target_asset_type_val, 
    asset_sub=asset_sub_where,
    factor_driver_desc=factor_driver_desc_where
)
                        
                        # Log SQL for debugging
                        service.log("Executing INSERT for site: " + current_site)
                        # Execute INSERT
                        stmt_insert = conn.createStatement()
                        inserted_count = stmt_insert.executeUpdate(insert_union_sql)
                        stmt_insert.close()
                        # Commit after each site
                        conn.commit()
                        total_inserted += inserted_count
                        service.log("Site " + current_site + ": Inserted " + str(inserted_count) + " records")
                    except SQLException, sql_error:
                        service.log("SQL Error processing site " + current_site + ": " + str(sql_error.getMessage()))
                        try:
                            conn.rollback()
                        except:
                            pass
                        continue
                    except Exception, general_error:
                        service.log("Error processing site " + current_site + ": " + str(general_error))
                        continue
                service.log("=== COMPLETE: Total " + str(total_inserted) + " records inserted across all sites")
                # Display success message
            except SQLException, main_sql_error:
                if conn is not None:
                    try:
                        conn.rollback()
                    except:
                        pass
                error_msg = "SQL Error: " + str(main_sql_error.getMessage())
                service.log(error_msg)
            except Exception, main_error:
                if conn is not None:
                    try:
                        conn.rollback()
                    except:
                        pass
                error_msg = "Error: " + str(main_error)
                service.log(error_msg)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                        service.log("Database connection closed")
                    except Exception, close_error:
                        service.log("Failed to close connection: " + str(close_error))
                        
            domainid = 'EG_ASSTDISTINCTVAL'
            listWhere = " EG_FIELDNAME = 'EG_FACTOR_DRIVER_VALUE' "
        else:
            domainid = 'EG_ASSTDISTINCTVAL'
            listWhere = " 1=2 "