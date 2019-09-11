import re
import shutil
import subprocess
from datetime import date

import requests
import os

pipelines = {
    "foundation-site": "foundation-mofostaging-net",
    "donate-mozilla-org": "donate-mozilla-org-us-staging",
    "network-pulse": "network-pulse-staging",
    "network-pulse-api": "network-pulse-api-staging",
}

slack_webhook = os.environ["SLACK_PIPELINES_WEBHOOK"]


# Each commit line is divided into 4 columns, separated by two double spaces. We only keep the last two,
# which contain the commit's author and title.
def get_commits_info(commits):
    result = []
    for commit in commits:
        commit = re.split(r'\s{2,}', commit)
        commit_info = ': '.join(commit[2:4])
        result.append(commit_info)

    return result


# Task only run from Monday to Thursday
if date.today().weekday() in range(0, 4):

    # Install HerokuCLI
    if shutil.which("heroku"):
        print("Heroku CLI is already installed")
    else:
        subprocess.run("curl https://cli-assets.heroku.com/heroku-linux-x64.tar.gz | tar -xz", shell=True, check=True)
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
                    "text": ":fire_engine: Error while running `slack_webhook.py` task on `mofo-cron`. Check logs at "
                    f"https://eu.logentries.com/app/3aae5f3f#/search/log/628eb861?last=Last%2020%20Minutes"
                },
                headers={"Content-Type": "application/json"},
            ).raise_for_status()
            break
        else:
            """
            We expect Heroku's output to have this structure:
            - line 1 is empty,
            - line 2 is the name of the app. It also tells us if prod is behind staging or not.
            - line 3 and 4 are column titles and table structure,
            - line 5 to the third to last are commits (date, author, etc),
            - Line second to last is the GitHub diff URL,
            - Last line is an empty line.
            """
            title = output[1].strip("=\n").lstrip()
            if re.search("donate", title):
                title = "<@tchevalier>: " + title
            commits_list = output[4:-2]
            if commits_list:
                if len(commits_list) >= 2:
                    attachment_title = "Commits to deploy to production:"
                    body = "".join("- " + e for e in get_commits_info(commits_list))
                else:
                    attachment_title = "Commit to deploy to production:"
                    body = get_commits_info(commits_list)[0]
            diff_url = output[-1].rstrip()
            up_to_date_regex = "is up to date"

            if re.search(up_to_date_regex, title):
                print(f"Nothing to promote for {app}")
            else:
                print(f"Posting message to Slack for {app}.")
                slack_payload = {
                    "attachments": [
                        {
                            "fallback": f"{app} can be promoted to production.\n"
                            f"URL to Github diff: {diff_url}\n"
                            f"URL to pipeline: https://dashboard.heroku.com/pipelines/{app}",
                            "pretext": f"{title}",
                            "title": f"{attachment_title}",
                            "text": f"{body}",
                            "color": "#36bced",
                            "actions": [
                                {
                                    "type": "button",
                                    "text": "View Github diff",
                                    "url": f"{diff_url}",
                                },
                                {
                                    "type": "button",
                                    "text": "View pipeline on Heroku",
                                    "url": f"https://dashboard.heroku.com/pipelines/{app}",
                                },
                            ],
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
