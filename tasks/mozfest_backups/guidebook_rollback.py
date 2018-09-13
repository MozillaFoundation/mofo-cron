import json
import os
from utilities import (
    get_bucket_content,
    filter_by_resources,
    s3,
    get_guidebook_content,
    upload_to_guidebook,
)

S3_BUCKET = os.environ["MOZFEST_S3_BUCKET"]

# Put this in an env var
guidebook_resources = ["guides", "sessions", "schedule-tracks", "locations"]

# Get the latest file for now
def get_backup_content(backups_list):
    latest_backups = max(backups_list, key=lambda o: o["LastModified"])
    backup_file = s3.get_object(Bucket=S3_BUCKET, Key=latest_backups["Key"])["Body"]
    backup_file_content = json.loads(backup_file.read())

    return backup_file_content


if __name__ == "__main__":
    # get files from S3
    backups_s3 = get_bucket_content()

    # Backup data from guidebook before initiating the rollback

    for resource in guidebook_resources:
        all_backups = filter_by_resources(backups_s3, resource)
        guidebook_backup = get_backup_content(all_backups)
        guidebook_current_data = get_guidebook_content(resource)
        if guidebook_backup == guidebook_current_data:
            print(
                f"No rollback necessary for {resource}: No difference found between current data and backups."
            )
        else:
            upload_to_guidebook(guidebook_backup, resource, guidebook_current_data)


#  TODO:
# chose which backup we want to rollback to.
# Create a diff of everything that happened to send to people who actually knows the schedule :D
# Do a backuop before rollback

# Need a CLI for people to run the rollback!
