import json
from datetime import datetime
import requests
import os

# GuideBook config
API_URL = "https://builder.guidebook.com/open-api/v1/"
API_KEY = os.environ["GUIDEBOOK_KEY"]
GUIDE_ID = os.environ["GUIDE_ID"]

TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M")


def get_guidebook_content(guidebook_resource):
    resource_url = API_URL + guidebook_resource + f"/?guide={GUIDE_ID}"
    r = requests.get(resource_url, headers={"Authorization": "JWT " + API_KEY})

    data = r.json()

    # pagination
    while r.json()["next"]:
        r = requests.get(r.json()["next"], headers={"Authorization": "JWT " + API_KEY})
        data.extend(r.json())

    return data


# TODO: actually upload those files XD
def upload_to_s3(guidebook_resource, json_content):
    with open(f"{guidebook_resource}-{TIMESTAMP}.json", "w") as f:
        json.dump(json_content, f, sort_keys=True, indent=4)


# Rollback: do a diff on what's actually on guidebook (redo a dump of everything) and last backup.
# Check if tracks, location, session are different.
# Do a intersection set with session IDs + diff
# Check what's new (new ids)
# Check what was removed (ids that are not in the backup)
# create different jsons with all changes (session updates, deletes and additions)
# do requests to guidebook

# Need a CLI for people to run the rollback!


if __name__ == "__main__":
    guidebook_resources = ["sessions", "schedule-tracks", "locations"]

    for resource in guidebook_resources:
        content = get_guidebook_content(resource)
        upload_to_s3(resource, content)
