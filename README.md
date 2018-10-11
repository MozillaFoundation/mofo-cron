# MoFo Cron

A collection of tasks that we wish to run at regular intervals. These tasks are run using the Heroku Scheduler addon.

## Tasks

### tasks/create_image.js

This task creates an image from the specified instance.

Usage: `node tasks/create_image {region} {instanceId} {Name} {DayOfWeek} {NoReboot} {DryRun}`

* region - AWS region to use
* instanceId - id of the EC2 instance an image should be made of
* Name - a name for the image, which will have the date appended to it
* DayOfWeek - specify to only run the createImage command on a specific day. Compares the provided value with `(new Date()).getDay()`, so this value should be between 1 and 7, inclusive.
* NoReboot - optional, true|false - default false - shutdown the instance to image it and then reboot
* DryRun - optional, true|false - default false - Don't actually create the image, but check to make sure it would work.

Additionally, ACCESS_KEY_ID and SECRET_ACCESS_KEY must be defined in the environment, and the IAM user associated with it must have the following policy in order to work:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "Stmt46546898700000",
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "ec2:CreateSnapshot",
                "ec2:CreateImage"
            ],
            "Resource": [
                "*"
            ]
        }
    ]
}
```

### tasks/clone_foundation_site/task.sh

This task copies the production foundation site data to staging, scrubbing the database of non-staff accounts and sessions during the process.

Usage: `./tasks/clone_foundation_site/task.sh`

To run it only on Monday, add the `--only-monday` flag.

The following environment variables must be defined:
- `STAGING_APP_NAME` The target of the database restoration
- `PRODUCTION_APP_NAME` The app whose database should be snapshotted for restoration
- `AWS_ACCESS_KEY_ID` The AWS Access Key to use when snycing the S3 buckets
- `AWS_SECRET_ACCESS_KEY` The AWS Secret Access Key to use when syncing the S3 buckets
- `STAGING_S3_BUCKET` The target bucket for the sync step
- `PRODUCTION_S3_BUCKET` The source bucket for the sync step
- `STAGING_S3_PREFIX` The bucket prefix to use when syncing, for the target bucket
- `PRODUCTION_S3_PREFIX` The bucket prefix to use when syncing, for the target bucket
- `S3_REGION` The S3 region containing the bucket

### tasks/mozfest_backups

This task create a hourly backup of Mozfest Guidebook. It gets content for `sessions`, `schedule-tracks`, `guides`, `locations` and upload it to a S3 bucket (`mofo-projects` profile, name of the bucket available as an env var on Heroku).
Backups older than a day are automatically deleted.

Dependencies listed on `Pipefile`.

Usage: `python tasks/mozfest_backups/guidebook_backup.py`

The following environment variables must be defined:
- `GUIDEBOOK_KEY` The Guidebook API key
- `GUIDE_ID` The Guidebook guide id: determines which guide will be backup or restored
- `MOZFEST_AWS_ACCESS_KEY_ID` The AWS Access Key to use when uploading, getting or deleting content from S3 bucket
- `MOZFEST_AWS_SECRET_ACCESS_KEY` The AWS Secret Access Key to use when uploading, getting or deleting content from S3 bucket
- `MOZFEST_S3_BUCKET` The bucket where backups are uploaded
- `VICTOROPS_KEY` VictorOps routing key

#### Rollback

It's possible to restore Guidebook data:
- Manually using the json files stored on S3: it's useful if only a few Guidebook entries need to be restored,
- Automatically using the backup CLI tool. It will rollback everything to a certain point in time. It won't be able to link restored sessions to a location and/or a track and won't delete new entries that were added after that certain point in time. This tool is to be used in case someone wipes Mozfest guidebook by accident or delete a substantial part of it.

if you want to make a manual restoration, but don't have access to the S3 bucket, ask Cade (cade@mozillafoundation.org) or Patjouk (lucied@mozillafoundation.org) by email or slack.

To run the automatic restoration:
- clone this repo,
- run `pipenv install`,
- copy the `env.dist` file to an `.env` and fill it,
- run `pipenv run python tasks/mozfest_backups/rollback.py`,
- select a timestamp. The format is YYYYMMDD-HHMM,
- let the script run,
- go to the S3 bucket and download the `entries-modified-TIMESTAMP.csv` and the 4 `before-rollback-RESOURCE-TIMESTAMP.json` files. Send those files to the person who asked for a rollback.
