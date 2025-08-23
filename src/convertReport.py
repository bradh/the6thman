import os

def convRepToXml(reportObj):
    VERS = '2.0'
    HOW = 'm-g'
    CE = '10'
    LE = '10'
    LIFESPAN = 10 /60/24 # 10 minutes !To discuss!
    uid = reportObj.uid
    sym = 'a-s-G'
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

def convRepToCsv(reportObj, filePath):
    """
    Function that turns a report object into a new row within a csv file. This allows for long term storage of reports and
    archiving.

    Args:
    reportObj (report obj): A report object that was created using the newReport class in genReport.py
    filePath (str): The path to the csv to be created or edited
    """
    if os.path.isfile(filePath): # If the audit file already exists
        fileObj = open(filePath, 'r+') # Open the file in append mode so nothing is overwritten
    else: # If the audit file doesn't exist yet
        fileObj = open(filePath, 'x')
        columns = [
            'timeStamp',    #00
            'realTime',     #01
            'callsign',     #02
            'teamName',     #03
            'uid',          #04
        ]
        fileObj.write('\t'.join(columns)+'\n')
    values =[
        reportObj.timeStamp,#00
        reportObj.realTime, #01
        reportObj.callsign, #02
        reportObj.teamName, #03
        reportObj.uid,      #04
    ]
    fileObj.write('\t'.join(values)+'\n')
    fileObj.close()

    return
