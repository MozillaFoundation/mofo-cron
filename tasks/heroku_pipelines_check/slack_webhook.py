import re
import subprocess
import requests
import os

pipelines = {
    "foundation-site": "foundation-mofostaging-net",
    "mozillafestival-org": "mozillafestival-org-staging",
    "donate-mozilla-org": "donate-mozilla-org-us-staging",
}

slack_webhook = os.environ["SLACK_PIPELINES_WEBHOOK"]

for app in pipelines:
    output = (
        subprocess.check_output(["heroku", "pipelines:diff", "-a", pipelines[app]])
        .decode()
        .splitlines(keepends=True)
    )
    title = output[1].strip("=\n").lstrip()
    body = ''.join(output[4:-2])
    diff_url = output[-1].strip("\n")

    regex = "is up to date"

    if re.search(regex, title):
        print(f"Nothing to promote for {app}")
        pass
    else:
        slack_payload = {
            "attachments": [
                {
                    "fallback": f"{app} can be promoted to production.\n"
                    f"URL to Github diff: {diff_url}\n"
                    f"URL to pipeline: https://dashboard.heroku.com/pipelines/{app}",
                    "pretext": f"{title}",
                    "title": f"Commit(s) to deploy to production:",
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

        r = requests.post(f'{slack_webhook}',
                          json=slack_payload,
                          headers={'Content-Type': 'application/json'}
                          )
