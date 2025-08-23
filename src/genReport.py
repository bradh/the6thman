import json
from datetime import datetime
import os

# ---------- Helpers for sim movement ----------
def simulate_positions(start_lat=-27.4698, start_lon=153.0251, n=100, step_deg=0.00018):
    """
    Simulates a rough urban foot patrol path. Step is ~20m-ish at Brisbane lat (hand-wavy).
    """
    lat, lon = start_lat, start_lon
    for i in range(n):
        # weave a little to look less robotic
        lat += step_deg * (1.0 if i % 3 != 0 else 0.6)
        lon += step_deg * (0.6 if i % 4 != 0 else 1.0)
        yield (round(lat, 6), round(lon, 6))

# ---------- UID + Report objects (fixed) ----------
def genUid(cs, t):
    """
    Generates a uid for the point. Gross? Yep. Stable? Also yep.
    """
    ts = t.strftime('%Y%m%d%H%M%S%f')
    return f'{cs}-{ts}'

class newReport:
    """
    Class for creating report object with the required properties to generate the message xml.
    """
    def __init__(self, repCallsign, team):
        timeNow = datetime.now()
        self.timeStamp = timeNow.strftime('%d %H%M %b%y').upper()
        self.realTime = timeNow
        self.callsign = repCallsign
        self.teamName = team
        self.uid = genUid(repCallsign, timeNow)
        # extras for sim
        self.latitude = None
        self.longitude = None
        self.assess = None
        self.markers = []
        return

    def setAssessment(self, assessment):
        """
        Writes AI assessment onto the report.
        """
        self.assess = assessment
        return

    def setPosition(self, lat, lon):
        self.latitude = lat
        self.longitude = lon

    def addMarker(self, marker):
        self.markers.append(marker)

# ---------- Marker logic ----------
def boolish(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ('true', '1', 'yes', 'y')
    if isinstance(v, (int, float)):
        return v != 0
    return False

def buildMarkersFromAssessment(assessment_dict, lat, lon, callsign, step_idx):
    """
    Turn Gemma SA output into simple markers. Affiliation defaults to UNKNOWN (2525),
    since we’re not doing friend-foe classification here.
    """
    people = int(assessment_dict.get('peopleCount', 0) or 0)
    hostile = boolish(assessment_dict.get('hostilePresence', False))
    weapons = boolish(assessment_dict.get('weaponsDetected', False))
    hazards = boolish(assessment_dict.get('environmentalHazards', False))
    rubble = boolish(assessment_dict.get('rubblePresent', False))

    base = {
        "uid": f"{callsign}-MK-{step_idx}",
        "lat": lat,
        "lon": lon,
        "time": datetime.utcnow().isoformat() + "Z",
        # 2525/CoT vibe: unknown affiliation grounding
        "affiliation": "UNKNOWN",   # a-u-* … unknown per 2525
        "category": "GROUND",
    }

    markers = []

    # Always drop a "people" marker so you have a breadcrumb of crowd density
    markers.append({
        **base,
        "type": "people",
        "details": {"count": people},
        "title": f"People: {people}",
        "cotType": "a-u-G-INFO"  # pseudo-CoT tag for info; adjust to your schema
    })

    if hostile:
        markers.append({
            **base,
            "type": "hostilePresence",
            "details": {"hostile": True},
            "title": "Hostile presence",
            "cotType": "a-u-G-THREAT"
        })

    if weapons:
        markers.append({
            **base,
            "type": "weaponsDetected",
            "details": {"weapons": True},
            "title": "Weapons detected",
            "cotType": "a-u-G-WEAP"
        })

    if hazards:
        markers.append({
            **base,
            "type": "environmentalHazards",
            "details": {"hazards": True},
            "title": "Environmental hazard",
            "cotType": "a-u-G-HAZ"
        })

    if rubble:
        markers.append({
            **base,
            "type": "rubblePresent",
            "details": {"rubble": True},
            "title": "Rubble present",
            "cotType": "a-u-G-DEBRIS"
        })

    return markers

# ---------- Main sim loop tying it all together ----------
def main():
    repCallsign = "VIKING1"
    teamName = "Alpha"
    images_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../files/images'))

    if not os.path.exists(images_dir):
        print(f"⚠️  Directory not found: {images_dir}")
        return

    files = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
    # keep deterministic order
    files.sort()

    # walk a path with same length as file list (or loop if needed)
    path_iter = simulate_positions(n=max(1, len(files)))

    print(f"📂 Scanning directory: {images_dir}")
    for idx, file_name in enumerate(files, start=1):
        file_path = os.path.join(images_dir, file_name)
        mime_type = getMimeType(file_name)
        if not isAllowedMimeType(mime_type):
            print(f"⛔ Skipping unsupported file: {file_name} (MIME: {mime_type})")
            continue

        lat, lon = next(path_iter)

        try:
            with open(file_path, 'rb') as f:
                file_buffer = f.read()

            # Gemma analysis (JSON string expected from your function)
            raw = handleOcrUpload(file_buffer, file_name)

            # Be paranoid: ensure JSON
            assessment = raw if isinstance(raw, dict) else json.loads(raw)

            report = newReport(repCallsign, teamName)
            report.setPosition(lat, lon)
            report.setAssessment(assessment)

            # Build markers based on the assessment
            markers = buildMarkersFromAssessment(assessment, lat, lon, repCallsign, idx)
            for m in markers:
                report.addMarker(m)

            # For now, just print. Swap this for ATAK CoT XML, DB insert, MQTT, whatever.
            print(f"\n🧭 STEP {idx} @ ({lat},{lon}) :: {file_name}")
            print(f"UID: {report.uid}  TS: {report.timeStamp}")
            print("Assessment:", json.dumps(assessment, ensure_ascii=False))
            print("Markers:")
            for mk in report.markers:
                print("  -", json.dumps(mk, ensure_ascii=False))

        except Exception as e:
            print(f"💥 Failed at {file_name}: {e}")

if __name__ == "__main__":
    main()



# from datetime import datetime


#
# def genUid(cs, time):
#     """
#     Generates a uid for the point. These uid are not to any standard and is pretty gross, so feel free to fix.
#
#     Args:
#     cs (str): The callsign/name of the cliet making the report. This is set through ATAK settings
#     time (time): The raw time value for when the report was generated. This high precision and should be unique for these reports
#
#     Returns:
#     (str): The 'uid' made up of the callsign and current time
#     """
#     return f'{self.callsign}{self.realTime}'
#
# class newReport:
#     """
#     Class for creating report object with the required properties to generate the message xml.
#     """
#     def __init__(self, repCallsign, team):
#         timeNow = datetime.now()
#         self.timeStamp = timeNow.stftime('%d %H%M %b%y').upper()
#         self.realTime = timeNow
#         self.callsign = repCallsign
#         self.teamName = team
#         self.uid = genUid(repCallsign, timeNow)
#         return
#
#     def setAssessment(self, assessment):
#         """
#         Method to write AI assessment as report object property. This should probably be broken down into multiple properties
#         once we have nailed down what that will look like.
#
#         Args:
#         assessment (str): The assessment generated by the AI
#         """
#         self.assess = assessment
#         return