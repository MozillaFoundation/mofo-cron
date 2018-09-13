from utilities import (
    delete_old_backups,
    get_bucket_content,
    filter_by_resources,
    get_guidebook_content,
    is_stale,
    upload_to_s3,
)


# put this in an env var
guidebook_resources = ["guides", "sessions", "schedule-tracks", "locations"]


def cleanup():
    s3_previous_backups = get_bucket_content()

    # Delete backups on S3 that are older than 2 days
    delete_old_backups(s3_previous_backups)

    # Alert if no backups were uploaded during the last 3 hours
    for resource in guidebook_resources:
        filtered_previous_backups = filter_by_resources(s3_previous_backups, resource)
        is_stale(filtered_previous_backups)


def do_backup(rollback=False):
    for resource in guidebook_resources:
        guidebook_data = get_guidebook_content(resource)
        if rollback:
            upload_to_s3(resource, guidebook_data, rollback=True)
        else:
            upload_to_s3(resource, guidebook_data)


if __name__ == "__main__":
    print("Starting backups of Guidebook data")
    cleanup()
    do_backup()
    print("Backup complete")
