import os
import sys
import requests


class ScriptError(Exception):
    """
    Something went wrong in the script, details in self.message
    """
    pass


# Authentication header class for requests
class TokenAuth(requests.auth.AuthBase):
    """
    Authentication class for requests.
    Adds a bearer token to the Authorization header
    """
    def __init__(self, token):
        self.token = token

    def __call__(self, request):
        request.headers['Authorization'] = f'Bearer {self.token}'
        return request


class DeleteResponses:
    """
    A class encapsulating the logic for deleting all the responses in every form contained within the authenticated
    Typeform account.
    """

    TYPEFORM_API = 'https://api.typeform.com/forms'

    def __init__(self, auth_token):
        """
        Initialize a class instance, setting the authentication token for making requests to TypeForm

        :param auth_token: str
            The token for making requests to TypeForm. Must have at least the following scopes:
            Forms: Read
            Responses: Read, Write

        :raises ScriptError
            If no auth_token provided to constructor
        """
        if not auth_token:
            raise ScriptError('auth_token not provided')

        self.token_auth = auth_token

    def decode_json(self, response):
        """
        Attempt to decode the JSON payload and exit with error if it fails

        :param response: requests.Response
            The response object from a requests request to convert into a dict
        :return: dict
            The dict representation of the JSON response
        :raises ScriptError:
            If payload is not valid JSON
        """
        try:
            return response.json()
        except ValueError as err:
            raise ScriptError(f'Failed to decode json payload for {response.request.method} {response.url}: {err}')

    def get_forms_by_page(self, page):
        """
        Make an HTTP GET request to list a given page of forms in the authenticated Typeform account
        API docs: https://developer.typeform.com/create/reference/retrieve-forms/#retrieve-forms

        :param page: int
            The page to fetch from the endpoint (will handle up to 200 forms per page)
        :return: (list, int)
            A tuple of the list of forms returned and the number of pages available to query.
        :raises ScriptError:
            If a non-OK status code is received from Typeform
        """
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

    def get_form_responses_by_page(self, form_id, page):
        """
        Make an HTTP GET request for a single page of a forms' responses. Up to 1000 per page.
        API docs: https://developer.typeform.com/responses/reference/retrieve-responses/#retrieve-responses

        :param form_id: str
            The Typeform form's identifier
        :param page: int
            The page number to request
        :return: (list, int)
            A tuple containing the list of response IDs and the number of pages available to query.
        :raises ScriptError:
            If a non-OK status code is received from Typeform
        """
        responses_response = requests.get(
            f'{self.TYPEFORM_API}/{form_id}/responses',
            auth=self.token_auth,
            params={
                'page_size': 1000,
            }
        )

        if responses_response.status_code != requests.codes.ok:
            raise ScriptError(f'Failed to retrieve responses for form: {form_id} - {responses_response.status_code}')

        json_response = self.decode_json(responses_response)

        # map the responses so we only have their IDs & Convert the map generator object into a proper list
        response_ids = list(map(lambda response: response['response_id'], json_response['items']))

        return response_ids, json_response['page_count']

    def get_form_id_list(self):
        """
        Fetch all forms in the account, one page at a time, concatenating all the pages together into a single list.

        :return: list
            A list of form ID strings
        """
        form_list = []

        response_forms, page_count = self.get_forms_by_page(1)
        form_list.extend(response_forms)

        if page_count > 1:
            for next_page in range(2, page_count + 1):
                response_forms, _ = self.get_forms_by_page(next_page)
                form_list.extend(response_forms)

        # map the list of forms into just form IDs and convert the map into a list.
        return list(map(lambda form_item: form_item['id'], form_list))

    def get_form_responses(self, form_id):
        """
        Get all responses for a form, one page at a time and concatenating the lists of response IDs together

        :param form_id: str
            The string identifier for a form, whose responses will be requested
        :return: list
            A list of string identifiers representing every response in a form
        """
        response_ids = []

        responses, page_count = self.get_form_responses_by_page(form_id, 1)
        response_ids.extend(responses)

        if page_count > 1:
            for current_page in range(2, page_count + 1):
                responses, _ = self.get_form_responses_by_page(form_id, current_page)
                response_ids.extend(responses)

        return response_ids

    def delete_responses(self, form_id, response_ids):
        """
        Make an HTTP DELETE request to delete all the responses identified in response_ids

        API docs: https://developer.typeform.com/responses/reference/delete-responses/#delete-responses

        :param form_id: str
            The string identifier of a Typeform form
        :param response_ids: list
            A list of response ID strings that will be deleted
        :return: None
        :raises ScriptError:
            If a non-OK status code is received from Typeform
        """
        #
        del_response = requests.delete(
            f'{self.TYPEFORM_API}/{form_id}/responses',
            auth=self.token_auth,
            params={
                'included_tokens': response_ids
            }
        )

        if del_response.status_code != requests.codes.ok:
            raise ScriptError(f'Failed to delete responses for form: {form_id} - {del_response.status_code}')

    #
    def delete_form_responses(self, form_id, response_ids):
        """
        Delete all responses for a form in batches of 25 ids (The request to delete responses has IDs in the query, so limiting it to something reasonably small)

        :param form_id:
            The string identifier of a Typeform form
        :param response_ids:
            A list of all response ID strings for the given Typeform form
        :return: None
        """
        num_to_delete = len(response_ids)
        while len(response_ids) > 0:
            to_del = response_ids[:25]
            response_ids = response_ids[25:]
            self.delete_responses(form_id, to_del)

        print(f'Deleted {num_to_delete} responses from form {form_id}')

    def execute(self):
        """
        Kicks off the chain of calls that glues every step together.

        1. Fetch all forms (by page if necessary)
        2. For each form, fetch all responses (by page if necessary)
        3. For each form, delete all responses (in batches of 25)

        :return: None
        """
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
    # If the script is called directly, instantiates and executes the process
    if 'TYPEFORM_AUTH_TOKEN' not in os.environ:
        print('You must set TYPEFORM_AUTH_TOKEN')
        exit(1)

    delete_responses = DeleteResponses(os.environ['TYPEFORM_AUTH_TOKEN'])
    delete_responses.execute()
