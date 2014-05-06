import os
import time
import unittest
from sharefile import ShareFileClient

sf_host = os.getenv('SF_HOST')
company = os.getenv('SF_COMPANY')
client_id = os.getenv('SF_CLIENT_ID')
client_secret = os.getenv('SF_CLIENT_SECRET')
username = os.getenv('SF_USERNAME')
password = os.getenv('SF_PASSWORD')
domain = os.getenv('SF_DOMAIN') # e.g. @ca.com
test_email_1 = os.getenv('SF_TEST_EMAIL_1') # e.g. sharefiletest1@ca.com
test_email_2 = os.getenv('SF_TEST_EMAIL_2') # e.g. sharefiletest2@ca.com


class ShareFileClientTest(unittest.TestCase):
    def setUp(self):
        self.client = ShareFileClient(sf_host, client_id, client_secret,
                                      username, password, company)

    def test_get_authid(self):
        authid = self.client.get_authid()
        self.assertIsNotNone(authid)
        self.assertIsNotNone(self.client.authid)

    def test_list_employees(self):
        employees = self.client.list_employees()
        self.assertIn('value', employees)
        self.assertIsInstance(employees['value'], list)
        self.assertTrue(len(employees['value']) > 10000)
        self.assertIn('Email', employees['value'][0])

    def test_get_employee(self):
        emp_id = username.split('@')[0]
        employee = self.client.get_employee(emp_id)
        self.assertIn('value', employee)
        self.assertEqual(employee['value']['primaryemail'], emp_id + domain)

    def test_get_nonexistent_employee(self):
        nonexistent = self.client.get_employee('wewillneverhavesomeonebythisname')
        self.assertTrue(nonexistent['error'])

    def test_create_delete_employee(self):
        email = test_email_1
        # First create
        employee = self.client.create_employee(email, 'ShareFile', 'ShareFile')
        self.assertIn('primaryemail', employee['value'])
        self.assertEqual(employee['value']['primaryemail'], email)
        # Then query
        found_employee = self.client.get_employee(email)
        self.assertFalse(found_employee['error'])
        self.assertEquals(found_employee['value']['primaryemail'], email)
        # Then delete
        deleted_employee = self.client.delete_employee(email)
        self.assertFalse(deleted_employee['error'])
        # Finally check delete
        missing_employee = self.client.get_employee(email)
        self.assertTrue(missing_employee['error'])

    def test_delete_reassign_folders_employee(self):
        email = test_email_2
        target = self.client.username
        # First create
        employee = self.client.create_employee(email, 'ShareFile', 'ShareFile',
                                               password)
        self.assertIn('primaryemail', employee['value'])
        self.assertEqual(employee['value']['primaryemail'], email)
        # Then query
        found_employee = self.client.get_employee(email)
        self.assertFalse(found_employee['error'])
        self.assertEquals(found_employee['value']['primaryemail'], email)
        # Then upload a file
        new_client = ShareFileClient(sf_host, client_id, client_secret, email,
                                     password, company)
        new_client.upload_file_to_home('testfile.txt')
        # Then delete and reassign
        result = self.client.delete_employee(email, target, completely=True)
        self.assertFalse(result['error'])
        # Get shared folders
        folders = self.client.get_shared_folders()
        self.assertFalse(folders['error'])
        self.assertTrue(len(folders['value']) > 0)
        folder_names = set(f['displayname'].lower() for f in folders['value'])
        self.assertIn(email.lower(), folder_names)
        # Then check delete
        missing_employee = self.client.get_employee(email)
        self.assertTrue(missing_employee['error'])
        # Finally delete folder
        test_folder = [f['id'] for f in folders['value']
                       if f['displayname'].lower() == email.lower()][0]
        result = self.client.delete_folder(test_folder)
        # Get shared folders again
        folders = self.client.get_shared_folders()
        self.assertFalse(folders['error'])
        self.assertTrue(len(folders['value']) >= 0)
        folder_names = set(f['displayname'].lower() for f in folders['value'])
        self.assertNotIn(email.lower(), folder_names)


if __name__ == '__main__':
    unittest.main(verbosity=5)
