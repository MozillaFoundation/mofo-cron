import os
import sys
import requests


# Print a message and then terminate the script with an exit code of 1
def script_error(message):
    print(message)
    sys.exit(1)


TYPEFORM_API = 'https://api.typeform.com/forms'

try:
    auth_tok = os.environ['TYPEFORM_AUTH_TOKEN']
except KeyError:
    script_error('TYPEFORM_AUTH_TOKEN not defined')


# Authentication header class for requests
class TokenAuth(requests.auth.AuthBase):
    def __call__(self, token):
        return token


# Attempt to decode the JSON payload and exit with error if it fails
def decode_json(response):
    try:
        return response.json()
    except ValueError as err:
        script_error(f'Failed to decode json payload for {response.request.method} {response.url}: {err}')


# Make an HTTP request to the forms endpoint for a given page
# Returns a tuple of (forms, page_count)
def get_forms_by_page(page):
    # https://developer.typeform.com/create/reference/retrieve-forms/#retrieve-forms
    forms_response = requests.get(
        f'{TYPEFORM_API}',
        auth=TokenAuth(auth_tok),
        params={
            'page': page,
            'page_size': 200
        }
    )

    if forms_response.status_code != requests.codes.ok:
        script_error(f'Failed to get list of forms: {forms_response.reason} - {forms_response.status_code}')

    json_response = decode_json(forms_response)

    return json_response['items'], json_response['page_count']


# Make an HTTP request for a forms' responses, by page
# Returns a tuple of (responses, page_count)
def get_responses_for_form_by_page(form_id, page):
    # https://developer.typeform.com/responses/reference/retrieve-responses/#retrieve-responses
    responses_response = requests.get(
        f'{TYPEFORM_API}/forms/{form_id}/responses',
        auth=TokenAuth(auth_tok),
        params={
            'page_size': 1000,  # max allowed by API
            'fields': 'response_id',  # only get IDs, not content
        }
    )

    if responses_response.status_code != requests.codes.ok:
        script_error(f'Failed to retrieve responses for form: {form_id} - {responses_response.status_code}')

    json_response = decode_json(responses_response)

    return json_response['items'], json_response['page_count']


# Fetch all forms in the account, one page at a time
# Returns a list of form ids
def get_form_id_list():
    form_list = []

    # Get the first page of results, up to 200
    response_forms, page_count = get_responses_by_page(1)
    form_list.append(response_forms)

    # We probably won't ever go above 200 forms, but if we do, fetch them too
    if page_count > 1:
        for next_page in range(2, page_count + 1):
            response_forms, _ = get_forms_by_page(next_page)
            form_list.append(response_forms)

    # map the form_list into just form IDs
    return map(lambda form_item: form_item.id, form_list)


# Get all responses for a form, one page at a time
# Returns a list of response ids
def get_responses_for_form(form_id):
    response_ids = []

    responses, page_count = get_responses_for_form_by_page(form_id, 1)
    response_ids.append(responses)

    if page_count > 1:
        for current_page in range(2, page_count + 1):
            responses, _ = get_responses_for_form_by_page(form_id, current_page)
            response_ids.append(responses)

    return response_ids

# Make an HTTP request to delete the specified responses
def delete_responses(form_id, response_ids):
    # https://developer.typeform.com/responses/reference/delete-responses/#delete-responses
    del_response = requests.delete(
        f'{TYPEFORM_API}/forms/{form_id}/responses',
        auth=TokenAuth(auth_tok),
        params={
            'included_tokens': response_ids
        }
    )

    if del_response.status_code != requests.codes.ok:
        script_error(f'Failed to delete responses for form: {form_id} - {del_response.status_code}')


# Delete all responses for a form, 25 at a time
def delete_all_form_responses(form_id, response_ids):

    while len(response_ids) > 0:
        to_del = response_ids[:25]
        response_ids = response_ids[25:]
        delete_responses(form_id, to_del)


# Get the list of form IDs
form_id_list = get_form_id_list()

# For each form, fetch the list of response IDs and delete them
for form_id in form_id_list:
    delete_all_form_responses(form_id, get_responses_for_form(form_id))


