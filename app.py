import os
import jwt
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta, timezone
from flask_bcrypt import Bcrypt

#Get the base directory of the app
basedir = os.path.abspath(os.path.dirname(__file__))

# Create an instance of the Flask class
app = Flask(__name__)

# --- Ensure SECRET_KEY is set robustly ---
# If you haven't already, set a strong secret key.
# You can generate one using: import os; os.urandom(24)
# It's best to set this from an environment variable in production.
if not app.config.get("SECRET_KEY"):
    app.config["SECRET_KEY"] = "your_super_secret_and_random_key_for_development" # CHANGE THIS FOR PRODUCTION
    print("WARNING: Using default SECRET_KEY. Please set a strong SECRET_KEY in your config or environment.")

app.config["JWT_EXPIRATION_DELTA"] = timedelta(hours=1) # Token expires in 1 hour (adjust as needed)


# Database Configuration

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'add.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Initialize Extentions ---
db = SQLAlchemy(app) # Initialize SQLAlchemy with our app
migrate = Migrate(app, db) #Initialize Flask-Migrate with our app and database
bcrypt = Bcrypt(app)

# --- MODELS ---

class User(db.Model): # <<< NEW MODEL
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False) # Increased length for bcrypt hash
    workouts = db.relationship('SnatchWorkout', backref='user', lazy=True)

    def set_password(self, password): # <<< NEW METHOD
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password): # <<< NEW METHOD
        return bcrypt.check_password_hash(self.password_hash, password)


    def __repr__(self):
        return f'<User {self.username}>'


class SnatchWorkout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    duration_minutes = db.Column(db.Integer, nullable=False)
    kettlebell_weight_kg = db.Column(db.Float, nullable=False) # Assuming weight in KG
    total_snatches = db.Column(db.Integer, nullable=False)
    total_weight_moved_kg = db.Column(db.Float, nullable=False) # Calculated field
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reps_per_interval = db.Column(db.Integer, nullable=False)


    def __init__(self, reps_per_interval, workout_date, duration_minutes, kettlebell_weight_kg, total_snatches):
        self.reps_per_interval = reps_per_interval
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
            'total_weight_moved_kg': self.total_weight_moved_kg,
            'reps_per_interval': self.reps_per_interval,
            'user_id': self.user_id
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
        # Fetch workouts ordered by date ascending to make comparison easier
        workouts_query = SnatchWorkout.query.order_by(SnatchWorkout.workout_date.asc()).all()
        
        processed_workouts = []
        # Dictionary to keep track of the last total_weight_moved for each kettlebell weight
        # Key: kettlebell_weight_kg, Value: last total_weight_moved_kg
        last_total_weight_moved_by_kb = {}

        for workout in workouts_query:
            workout_dict = workout.to_dict() # Get the basic dictionary representation
            percentage_change = None # Default to None

            current_kb_weight = workout.kettlebell_weight_kg
            current_total_weight_moved = workout.total_weight_moved_kg

            if current_kb_weight in last_total_weight_moved_by_kb:
                previous_total_weight_moved = last_total_weight_moved_by_kb[current_kb_weight]
                if previous_total_weight_moved is not None and previous_total_weight_moved > 0: # Avoid division by zero or if previous was None
                    change = current_total_weight_moved - previous_total_weight_moved
                    percentage_change = (change / previous_total_weight_moved) * 100
                    percentage_change = round(percentage_change, 2) # Round to 2 decimal places
            
            workout_dict['percentage_change_from_previous_same_weight'] = percentage_change
            
            # Update the last known total weight moved for this kettlebell weight
            last_total_weight_moved_by_kb[current_kb_weight] = current_total_weight_moved
            
            processed_workouts.append(workout_dict)

        # Optional: Re-sort by date descending for the API response (common for display)
        processed_workouts.sort(key=lambda w: w['workout_date'], reverse=True)
            
        return jsonify(processed_workouts), 200
    except Exception as e:
        # Log the exception for debugging on the server
        app.logger.error(f"Error in get_all_snatch_workouts: {str(e)}") 
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    
# --- AUTHENTICATION ROUTES ---

@app.route('/api/auth/register', methods=['POST'])
def register_user():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No input data provided"}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "Missing username, email, or password"}), 400

    # Check if username already exists
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409 # 409 Conflict

    # Check if email already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email address already registered"}), 409 # 409 Conflict

    # Create new user
    new_user = User(username=username, email=email)
    new_user.set_password(password) # Hashes the password

    try:
        db.session.add(new_user)
        db.session.commit()
        # Return some user info (but NOT the password hash)
        return jsonify({
            "message": "User registered successfully!",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email
            }
        }), 201 # 201 Created
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error during registration: {str(e)}") # Log the error server-side
        return jsonify({"error": "Registration failed due to an internal error"}), 500

# --- LOGIN ROUTE ---

@app.route('/api/auth/login', methods=['POST'])
def login_user():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No input data provided"}), 400

    # Allow login with either username or email
    identifier = data.get('identifier') # Can be username or email
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"error": "Missing identifier (username/email) or password"}), 400

    # Try to find user by email first, then by username
    user = User.query.filter_by(email=identifier).first()
    if not user:
        user = User.query.filter_by(username=identifier).first()

    if user and user.check_password(password):
        # Credentials are valid, generate JWT
        try:
            payload = {
                'exp': datetime.now(timezone.utc) + app.config["JWT_EXPIRATION_DELTA"], # Expiration time
                'iat': datetime.now(timezone.utc), # Issued at time
                'sub': user.id # Subject of the token (user ID)
            }
            token = jwt.encode(
                payload,
                app.config["SECRET_KEY"],
                algorithm="HS256" # Standard algorithm for symmetric keys
            )
            return jsonify({"message": "Login successful!", "access_token": token}), 200
        except Exception as e:
            app.logger.error(f"Error generating token: {str(e)}")
            return jsonify({"error": "Token generation failed"}), 500
    else:
        # Invalid credentials
        return jsonify({"error": "Invalid username/email or password"}), 401 # 401 Unauthorized




if __name__ == '__main__':
    app.run(debug=True, port=5001)