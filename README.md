# MoFo Cron

A collection of tasks that we wish to run at regular intervals. These tasks are run using the Heroku Scheduler addon.

## Tasks

### tasks/create_image.js

This task creates an image from the specified instance.

Usage: `node tasks/create_image {region} {instanceId} {Name} {NoReboot} {DryRun}`

* region - AWS region to use
* instanceId - id of the EC2 instance an image should be made of
* Name - a name for the image, which will have the date appended to it
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