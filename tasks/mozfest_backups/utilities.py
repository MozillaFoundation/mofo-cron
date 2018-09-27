import csv
import io
import json
import re
from datetime import datetime, timezone, timedelta
import os

import requests
import boto3

import attr

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

# Used to create backups' file name
TIMESTAMP = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M")


def get_bucket_content():
    """
    Get a list of all the files available on S3 in this bucket.

    :return: List of backups available on S3
    """

    return s3.list_objects_v2(Bucket=S3_BUCKET)["Contents"]


def get_time_diff(file):
    """
    Get the time difference between now and the `last_modified` metadata from the S3 file

    :param file: Backup on S3
    :return: Datetime object
    """

    now = datetime.now(tz=timezone.utc)
    time_diff = now - file

    return time_diff


def filter_by_resources(file_list, guidebook_resource):
    """
    Filter a list of S3 files by Guidebook resource type.

    :param file_list: List of all files on S3
    :param guidebook_resource: Guidebook resource type. Can be "guides", "sessions", "schedule-tracks" or "locations"
    :return: A list of files filtered by the Guidebook resource type passed in param
    """

    regex = re.compile(guidebook_resource)
    filtered_list = [file for file in file_list if regex.match(file["Key"])]

    return filtered_list


# Check metadata of the latest uploaded file for each type and alert if older than 3 hours
def is_stale(file_list):
    """
    Check if the file was uploaded less than 3 hours ago. If not, posted an alert in #mofo-mozfest-backup slack
    channel.

    :param file_list: List of backup files
    :return:
    """

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
    """
    Delete backups that are older than 24h.

    :param file_list: List of backups on S3
    :return:
    """

    print("Deleting files that are older than 48h")

    for file in file_list:
        time_diff = get_time_diff(file["LastModified"])
        if time_diff >= timedelta(days=1):
            print(f"Deleting {file['Key']}")
            s3.delete_object(Bucket=S3_BUCKET, Key=file["Key"])


def get_guidebook_content(guidebook_resource):
    """
    Get content (sessions, tracks, etc) from Guidebook.

    :param guidebook_resource: Guidebook resources type. Can be "guides", "sessions", "schedule-tracks" or "locations"
    :return: Content from guidebook (dict)
    """

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
    """
    Upload data from Guidebook to a S3 bucket.

    :param guidebook_resource: Guidebook resources type. Can be "guides", "sessions", "schedule-tracks" or "locations"
    :param json_content: Guidebook content
    :param rollback: If True, add `before-rollback` in front of the file name.
    :return:
    """

    if rollback:
        filename = f"before-rollback-{guidebook_resource}-{TIMESTAMP}.json"
    else:
        filename = f"{guidebook_resource}-{TIMESTAMP}.json"

    data = json.dumps(json_content).encode()
    s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=data)
    print(f"Uploaded {guidebook_resource} to S3.")


def fill_description_field(session):
    """
    Sessions' description can be empty on Guidebook website but can't be if you upload them using the API. The field
    can't be None or empty but we don't want to put a placeholder content that might never get changed. Instead,
    we use an empty paragraph html: it's not considered empty by Guidebook but it is for us.

    :param session: Element that will be uploaded to Guidebook
    :return:
    """

    if not session["description_html"]:
        session["description_html"] = "<p></p>"


def drop_locations(session):
    """
    Sessions can't be restored if they contain an location_id that doesn't exist anymore. It would have been nice to
    update to the newest id but let's drop that field for now.

    :param session: Mozfest session
    :return:
    """

    if session["locations"]:
        session["locations"] = []


def drop_schedule_tracks(session):
    """
    Deleted schedule tracks get new ids when uploaded again: we won't be able to restore a session because the
    previous id will be missing. Since schedule_tracks don't have an import_id, we drop the content from that field
    if the schedule tracks id doesn't exist anymore.

    :param session:
    :return:
    """

    # do a list with all the schedule tracks id. Check if id is in the list or not: if not, remove that element from
    #  the list.

    if session["schedule_tracks"]:
        session["schedule_tracks"] = []


@attr.s
class PatchGuideDescription(object):
    """
    Guides objects are different from other guidebook resources: they can't be created or deleted through the API.
    We can only `PATCH` them.
    """

    backup = attr.ib()

    def execute(self):
        print(f"updating data for guide")
        resource_url = API_URL + f"guides/{GUIDE_ID}/"
        requests.patch(
            resource_url, headers={"Authorization": "JWT " + API_KEY}, json=self.backup
        ).raise_for_status()


@attr.s
class PatchGuidebookContent(object):
    """
    `PATCH` a Guidebook element. Each element is composed of its Guidebook ID, a resource type (session,
    track, location) and a backup.
    """

    guidebook_element_id = attr.ib()
    guidebook_resource_name = attr.ib()
    backup_element = attr.ib()

    def execute(self):
        print(
            f"updating data for ID: {self.guidebook_element_id} ({self.guidebook_resource_name})"
        )

        if self.guidebook_resource_name == "sessions":
            fill_description_field(self.backup_element)
            drop_locations(self.backup_element)
            drop_schedule_tracks(self.backup_element)

        resource_url = (
            API_URL + self.guidebook_resource_name + f"/{self.guidebook_element_id}/"
        )
        r = requests.patch(
            resource_url,
            headers={"Authorization": "JWT " + API_KEY},
            data=self.backup_element,
        ).raise_for_status()


@attr.s
class RestoreGuidebookContent(object):
    """
    Restore a Guidebook element that was removed. The element gains an import ID to avoid duplicate if we apply
    multiple rollbacks.

    Each Guidebook element is composed of an ID, a resource type (session, track, location) and a backup.
    """

    element_id = attr.ib()
    guidebook_resource_name = attr.ib()
    backup_element = attr.ib()

    def execute(self):
        print(
            f"Sending data for ID: {self.element_id} ({self.guidebook_resource_name})"
        )
        self.backup_element["import_id"] = self.element_id

        if self.guidebook_resource_name == "sessions":
            fill_description_field(self.backup_element)
            drop_locations(self.backup_element)
            drop_schedule_tracks(self.backup_element)

        resource_url = API_URL + self.guidebook_resource_name + "/"
        r = requests.post(
            resource_url,
            headers={"Authorization": "JWT " + API_KEY},
            data=self.backup_element,
        )
        print("Content:", r.content)
        r.raise_for_status()
        # todo .raise_for_status()


def write_csv(list_of_changes):
    """
    Take a list of rolled-back Guidebook elements and convert it in csv.

    :param list_of_changes: list of rolled-back Guidebook elements
    :return:
    """

    rows = []
    first_row = ["Type", "name"]
    rows.append(first_row)

    for guidebook_resources_type in list_of_changes:
        for e in guidebook_resources_type:
            if e:
                row = [e.guidebook_resource_name, e.backup_element["name"]]
                rows.append(row)

    data_to_upload = io.StringIO()

    csvwriter = csv.writer(
        data_to_upload, delimiter=",", quotechar="|", quoting=csv.QUOTE_MINIMAL
    )

    csvwriter.writerows(rows)

    return data_to_upload.getvalue()


def upload_csv_to_s3(data):
    """
    Upload a csv file to S3 containing the name and type of rolled-back Guidebook elements.

    :param data: String of rolled back Guidebook elements.
    :return:
    """

    filename = f"entries-modified-{TIMESTAMP}.csv"

    print(f"Uploading {filename} to {S3_BUCKET}")
    s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=data)
    print("Upload done!")
