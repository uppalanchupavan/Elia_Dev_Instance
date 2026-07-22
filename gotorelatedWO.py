##==============================================================================
#*   Launch Point NAME: EG_ASSET_GOTO_WOTRACK
#* 
#*   PURPOSE: To implement GO TO WOTRACK button in list Tab. On clicking the button, system should move 
#*            from ASSET to WOTRACK app list tab.   The system should display the list of WOs based on ASSET available in asset resultSet
#*
#*   REVISIONS:
#*   Ver        Date              Author                             Description
#*   ---------  ---------- ---  ---------- ---------------  -----------------------------------
#*   1          29/08/2025      Ayushi B                    To implement a GOTOWOTRACK button
#*   2          15/06/2026      Pavan Uppalanchu            To modify the logic on assetWhereClause:
#*
#***************************** End Standard Header ****************************
#================================================================================

from psdi.util.logging import MXLoggerFactory
from java.net import URLEncoder
from java.text import SimpleDateFormat
from java.util import Date
from psdi.mbo import MboConstants
from psdi.server import MXServer

logger = MXLoggerFactory.getLogger("maximo.autoscript")
logger.info("===== ASSET → GO TO WORK ORDER ACTION STARTED =====")

# -------------------------------------------------
# 1. Get Web Client Context
# -------------------------------------------------
wcs = service.webclientsession()
currentApp = wcs.getCurrentApp()
resultsBean = currentApp.getResultsBean()
user = wcs.getUserInfo().getUserName() # Fetch user safely from session context

# -------------------------------------------------
# 2. Get the user's current WHERE clause from Asset list tab
# -------------------------------------------------
# getUserWhere() retrieves the exact filter applied by the user in the list view
assetUserWhere = resultsBean.getCompleteWhere()
logger.info("Retrieved Asset list where clause: %s" % assetUserWhere)

# -------------------------------------------------
# 3. Build Work Order WHERE clause using a subquery
# -------------------------------------------------
# If the user hasn't filtered anything, assetUserWhere might be None or empty

if len(assetUserWhere) >3950:
    params = ['The Current Query cannot be auto saved. The length of Query is ' + str(len(assetUserWhere))+'. \nPlease reduce Where Clause length less than 3950 charecters' ]
    service.error('eg_advsearch','eg_assetadvsearchresultset',params)
if assetUserWhere and assetUserWhere.strip():
    # Wrap the asset where clause into a subquery for work orders
    whereClause = "assetnum in (select assetnum from asset where (%s))" % assetUserWhere
else:
    # Optional: If you want to block them from moving over without a filter,
    # uncomment the next line. Otherwise, it brings over all WOs.
    # service.error("custom", "NoAssetsInListView")
    whereClause = "assetnum in (select assetnum from asset)"

# If your target Work Order application requires a site restriction, 
# you can append it here if needed, e.g.:
# whereClause += " and siteid = '" + currentApp.getAppBean().getMbo().getString("SITEID") + "'"

logger.info("Generated WO target where clause: %s" % whereClause)

# -------------------------------------------------
# 4. SAVE QUERY IN QUERY TABLE
# -------------------------------------------------

if not resultsBean.getMboSet().isEmpty():
    fmt = SimpleDateFormat("yyyy-MM-dd_HH-mm-ss")
    timestamp = fmt.format(Date())

    filterName = "FILTER_{}_{}".format(timestamp, user)
    clauseName = "auto_saved_{}_{}".format(user, timestamp)
    logger.info("Creating saved query: " + filterName)

    if assetUserWhere:
        queryMboSet = MXServer.getMXServer().getMboSet("QUERY", mbo.getUserInfo())
        queryMbo = queryMboSet.add()
        queryMbo.setValue("APP", "ASSET", 11L)
        queryMbo.setValue("CLAUSENAME", filterName, 11L)
        queryMbo.setValue("OWNER", user, 11L)
        queryMbo.setValue("DESCRIPTION", clauseName, 11L)
        queryMbo.setValue("CLAUSE", assetUserWhere, 11L)
        queryMboSet.save()
        queryMboSet.close()
        logger.info("Saved query created successfully")
    else:
        logger.info("Could not save query; list view is completely empty or Mbo is unavailable.")

    # -------------------------------------------------
    # 5. Encode and Navigate to Work Order Tracking
    # -------------------------------------------------
    encodedWhere = URLEncoder.encode(whereClause, "UTF-8")

    finalUrl = (
        "/maximo/oslc/graphite/manage-shell/index.html"
        "?event=loadapp"
        "&value=wotrack"
        "&additionalevent=sqlwhere"
        "&additionaleventvalue=" + encodedWhere
    )

    wcs.gotoApplink(finalUrl)

    logger.info("Navigation triggered to WOTRACK with URL-encoded where clause.")
    logger.info("===== ASSET → GO TO WORK ORDER ACTION COMPLETED =====")