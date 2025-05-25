import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime

#Get the base directory of the app
basedir = os.path.abspath(os.path.dirname(__file__))

# Create an instance of the Flask class
app = Flask(__name__)

# Database Configuration

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'add.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Initialize Extentions ---
db = SQLAlchemy(app) # Initialize SQLAlchemy with our app
migrate = Migrate(app, db) #Initialize Flask-Migrate with our app and database

# --- MODELS ---
class SnatchWorkout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    duration_minutes = db.Column(db.Integer, nullable=False)
    kettlebell_weight_kg = db.Column(db.Float, nullable=False) # Assuming weight in KG
    total_snatches = db.Column(db.Integer, nullable=False)
    total_weight_moved_kg = db.Column(db.Float, nullable=False) # Calculated field

    def __init__(self, workout_date, duration_minutes, kettlebell_weight_kg, total_snatches):
        self.workout_date = workout_date
        self.duration_minutes = duration_minutes
        self.kettlebell_weight_kg = kettlebell_weight_kg
        self.total_snatches = total_snatches
        # Calculate total weight moved upon initialization
        self.total_weight_moved_kg = kettlebell_weight_kg * total_snatches

    def __repr__(self):
        return f'<SnatchWorkout {self.id} on {self.workout_date.strftime("%Y-%m-%d")}>'

    def to_dict(self):
        """Serializes the object to a dictionary."""
        return {
            'id': self.id,
            'workout_date': self.workout_date.isoformat(), # Format date as YYYY-MM-DD
            'duration_minutes': self.duration_minutes,
            'kettlebell_weight_kg': self.kettlebell_weight_kg,
            'total_snatches': self.total_snatches,
            'total_weight_moved_kg': self.total_weight_moved_kg
        }

# --- ROUTES ---
@app.route('/')
def hello_world():
    return 'Hello, Kettlebell Thunder Backend!'

@app.route('/api/health')
def health_check():
    return jsonify(status="API is healthy and running!", message="Welcome to Kettlebell Thunder!")

# --- API Endpoints for Snatch Workouts ---

@app.route('/api/snatch_workouts', methods=['POST'])
def add_snatch_workout():
    data = request.get_json() # Get data from POST request body

    if not data:
        return jsonify({"error": "No input data provided"}), 400

    # Validate required fields
    required_fields = ['workout_date_str', 'duration_minutes', 'kettlebell_weight_kg', 'total_snatches']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    try:
        # Convert date string (e.g., "YYYY-MM-DD") to date object
        workout_date_obj = datetime.strptime(data['workout_date_str'], '%Y-%m-%d').date()

        new_workout = SnatchWorkout(
            workout_date=workout_date_obj,
            duration_minutes=data['duration_minutes'],
            kettlebell_weight_kg=data['kettlebell_weight_kg'],
            total_snatches=data['total_snatches']
        )
        db.session.add(new_workout)
        db.session.commit()
        return jsonify(new_workout.to_dict()), 201 # 201 Created
    except ValueError as e: # Catches errors from strptime or if data types are wrong for model
        db.session.rollback()
        return jsonify({"error": f"Invalid data format: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/snatch_workouts', methods=['GET'])
def get_all_snatch_workouts():
    try:
        workouts = SnatchWorkout.query.order_by(SnatchWorkout.workout_date.desc()).all()
        return jsonify([workout.to_dict() for workout in workouts]), 200
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)