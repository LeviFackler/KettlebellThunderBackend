from flask import Flask, jsonify

# Create an instance of the Flask class
app = Flask(__name__)

# Define a route for the root URL of the app
@app.route('/')
def hello_world():
    return 'Hello, Kettlebell Thunder Backend!'

# Define a route for a simple API-like health check
@app.route('/api/health')
def health_check():
    return jsonify(status="API is healthy and running!", message="Welcome to Kettlebell Thunder!")

if __name__ == '__main__':
    app.run(debug=True, port=5001)