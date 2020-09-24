import unittest
from unittest import TestCase
from unittest.mock import Mock, patch, call

from delete_responses import (
    DeleteResponses,
    TokenAuth,
    ScriptError
)

mock_forms_page_1 = [{'id': '1'}, {'id': '2'}]
mock_forms_page_2 = [{'id': '3'}, {'id': '4'}]
mock_forms_page_3 = [{'id': '5'}, {'id': '6'}]
mock_multi_page_return_values = [
    (mock_forms_page_1, 3),
    (mock_forms_page_2, 3),
    (mock_forms_page_3, 3)
]
mock_form_responses_page_1 = [{'response_id': '1'}, {'response_id': '2'}, {'response_id': '3'}]
mock_form_responses_page_2 = [{'response_id': '4'}, {'response_id': '5'}, {'response_id': '6'}]
mock_form_responses_page_3 = [{'response_id': '7'}, {'response_id': '8'}, {'response_id': '9'}]
mock_form_responses_return_values = [
    {
        'items': mock_form_responses_page_1,
        'page_count': 3
    },
    {
        'items': mock_form_responses_page_2,
        'page_count': 3
    },
    {
        'items': mock_form_responses_page_3,
        'page_count': 3
    }
]


class TestDeleteResponses(TestCase):
    def test_token_auth(self):
        test_value = 'test_token'
        token_auth = TokenAuth(test_value)
        request = Mock()
        request.headers = {}
        token_auth(request)
        self.assertEqual(request.headers.get('Authorization', None), f'Bearer {test_value}')

    @patch('delete_responses.DeleteResponses.get_forms_by_page')
    def test_get_form_id_list_empty(self, mock_get_forms_by_page):
        mock_get_forms_by_page.return_value = ([], 1)
        delete_responses = DeleteResponses()
        form_list = delete_responses.get_form_id_list()
        mock_get_forms_by_page.assert_called_once()
        self.assertEqual(form_list, [])

    @patch('delete_responses.DeleteResponses.get_forms_by_page')
    def test_get_form_id_list_one_page(self, mock_get_forms_by_page):
        mock_get_forms_by_page.return_value = (mock_forms_page_1, 1)
        delete_responses = DeleteResponses()
        form_list = delete_responses.get_form_id_list()
        mock_get_forms_by_page.assert_called_once()
        self.assertEqual(form_list, ['1', '2'])

    @patch('delete_responses.DeleteResponses.get_forms_by_page')
    def test_get_form_id_list_multi_page(self, mock_get_forms_by_page):
        mock_get_forms_by_page.side_effect = mock_multi_page_return_values
        delete_responses = DeleteResponses()
        form_list = delete_responses.get_form_id_list()
        calls = [call(1), call(2), call(3)]
        mock_get_forms_by_page.assert_has_calls(calls)
        self.assertEqual(form_list, ['1', '2', '3', '4', '5', '6'])

    @patch('requests.get')
    def test_get_forms_by_page_raises_err(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.side_effect = mock_response
        delete_responses = DeleteResponses()
        self.assertRaises(ScriptError, delete_responses.get_forms_by_page, 1)

    @patch('requests.get')
    def test_get_forms_by_page_bad_json(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('This is not JSON')
        mock_get.side_effect = mock_response
        delete_responses = DeleteResponses()
        self.assertRaises(ScriptError, delete_responses.get_forms_by_page, 1)

    @patch('requests.get')
    def test_get_form_responses_one_page(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': mock_form_responses_page_1,
            'page_count': 1
        }
        mock_get.return_value = mock_response
        delete_responses = DeleteResponses()
        response_list = delete_responses.get_form_responses('1')
        mock_get.assert_called_once()
        self.assertEqual(response_list, ['1', '2', '3'])

    @patch('requests.get')
    def test_get_form_responses_form_multi_page(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = mock_form_responses_return_values
        mock_get.return_value = mock_response
        delete_responses = DeleteResponses()
        response_list = delete_responses.get_form_responses('1')
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(response_list, ['1', '2', '3', '4', '5', '6', '7', '8', '9'])

    @patch('requests.get')
    def test_get_form_responses_by_page_raises_err(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.side_effect = mock_response
        delete_responses = DeleteResponses()
        self.assertRaises(ScriptError, delete_responses.get_form_responses, 1)

    @patch('requests.get')
    def test_get_form_responses_by_page_bad_json(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('This is not JSON')
        mock_get.side_effect = mock_response
        delete_responses = DeleteResponses()
        self.assertRaises(ScriptError, delete_responses.get_form_responses, 1)

    # TODO: test delete_all_form_responses and deleteresponses

    @patch('requests.delete')
    def test_delete_form_responses(self, mock_delete):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        delete_responses = DeleteResponses()
        try:
            delete_responses.delete_form_responses('1', ['1', '2', '3'])
        except ScriptError:
            self.fail('delete_responses.delete_form_responses() raised an exception unexpectedly')

    @patch('delete_responses.DeleteResponses.delete_responses')
    def test_delete_form_responses_batched(self, mock_delete_responses):
        delete_responses = DeleteResponses()
        response_ids = list(map(str, range(1, 300)))
        try:
            delete_responses.delete_form_responses('1', response_ids)
        except ScriptError:
            self.fail('delete_responses.delete_form_responses() raised an exception unexpectedly')
        self.assertEqual(mock_delete_responses.call_count, 12)

    @patch('requests.delete')
    def test_delete_responses_raises(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.side_effect = mock_response
        delete_responses = DeleteResponses()
        self.assertRaises(ScriptError, delete_responses.delete_responses, '1', ['1', '2', '3'])


if __name__ == '__main__':
    unittest.main()
