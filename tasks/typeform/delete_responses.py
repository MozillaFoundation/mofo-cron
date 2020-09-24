import os
import sys
import requests


class ScriptError(Exception):
    """Something went wrong in the script, details in self.message"""
    pass


# Authentication header class for requests
class TokenAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, request):
        request.headers['Authorization'] = f'Bearer {self.token}'
        return request


class DeleteResponses:
    def __init__(self):
        self.TYPEFORM_API = 'https://api.typeform.com/forms'

        try:
            self.token_auth = TokenAuth(os.environ['TYPEFORM_AUTH_TOKEN'])
        except KeyError:
            raise ScriptError('TYPEFORM_AUTH_TOKEN not defined')

    # Attempt to decode the JSON payload and exit with error if it fails
    def decode_json(self, response):
        try:
            return response.json()
        except ValueError as err:
            raise ScriptError(f'Failed to decode json payload for {response.request.method} {response.url}: {err}')

    # Make an HTTP request to the forms endpoint for a given page
    # Returns a tuple of (forms, page_count)
    def get_forms_by_page(self, page):
        # https://developer.typeform.com/create/reference/retrieve-forms/#retrieve-forms
        forms_response = requests.get(
            f'{self.TYPEFORM_API}',
            auth=self.token_auth,
            params={
                'page': page,
                'page_size': 200
            }
        )

        if forms_response.status_code != requests.codes.ok:
            raise ScriptError(f'Failed to get list of forms: {forms_response.reason} - {forms_response.status_code}')

        json_response = self.decode_json(forms_response)

        return json_response['items'], json_response['page_count']

    # Make an HTTP request for a forms' responses, by page
    # Returns a tuple of (responses, page_count)
    def get_form_responses_by_page(self, form_id, page):
        # https://developer.typeform.com/responses/reference/retrieve-responses/#retrieve-responses
        responses_response = requests.get(
            f'{self.TYPEFORM_API}/{form_id}/responses',
            auth=self.token_auth,
            params={
                'page_size': 1000,  # max allowed by API
            }
        )

        if responses_response.status_code != requests.codes.ok:
            raise ScriptError(f'Failed to retrieve responses for form: {form_id} - {responses_response.status_code}')

        json_response = self.decode_json(responses_response)

        response_ids = list(map(lambda response: response['response_id'], json_response['items']))

        return response_ids, json_response['page_count']

    # Fetch all forms in the account, one page at a time
    # Returns a list of form ids
    def get_form_id_list(self):
        form_list = []

        # Get the first page of results, up to 200
        response_forms, page_count = self.get_forms_by_page(1)
        form_list.extend(response_forms)

        # We probably won't ever go above 200 forms, but if we do, fetch them too
        if page_count > 1:
            for next_page in range(2, page_count + 1):
                response_forms, _ = self.get_forms_by_page(next_page)
                form_list.extend(response_forms)

        # map the form_list into just form IDs
        return list(map(lambda form_item: form_item['id'], form_list))

    # Get all responses for a form, one page at a time
    # Returns a list of response ids
    def get_form_responses(self, form_id):
        response_ids = []

        responses, page_count = self.get_form_responses_by_page(form_id, 1)
        response_ids.extend(responses)

        if page_count > 1:
            for current_page in range(2, page_count + 1):
                responses, _ = self.get_form_responses_by_page(form_id, current_page)
                response_ids.extend(responses)

        return response_ids

    # Make an HTTP request to delete the specified responses
    def delete_responses(self, form_id, response_ids):
        # https://developer.typeform.com/responses/reference/delete-responses/#delete-responses
        del_response = requests.delete(
            f'{self.TYPEFORM_API}/{form_id}/responses',
            auth=self.token_auth,
            params={
                'included_tokens': response_ids
            }
        )

        if del_response.status_code != requests.codes.ok:
            raise ScriptError(f'Failed to delete responses for form: {form_id} - {del_response.status_code}')

    # Delete all responses for a form, 25 at a time
    def delete_form_responses(self, form_id, response_ids):
        num_to_delete = len(response_ids)
        while len(response_ids) > 0:
            to_del = response_ids[:25]
            response_ids = response_ids[25:]
            self.delete_responses(form_id, to_del)
        print(f'Deleted {num_to_delete} responses from form {form_id}')

    def execute(self):
        try:
            # Get the list of form IDs
            form_id_list = self.get_form_id_list()

            if len(form_id_list) == 0:
                print('No forms in account')
                exit(0)

            # For each form, fetch the list of response IDs and delete them
            for form_id in form_id_list:
                form_responses = self.get_form_responses(form_id)
                self.delete_form_responses(form_id, form_responses)
        except ScriptError as err:
            print(f'Failed to execute: {err.message}')


if __name__ == '__main__':
    delete_responses = DeleteResponses()
    delete_responses.execute()
