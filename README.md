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


### tasks/heroku_pipelines_check

#### How to setup local dev

- Create a virtualenv: `python -m venv venv`. Activate it.
- Install pip-tools: `pip install pip-tools`.
- Install python dependencies by running `pip-sync requirements.txt dev-requirements.txt`.

This task checks Heroku pipelines and posts a message on Slack (#mofo-production) if staging could be promoted to prod. It runs from Monday to Thursday. Supported pipelines listed at the top of `slack_webhook.py`.

Dependencies (`Pipefile`):
- requests

Usage: `python tasks/heroku_pipelines_check/slack_webhook.py`

### tasks/typeform

This task will clear out **all** of the responses collected for **every** form in an authenticated Typeform account.
See the [docstrings in the code](/tasks/typeform/delete_responses.py) for more information on the process and for links
to Typeform API documentation for endpoints we're using and how to Authenticate.

#### Usage
1. activate the Python virtual environment (varies depending on OS)
2. execute `TYPEFORM_AUTH_TOKEN=some-value python tasks/typeform/delete_responses.py`

#### Testing
1. activate the Python virtual environment (varies depending on OS)
2. execute `python tasks/typeform/test_delete_responses.py`
