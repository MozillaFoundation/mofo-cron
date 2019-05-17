#!/usr/bin/env bash

# Clone and scrub the production foundation site

on_exit() {
    RV=$?

    # If the script exits with a non-zero exit code, force a staging rollback and
    # ensure that staging is not in maintenance mode or scaled down
    if [ $RV -ne 0 ]; then
        echo "Rolling back staging..."
        heroku pg:backups:restore -a ${staging_app} --confirm ${staging_app}

        echo "Scaling web dynos on staging to 1..."
        heroku ps:scale -a ${staging_app} web=1

        echo "Disabling maintenance mode on the staging app..."
        heroku maintenance:off -a ${staging_app}
    else
        echo "task complete!"
    fi

    exit $RV
}

trap 'on_exit' 0

set -e

current_dir=$(pwd)

# Option to check if today is a Monday
while [[ $# -gt 0 ]]
do key="$1"

case $key in
    --only-monday)
    echo "Checking the day of the week..."
    DAYOFWEEK=$(date +%u)
    if [ "${DAYOFWEEK}" -ne 1 ]; then
        echo "The clone foundation DB task only executes on Mondays"
        exit 0
    else
        echo "Happy Monday! Beginning database transfer process..."
    fi
    shift
    ;;
    *)
    echo "Invalid option. Use --only-monday to make this task run on Mondays only."
    exit 0
    ;;
esac
done

# temporarily disable automatic exit on non-zero exit code
set +e

echo "Beginning database transfer process..."

HEROKU_BIN=$(command -v heroku)


if [ "$?" -eq 0 ]; then
    echo "Heroku CLI is already installed..."
else
    echo "Downloading and extracting the standalone Heroku CLI tool..."
    curl "https://cli-assets.heroku.com/heroku-linux-x64.tar.gz" -o "heroku-linux-x64.tar.gz"
    tar -xf heroku-linux-x64.tar.gz
    export PATH=~/heroku/bin:${PATH}
fi

echo "Check if AWS cli is installed..."
AWS_BIN=$(python -c "import awscli")

if [ "$?" -eq 0 ]; then
    echo "AWS cli is already installed..."
else
    echo "Installing the AWS cli"
    pip install awscli
fi

# re-enable exit on non-zero exit code
set -e

production_app=${PRODUCTION_APP_NAME}
staging_app=${STAGING_APP_NAME}
staging_db=$(heroku config:get -a ${staging_app} DATABASE_URL)

echo "Enabling maintenance mode on the staging app..."
heroku maintenance:on -a ${staging_app}

echo "Scaling web dynos on staging to 0..."
heroku ps:scale -a ${staging_app} web=0

echo "Backing up production DB..."
heroku pg:backups:capture -a ${production_app}

echo "Backing up staging DB..."
heroku pg:backups:capture -a ${staging_app}

echo "Restoring the latest Production backup to staging..."
backup_download_url=$(heroku pg:backups:url -a ${production_app})
heroku pg:backups:restore --confirm ${staging_app} -a ${staging_app} ${backup_download_url}

echo "Executing cleanup SQL script.."
psql ${staging_db} -f ./tasks/clone_foundation_site/cleanup.sql

echo "Syncing S3 Buckets"
python -m awscli s3 sync --region ${S3_REGION} s3://${PRODUCTION_S3_BUCKET}/${PRODUCTION_S3_PREFIX} s3://${STAGING_S3_BUCKET}/${STAGING_S3_PREFIX}

echo "Running migrations..."
heroku run -a ${staging_app} -- python network-api/manage.py migrate --no-input

echo "Scaling web dynos on staging to 1..."
heroku ps:scale -a ${staging_app} web=1

echo "Disabling maintenance mode on staging.."
heroku maintenance:off -a ${staging_app}
