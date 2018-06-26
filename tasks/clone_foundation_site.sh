#!/usr/bin/env bash

# Clone and scrub the production foundation site

#  exit on error
set -e

current_dir=`pwd`

echo "Checking the day of the week..."
DAYOFWEEK=`date +%a`
if [ ${DAYOFWEEK} -ne "Mon" ]; then
    echo "This task only executes on Mondays"
    exit
else
    echo "Happy Monday! Beginning database transfer process..."
fi

if [ -x `command -v heroku` ]; then
    echo "Heroku CLI is already installed..."
else
    echo "Downloading and extracting the standalone Heroku CLI tool..."
    curl "https://cli-assets.heroku.com/heroku-linux-x64.tar.xz" -o "heroku-linux-x64.tar.xz"
    tar -xf heroku-linux-x64.tar.xz
    alias heroku=${current_dir}/heroku/bin/heroku
fi

if [ -x `command -v aws` ]; then
    echo "AWS cli is already installed..."
else
    echo "Downloading and installing the AWS cli"
    curl "https://s3.amazonaws.com/aws-cli/awscli-bundle.zip" -o "awscli-bundle.zip"
    unzip awscli-bundle.zip
    ./awscli-bundle/install -b ~/bin/aws
    export PATH=~/bin:${PATH}
fi


production_app=${PRODUCTION_APP_NAME}
staging_app=${STAGING_APP_NAME}
staging_db=`heroku config:get -a ${staging_app} DATABASE_URL`

echo "Enabling maintenance mode on the staging app..."
heroku maintenance:on -a ${staging_app}

echo "Scaling web dynos on staging to 0..."
heroku ps:scale -a ${staging_app} web=0

echo "Backing up production DB..."
heroku pg:backups:capture -a ${production_app}

echo "Backing up staging DB..."
heroku pg:backups:capture -a ${staging_app}

echo "Restoring the latest Production backup to staging..."
backup_download_url=`heroku pg:backups:url -a ${production_app}`
heroku pg:backups:restore --confirm ${staging_app} -a ${staging_app} ${backup_download_url}

echo "Executing cleanup SQL script.."
psql ${staging_db} -f `realpath tasks/cleanup.sql`

echo "Syncing S3 Buckets"
aws s3 sync --region ${S3_REGION} s3://${PRODUCTION_S3_BUCKET}/${PRODUCTION_S3_PREFIX} s3://${STAGING_S3_BUCKET}/${STAGING_S3_PREFIX}

echo "Scaling web dynos on staging to 1..."
heroku ps:scale -a ${staging_app} web=1

echo "Disabling maintenance mode on staging.."
heroku maintenance:off -a ${staging_app}

echo "restoration complete!"
