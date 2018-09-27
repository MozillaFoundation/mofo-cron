from itertools import groupby
import re

import click

from guidebook_backup import do_backup
from guidebook_rollback import prepare_data_to_rollback, do_rollback
from utilities import (
    get_bucket_content,
    filter_by_resources,
    write_csv,
    upload_csv_to_s3,
)


def get_timestamp(filename):
    """
    Search for timestamp in file name.

    :param filename: Key of a S3 object
    :return: timestamp YYYYMMDD-HHMM (string)
    """
    regex = re.compile("(?P<timestamp>\d+-\d+)")
    return regex.search(filename["Key"]).group("timestamp")


def is_valid_backup(list_files_s3):
    """
    Check on S3 which point in time we can rollback to. A valid point in time is a group of 4 files (one file per
    Guidebook resources). This point in time is represented by the timestamp in the backup's file name

    :return: Dict of available backups to rollback to.
    """
    guidebook_resources = ["guides", "schedule-tracks", "locations", "sessions"]

    # We only want backups files
    backups_list = []
    for resource in guidebook_resources:
        list_ = filter_by_resources(list_files_s3, resource)
        backups_list.extend(list_)

    # group by timestamp in file name, only keep groups of 4 files
    files_by_timestamp = {}

    backups_list = sorted(backups_list, key=get_timestamp)

    for k, g in groupby(backups_list, key=get_timestamp):
        groups = list(g)
        if len(groups) == 4:
            files_by_timestamp[k] = groups

    return files_by_timestamp


@click.command()
def rollback():
    """
    CLI tool to rollback substantial modifications made to the Mozfest Guidebook.
    """
    # Get all files from S3
    list_files = get_bucket_content()

    available_rollback_files = is_valid_backup(list_files)

    selected_timestamp = click.prompt(
        text="Select a rollback:\n", type=click.Choice(available_rollback_files.keys())
    )

    # Backup data from guidebook before initiating the rollback
    click.echo("Backup data currently in Guidebook just in case :D")
    do_backup(rollback=True)

    # Select backup data that needs to be restored
    modifications_list = prepare_data_to_rollback(list_files, selected_timestamp)

    # Apply all the changes to Guidebook
    do_rollback(modifications_list)

    # Upload a csv of all changes that were applied
    modifications_csv = write_csv(modifications_list)
    upload_csv_to_s3(modifications_csv)

    click.echo("Rollback completed!")


if __name__ == "__main__":
    rollback()
