import json
import re
from datetime import datetime, timezone, timedelta
import os

import requests
import boto3

# VictorOps configuration
VICTOROPS_KEY = os.environ["VICTOROPS_KEY"]

# GuideBook configuration
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


TIMESTAMP = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M")


def get_bucket_content():
    return s3.list_objects_v2(Bucket=S3_BUCKET)["Contents"]


def get_time_diff(file):
    now = datetime.now(tz=timezone.utc)
    time_diff = now - file

    return time_diff


def filter_by_resources(file_list, guidebook_resource):
    regex = re.compile(guidebook_resource)
    filtered_list = [file for file in file_list if regex.match(file["Key"])]

    return filtered_list


# Check metadata of the latest uploaded file for each type and alert if older than 3 hours
def is_stale(file_list):
    latest_file = max(file_list, key=lambda o: o["LastModified"])

    time_diff = get_time_diff(latest_file["LastModified"])

    if time_diff >= timedelta(hours=3):
        payload = {
            "message_type": "CRITICAL",
            "entity_id": "MozfestBackupScript",
            "entity_display_name": f"Mozfest backup task failed: {latest_file['Key']} was not updated for {time_diff}",
            "state_message": f"The scheduled task in charge of Mozfest Guidebook backups failed: {latest_file['Key']} "
            f"was not updated for {time_diff}."
            f"This task is running on the Heroku app 'mofo-cron' and is a 'clock' process."
            f"Backups are uploaded to S3, in the '{S3_BUCKET}' bucket in mofo-project."
            f"Logs are available on Logentries: "
            f"https://eu.logentries.com/app/3aae5f3f#/search/log/628eb861?last=Last%2020%20Minutes",
        }
        requests.post(
            f"https://alert.victorops.com/integrations/generic/20131114/alert/{VICTOROPS_KEY}",
            json=payload,
        )
        print(
            f"Failure: the file '{latest_file['Key']}' was not updated for {time_diff}. An alert has been sent."
        )


def delete_old_backups(file_list):
    print("Deleting files that are older than 48h")

    for file in file_list:
        time_diff = get_time_diff(file["LastModified"])
        if time_diff >= timedelta(days=2):
            print(f"Deleting {file['Key']}")
            s3.delete_object(Bucket=S3_BUCKET, Key=file["Key"])


def get_guidebook_content(guidebook_resource):
    # Guides don't have 'next' or 'results' keys
    if guidebook_resource == "guides":
        resource_url = API_URL + guidebook_resource + f"/{GUIDE_ID}"
        r = requests.get(resource_url, headers={"Authorization": "JWT " + API_KEY})
        return r.json()

    else:
        resource_url = API_URL + guidebook_resource + f"/?guide={GUIDE_ID}"
        r = requests.get(resource_url, headers={"Authorization": "JWT " + API_KEY})
        data = r.json()["results"]

        # pagination
        while r.json()["next"]:
            r = requests.get(
                r.json()["next"], headers={"Authorization": "JWT " + API_KEY}
            )
            data.extend(r.json()["results"])

        return data


def upload_to_s3(guidebook_resource, json_content, rollback=False):
    if rollback:
        filename = f"{guidebook_resource}-{TIMESTAMP}-before-rollback.json"
    else:
        filename = f"{guidebook_resource}-{TIMESTAMP}.json"

    data = json.dumps(json_content).encode()
    s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=data)
    print(f"Uploaded {guidebook_resource} to S3.")


def patch_guide(backup):
    resource_url = API_URL + f"guides/{GUIDE_ID}/"
    requests.patch(
        resource_url, headers={"Authorization": "JWT " + API_KEY}, json=backup
    ).raise_for_status()
    print(f"rollback of {guidebook_resource} done!")


def patch_guidebook_content(guidebook_element_id, guidebook_resource, backup_element):
    print(f"updating data for {guidebook_element_id}")
    resource_url = API_URL + guidebook_resource + f"/{guidebook_element_id}/"
    requests.patch(
        resource_url, headers={"Authorization": "JWT " + API_KEY}, data=backup_element
    ).raise_for_status()
    print(f"rollback of {guidebook_resource} done!")


def restore_guidebook_content(element_id, guidebook_resource, backup_element):
    print(f"Sending data {element_id}")
    backup_element["import_id"] = element_id
    resource_url = API_URL + guidebook_resource + "/"
    requests.post(
        resource_url, headers={"Authorization": "JWT " + API_KEY}, data=backup_element
    ).raise_for_status()
    print(f"rollback of {guidebook_resource} done!")
