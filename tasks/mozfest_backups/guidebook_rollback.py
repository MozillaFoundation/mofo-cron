from copy import deepcopy
import json
import os

from guidebook_backup import do_backup
from utilities import (
    get_bucket_content,
    filter_by_resources,
    s3,
    get_guidebook_content,
    patch_guide,
    patch_guidebook_content,
    restore_guidebook_content,
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


def remove_metadata(entry):
    metadata = ["id", "import_id", "created_at"]
    for m in metadata:
        try:
            del entry[m]
        # All guidebook resources don't have import_id
        except KeyError:
            pass


#
def is_different(backup, guidebook_data, resource_name):
    if resource_name == "guides":
        if backup == guidebook_data:
            print(
                f"No rollback necessary for {resource_name}: No difference found between current data and backups."
            )
        else:
            patch_guide(backup)
    else:
        # Create a copy and remove metadata: we don't want to alter the original dicts because we will need some of those metadata if the backup and the data on Guidebook are different
        backup_without_metadata = deepcopy(backup)
        guidebook_data_without_metadata = deepcopy(guidebook_data)

        for e in backup_without_metadata:
            remove_metadata(e)
        for e in guidebook_data_without_metadata:
            remove_metadata(e)

        if backup_without_metadata == guidebook_data_without_metadata:
            print(
                f"No rollback necessary for {resource_name}: No difference found between current data and backups."
            )
        else:
            # Id field converted to string to make it comparable with "import_id"
            guidebook_elements_by_id = {
                (str(e["import_id"]) if e.get("import_id") else str(e["id"])): e
                for e in guidebook_data
            }

            for backup_element in backup:
                element_id = str(backup_element["id"])

                if element_id in guidebook_elements_by_id:
                    guidebook_element = guidebook_elements_by_id[element_id]
                    guidebook_element_id = guidebook_element["id"]

                    remove_metadata(guidebook_element)
                    remove_metadata(backup_element)

                    if guidebook_element == backup_element:
                        pass
                    else:
                        patch_guidebook_content(
                            guidebook_element_id, resource_name, backup_element
                        )
                else:
                    restore_guidebook_content(element_id, resource_name, backup_element)


if __name__ == "__main__":
    # get files from S3
    backups_s3 = get_bucket_content()

    # Backup data from guidebook before initiating the rollback
    do_backup(rollback=True)

    for resource in guidebook_resources:
        all_backups = filter_by_resources(backups_s3, resource)
        guidebook_backup = get_backup_content(all_backups)
        guidebook_current_data = get_guidebook_content(resource)
        is_different(guidebook_backup, guidebook_current_data, resource)

#  TODO:
# chose which backup we want to rollback to.
# Create a diff of everything that happened to send to people who actually knows the schedule :D
# Do a backuop before rollback

# Need a CLI for people to run the rollback!
