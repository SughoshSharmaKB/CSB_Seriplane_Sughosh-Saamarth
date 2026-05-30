"""
Add this route to your existing Flask app (e.g., server.py or app.py).
Make sure generate.py is in the same directory as your Flask app.
"""

import subprocess
import json
import sys
import os
from flask import jsonify

# ─────────────────────────────────────────────
# ADD THIS ROUTE to your Flask app
# ─────────────────────────────────────────────

@app.route("/generate", methods=["POST"])
def generate_logs():
    try:
        generate_script = os.path.join(os.path.dirname(__file__), "generate.py")

        result = subprocess.run(
            [sys.executable, generate_script],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown error in generate.py"
            return jsonify({"error": error_msg}), 500

        data = json.loads(result.stdout)
        return jsonify(data)

    except subprocess.TimeoutExpired:
        return jsonify({"error": "generate.py timed out after 30 seconds"}), 500
    except json.JSONDecodeError:
        return jsonify({"error": "generate.py did not return valid JSON"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
