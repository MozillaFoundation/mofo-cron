import re
import shutil
import subprocess
from datetime import date

import requests
import os

pipelines = {
    "foundation-site": "foundation-mofostaging-net",
    "network-pulse": "network-pulse-staging",
    "network-pulse-api": "network-pulse-api-staging",
    "donate-wagtail": "donate-wagtail-staging",
}

slack_webhook = os.environ["SLACK_PIPELINES_WEBHOOK"]


# Each commit line is divided into 4 columns, separated by two double spaces. We only keep the last two,
# which contain the commit's author and title.
def get_commits_info(commits):
    result = []
    for commit in commits:
        # Since Heroku doesn't use 2 spaces anymore to separate the columns, we use a positive lookbehind to find
        # everything that is after the commit hash and the time and date.
        extra_spaces = re.compile(r"\s{2,}")
        commit = re.sub(extra_spaces, " ", commit)
        m = re.search(
            r"(?<=[\w\d]{7}\s\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\s).*", commit
        )

        result.append(m.group(0) + "\n")

    return result


# We need an extra button to link to the Thunderbird donate pipeline
def when(condition, button):
    if condition:
        return [button]
    else:
        return []


# Task only run from Monday to Thursday
if date.today().weekday() in range(0, 4):

    # Install HerokuCLI
    if shutil.which("heroku"):
        print("Heroku CLI is already installed")
    else:
        subprocess.run(
            "curl https://cli-assets.heroku.com/heroku-linux-x64.tar.gz | tar -xz",
            shell=True,
            check=True,
        )
        os.environ["PATH"] += ":/app/heroku/bin"

    for app in pipelines:
        output = (
            subprocess.check_output(["heroku", "pipelines:diff", "-a", pipelines[app]])
            .decode()
            .splitlines(keepends=True)
        )

        if not output:
            requests.post(
                f"{slack_webhook}",
                json={
                    "text": ":fire_engine: Error while running `slack_webhook.py` task on `mofo-cron`. Check logs in "
                    "Scalyr."
                },
                headers={"Content-Type": "application/json"},
            ).raise_for_status()
            break
        else:
            """
            We expect Heroku's output to have this structure:
            - line 1 is empty,
            - line 2 is the name of the app. It also tells us if prod is behind staging or not.
            - line 3 is column titles and table structure,
            - line 4 to the third to last are commits (date, author, etc),
            - Line second to last is the GitHub diff URL,
            - Last line is an empty line.
            """
            title = output[1].strip("=\n").lstrip()
            commits_list = output[3:-2]
            if commits_list:
                if len(commits_list) >= 2:
                    body = "".join("- " + e for e in get_commits_info(commits_list))
                else:
                    body = get_commits_info(commits_list)[0]
            diff_url = output[-1].rstrip()
            up_to_date_regex = "is up to date"

            if re.search(up_to_date_regex, title):
                print(f"Nothing to promote for {app}")
            else:
                print(f"Posting message to Slack for {app}.")
                slack_payload = {
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f":package: *{title}:*\n"
                                        f"{body}"
                            }
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "View Github diff"
                                    },
                                    "url": f"{diff_url}"
                                },
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "View pipeline on Heroku"
                                    },
                                    "url": f"https://dashboard.heroku.com/pipelines/{app}"
                                }
                            ]
                            + when(
                                app == "donate-wagtail",
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "View Thunderbird pipeline"
                                    },
                                    "url": "https://dashboard.heroku.com/pipelines/thunderbird-donate"
                                }
                            )
                        }
                    ]
                }

                requests.post(
                    f"{slack_webhook}",
                    json=slack_payload,
                    headers={"Content-Type": "application/json"},
                ).raise_for_status()
else:
    print("The pipelines webhook task only runs from Monday to Thursday.")
