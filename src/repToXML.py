def convertReport(reportObj):
    VERS = '2.0'
    HOW = 'm-g'
    CE = '10'
    LE = '10'
    LIFESPAN = 10 /60/24 # 10 minutes !To discuss!
    uid = reportObj.uid
    sym = reportObj.symbol
    ToR = reportObj.realTime
    point = reportObj.geometry
    x,y,z = point.x, point.y, point.z
    timestamp = reportObj.timeStamp
    callsign = reportObj.callsign
    team = reportObj.team
    gtpAssesment = reportObj.assess

    return (
        f"""<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
        <event version='{VERS}' uid='{uid}' type='{sym}' time='{ToR}' start='{ToR}' stale='{ToR+LIFESPAN}' how='{HOW}'>
            <point lat='{y}' lon='{x}' hae='{z}' ce='{CE}' le='{LE}' />
            <detail>
                <timestamp='{timestamp}'/>
                <callsign='{callsign}'/>
                <team='{team}'>
                <description='{gtpAssesment}'>
            </detail>
        </event>
        """)