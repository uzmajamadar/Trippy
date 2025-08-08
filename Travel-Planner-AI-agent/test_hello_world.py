from flask import Flask
import unittest

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'

class HelloWorldTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_hello(self):
        response = self.app.get('/')
        self.assertEqual(response.data, b'Hello, World!')

if __name__ == '__main__':
    unittest.main()