"""
Health check endpoint for monitoring and load balancers.
This simple script can be run separately or integrated into the main app.
"""

from flask import Flask, jsonify
import os
import sys

app = Flask(__name__)

@app.route('/health', methods=['GET'])
@app.route('/healthz', methods=['GET'])
def health_check():
    """
    Health check endpoint for container orchestration and load balancers.
    Returns 200 OK if the application is healthy.
    """
    return jsonify({
        'status': 'healthy',
        'service': 'shift-planner',
        'version': os.getenv('VERSION', 'dev')
    }), 200

@app.route('/ready', methods=['GET'])
def readiness_check():
    """
    Readiness check - verifies the app is ready to serve traffic.
    """
    # Add checks for database connectivity, required files, etc.
    try:
        # Example: Check if database file exists
        db_path = os.getenv('DB_PATH', 'shift_maker.sqlite3')
        if os.path.exists(db_path):
            return jsonify({
                'status': 'ready',
                'database': 'connected'
            }), 200
        else:
            return jsonify({
                'status': 'not ready',
                'database': 'not found'
            }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 503

if __name__ == '__main__':
    port = int(os.getenv('HEALTH_CHECK_PORT', 8001))
    app.run(host='0.0.0.0', port=port)
