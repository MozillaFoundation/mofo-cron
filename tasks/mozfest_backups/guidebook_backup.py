import json
from datetime import datetime
import os

import requests
import boto3

# GuideBook config
API_URL = "https://builder.guidebook.com/open-api/v1/"
API_KEY = os.environ["GUIDEBOOK_KEY"]
GUIDE_ID = os.environ["GUIDE_ID"]

# AWS configuration
AWS_ACCESS_KEY_ID = os.environ["MOZFEST_AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["MOZFEST_AWS_SECRET_ACCESS_KEY"]
S3_BUCKET = os.environ["MOZFEST_S3_BUCKET"]

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M")


def get_guidebook_content(guidebook_resource):
    if guidebook_resource == "guides":
        resource_url = API_URL + guidebook_resource + f"/{GUIDE_ID}"
    else:
        resource_url = API_URL + guidebook_resource + f"/?guide={GUIDE_ID}"

    r = requests.get(resource_url, headers={"Authorization": "JWT " + API_KEY})

    data = r.json()

    # pagination
    try:
        while r.json()["next"]:
            r = requests.get(
                r.json()["next"], headers={"Authorization": "JWT " + API_KEY}
            )
            data.extend(r.json())
    except KeyError:
        print(f"{guidebook_resource} doesn't have a 'next' page.")

    return data


def upload_to_s3(guidebook_resource, json_content):
    filename = f"{guidebook_resource}-{TIMESTAMP}.json"
    data = json.dumps(json_content, sort_keys=True, indent=4).encode()
    s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=data)
    print(f"Uploaded {guidebook_resource} to S3.")


# Alert: check for each file if timestamp is less than 3 hours
# Cleanup back up: only keep 48h of data and wipe the rest.

# Rollback (separate file + made to be executed locally): do a diff on what's actually on guidebook (redo a dump of everything) and last backup.
# Check if tracks, location, session are different.
# Do a intersection set with session IDs + diff
# Check what's new (new ids)
# Check what was removed (ids that are not in the backup)
# create different jsons with all changes (session updates, deletes and additions)
# do requests to guidebook

# Need a CLI for people to run the rollback!


if __name__ == "__main__":
    guidebook_resources = ["guides", "sessions", "schedule-tracks", "locations"]

    for resource in guidebook_resources:
        content = get_guidebook_content(resource)
        upload_to_s3(resource, content)
