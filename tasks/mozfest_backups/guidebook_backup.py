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

# Get the bucket content and delete backups older than 2 days
bucket_content = get_bucket_content()
delete_old_backups(bucket_content)

# For each Guidebook resource, check if the data is stale and upload new backups
for resource in guidebook_resources:
    filtered_content = filter_by_resources(bucket_content, resource)
    is_stale(filtered_content)
    guidebook_content = get_guidebook_content(resource)
    upload_to_s3(resource, guidebook_content)
