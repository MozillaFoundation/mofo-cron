from copy import deepcopy
import json
import os

from utilities import (
    get_bucket_content,
    filter_by_resources,
    s3,
    get_guidebook_content,
    PatchGuidebookContent,
    PatchGuideDescription,
    RestoreGuidebookContent,
    write_csv,
    upload_csv_to_s3,
)

S3_BUCKET = os.environ["MOZFEST_S3_BUCKET"]


def get_backup_content(backups_list):
    """
    Get the latest backup available on S3. Will be changed to the backup selected by the user in the CLI.

    :param backups_list: All backups available on S3, filtered by a Guidebook resource type
    :return: A unique backup (dict). For now, it's the latest one.
    """

    latest_backups = max(backups_list, key=lambda o: o["LastModified"])
    backup_file = s3.get_object(Bucket=S3_BUCKET, Key=latest_backups["Key"])["Body"]
    backup_file_content = json.loads(backup_file.read())

    return backup_file_content


def remove_metadata(entry):
    """
    Remove `id`, `import_id` and `created_at` fields: those fields might be different even if an element didn't
    changed (we can't control the `created_at` field for example).

    :param entry: Guidebook element in a backup or currently live on Guidebook
    :return:
    """

    metadata = ["id", "import_id", "created_at"]
    for m in metadata:
        try:
            del entry[m]
        # All guidebook resource type don't have import_id
        except KeyError:
            pass


def compare_guides(backup, guidebook_data):
    """
    Compare a backup guide and the one currently on Guidebook. Data that needs to be restored is added to a list.

    :param backup: Backup data from S3 (dict)
    :param guidebook_data: Guidebook data as it is at the time of the rollback (dict)
    :return: PatchGuideContent objects (list)
    """

    modified_entries = []

    if backup == guidebook_data:
        print(
            f"No rollback necessary for guide: No difference found between current data and backups."
        )
    else:
        modified_entries.append(PatchGuideDescription(backup))

    return modified_entries


def compare_content(backup, guidebook_data, resource_name):
    """
    Compare every elements from a resource type to its backup. Data that needs to be restored is added to a list.

    :param backup: Backup from S3 (dict)
    :param guidebook_data: Guidebook data as it is at the time of the rollback (dict)
    :param resource_name: Guidebook resource type: can be "sessions", "schedule-tracks", "locations" (dict)
    :return: PatchGuidebookContent and/or RestoreGuidebookContent (list)
    """

    # List of modifications that needs to be uploaded to Guidebook
    modified_entries = []

    # Create a copy and remove metadata: we don't want to alter the original dicts because we will need some of those
    # metadata if the backup and the data on Guidebook are different
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
        # `id` field is an int but `import_id` is a string: we need to convert `id` to be able to compare those two
        # fields.
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
                    modified_entries.append(
                        PatchGuidebookContent(
                            guidebook_element_id, resource_name, backup_element
                        )
                    )
            else:
                modified_entries.append(
                    RestoreGuidebookContent(element_id, resource_name, backup_element)
                )

    return modified_entries


def prepare_data_to_rollback():
    """
    Compare backups and data currently on Guidebook and prepare a list of data that will be restored on Guidebook.

    :return: List of changes to upload to Guidebook
    """

    # "Sessions" needs to be last: we need to update "sessions" fields with changes made in "schedule tracks" and
    # "locations".
    guidebook_resources = ["guides", "schedule-tracks", "locations", "sessions"]

    # Get all backups from S3
    backups_s3 = get_bucket_content()

    # List of changes that will be uploaded to Guidebook
    data_to_rollback = []

    for resource_type in guidebook_resources:
        all_backups = filter_by_resources(backups_s3, resource_type)
        selected_guidebook_backup = get_backup_content(all_backups)
        guidebook_current_data = get_guidebook_content(resource_type)

        if resource_type == "guides":
            changes = compare_guides(selected_guidebook_backup, guidebook_current_data)
        else:
            changes = compare_content(
                selected_guidebook_backup, guidebook_current_data, resource_type
            )

        data_to_rollback.append(changes)

    return data_to_rollback


def do_rollback(rollback_data):
    """
    Upload all changes to Guidebook.

    :param rollback_data: List of changes that need to be uploaded to Guidebook
    :return:
    """

    for guidebook_resource_type in rollback_data:
        for modification_to_apply in guidebook_resource_type:
            modification_to_apply.execute()


if __name__ == "__main__":
    # Backup data from guidebook before initiating the rollback
    # TODO uncomment
    # do_backup(rollback=True)

    # Select backup data that needs to be restored
    modifications_list = prepare_data_to_rollback()

    # Apply all the changes to Guidebook
    do_rollback(modifications_list)

    # Upload a csv of all changes that were applied
    modifications_csv = write_csv(modifications_list)
    upload_csv_to_s3(modifications_csv)


#  TODO:
# chose which backup we want to rollback to.
# Need a CLI for people to run the rollback!
